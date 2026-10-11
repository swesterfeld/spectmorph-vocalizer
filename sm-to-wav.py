#!/usr/bin/env python3

"""Render an Audio .sm file at a fixed MIDI note using smscript."""

import argparse
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave


OUTPUT_RATE = 48_000  # hard-coded by src/smscript.cc
WARMUP_SAMPLES = round(0.030 * OUTPUT_RATE)


def default_smtool() -> str:
    """Find the common installed smtool location without requiring shell setup."""
    in_path = shutil.which("smtool")
    if in_path:
        return in_path
    spectmorph_install = Path("/usr/local/spectmorph/bin/smtool")
    if spectmorph_install.is_file():
        return str(spectmorph_install)
    return "smtool"


def tool_output(tool: str, sm_file: Path, mode: str) -> float:
    result = subprocess.run(
        [tool, str(sm_file), mode],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    match = re.search(r":\s*([-+0-9.eE]+)\s*$", result.stdout)
    if not match:
        raise RuntimeError(
            f"could not parse output of {tool} {sm_file} {mode}: "
            f"{result.stdout!r}"
        )
    return float(match.group(1))


def load_frame_times(volume_file: Path) -> list[float]:
    times = []
    with volume_file.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            fields = line.split()
            if not fields:
                continue
            try:
                times.append(float(fields[0]) / 1000.0)
            except (ValueError, IndexError) as error:
                raise ValueError(
                    f"invalid line {line_number} in {volume_file}: {line.rstrip()}"
                ) from error

    if len(times) < 2:
        raise ValueError(f"{volume_file} must contain at least two frame timestamps")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError(f"timestamps in {volume_file} are not strictly increasing")
    return times


def write_smscript(
    script_file: Path,
    sm_file: Path,
    frame_times: list[float],
    midi_note: int,
    time_stretch: float,
    output_samples: int,
) -> None:
    if '"' in str(sm_file) or "\n" in str(sm_file):
        raise ValueError("the input filename may not contain a quote or newline")

    frequency = 440.0 * 2.0 ** ((midi_note - 69) / 12.0)
    frame_count = len(frame_times)

    # A seek selects the closest analysis frame.  Change frames at the midpoint
    # between their timestamps, matching utils.py's round-to-nearest behavior.
    boundaries = [0]
    boundaries.extend(
        round((a + b) * 0.5 * time_stretch * OUTPUT_RATE)
        for a, b in zip(frame_times, frame_times[1:])
    )
    boundaries.append(output_samples)
    boundaries = [max(0, min(output_samples, sample)) for sample in boundaries]

    with script_file.open("w", encoding="utf-8") as script:
        print(f'load "{sm_file}"', file=script)
        print("morphing 0.5", file=script)

        # smscript has a built-in 15-cent vibrato.  freq-glissando ramps its
        # vibrato depth to zero over 30 ms.  Prime that smoother with a silent
        # frame; the caller removes these samples from the resulting WAV.
        print("seek 0 0 0 0", file=script)
        print("seek 1 0 0 0", file=script)
        print(f"freq-glissando {frequency:.12g}", file=script)
        print(f"process {WARMUP_SAMPLES}", file=script)

        for index in range(frame_count):
            sample_count = boundaries[index + 1] - boundaries[index]
            if sample_count <= 0:
                continue
            position = index / (frame_count - 1)
            # Both morph inputs use the same unscaled frame.  The .volume file
            # is deliberately used only for timing; its amplitude column is not
            # applied to the already encoded spectral data.
            print(f"seek 0 0 {position:.17g} 1", file=script)
            print(f"seek 1 0 {position:.17g} 1", file=script)
            print(f"process {sample_count}", file=script)


def remove_warmup(input_file: Path, output_file: Path) -> None:
    with wave.open(str(input_file), "rb") as source:
        if source.getframerate() != OUTPUT_RATE:
            raise RuntimeError(
                f"smscript produced {source.getframerate()} Hz audio, "
                f"expected {OUTPUT_RATE} Hz"
            )
        if source.getnframes() < WARMUP_SAMPLES:
            raise RuntimeError("smscript output is shorter than its warm-up")
        remaining_frames = source.getnframes() - WARMUP_SAMPLES
        source.setpos(WARMUP_SAMPLES)

        with wave.open(str(output_file), "wb") as destination:
            destination.setnchannels(source.getnchannels())
            destination.setsampwidth(source.getsampwidth())
            destination.setframerate(source.getframerate())
            destination.setnframes(remaining_frames)
            destination.setcomptype(source.getcomptype(), source.getcompname())
            while audio := source.readframes(65_536):
                destination.writeframesraw(audio)


def find_tool(value: str, description: str) -> str:
    if "/" in value:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"{description} not found: {path}")
        return str(path)
    found = shutil.which(value)
    if found is None:
        raise FileNotFoundError(f"{description} not found in PATH: {value}")
    return found


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Render an .sm file at an optional time-stretch factor without "
            "amplitude changes, transposed to a fixed MIDI note."
        )
    )
    parser.add_argument("input", type=Path, help="input .sm file made by mkplan")
    parser.add_argument("midi_note", type=int, help="output MIDI note (0-127)")
    parser.add_argument("output", type=Path, help="output .wav file")
    parser.add_argument(
        "--time-stretch",
        type=float,
        default=1.0,
        metavar="FACTOR",
        help="duration multiplier; 2.0 is twice as long (default: 1.0)",
    )
    parser.add_argument(
        "--volume",
        type=Path,
        help="mkplan .volume sidecar (default: input name with .volume suffix)",
    )
    parser.add_argument(
        "--smscript",
        default=str(Path(__file__).resolve().parent / "src" / "smscript"),
        help="smscript executable (default: src/smscript next to this script)",
    )
    parser.add_argument(
        "--smtool",
        default=default_smtool(),
        help="smtool executable used to read duration metadata",
    )
    args = parser.parse_args()

    if not 0 <= args.midi_note <= 127:
        parser.error("midi_note must be between 0 and 127")
    if not math.isfinite(args.time_stretch) or args.time_stretch <= 0:
        parser.error("--time-stretch must be a finite number greater than zero")

    sm_file = args.input.expanduser().resolve()
    output_file = args.output.expanduser().resolve()
    volume_file = (
        args.volume.expanduser().resolve()
        if args.volume
        else sm_file.with_suffix(".volume")
    )
    if not sm_file.is_file():
        parser.error(f"input file not found: {sm_file}")
    if not volume_file.is_file():
        parser.error(f"volume sidecar not found: {volume_file}")
    if not output_file.parent.is_dir():
        parser.error(f"output directory not found: {output_file.parent}")

    try:
        smscript = find_tool(args.smscript, "smscript")
        smtool = find_tool(args.smtool, "smtool")
        frame_times = load_frame_times(volume_file)
        source_samples = tool_output(smtool, sm_file, "sample-count")
        source_rate = tool_output(smtool, sm_file, "mix-freq")
        output_samples = round(
            source_samples / source_rate * OUTPUT_RATE * args.time_stretch
        )

        with tempfile.TemporaryDirectory(prefix="sm-to-wav-") as temp_dir:
            temp_path = Path(temp_dir)
            script_file = temp_path / "render.script"
            frames_file = temp_path / "frames.txt"
            untrimmed_wav = temp_path / "render.wav"
            write_smscript(
                script_file,
                sm_file,
                frame_times,
                args.midi_note,
                args.time_stretch,
                output_samples,
            )
            child_env = os.environ.copy()
            installed_lib = Path(smtool).resolve().parent.parent / "lib"
            if installed_lib.is_dir():
                old_library_path = child_env.get("LD_LIBRARY_PATH")
                child_env["LD_LIBRARY_PATH"] = str(installed_lib)
                if old_library_path:
                    child_env["LD_LIBRARY_PATH"] += os.pathsep + old_library_path
            subprocess.run(
                [smscript, str(script_file), str(untrimmed_wav), str(frames_file)],
                check=True,
                env=child_env,
            )
            remove_warmup(untrimmed_wav, output_file)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
