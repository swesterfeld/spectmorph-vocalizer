import argparse
from bisect import bisect_left, bisect_right
import math
from pathlib import Path

import numpy as np
import soundfile as sf


SAFE_LABELS = {"_", "!"}


def read_labels(filename):
    """Read Audacity point labels; each label lasts until the next point."""
    labels = []
    for number, line in enumerate(Path(filename).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split("\t", 2)
        try:
            start, end = map(float, fields[:2])
            name = fields[2].strip()
            if not math.isfinite(start) or start < 0 or start != end or not name:
                raise ValueError
            if labels and start <= labels[-1][0]:
                raise ValueError
        except (ValueError, IndexError):
            raise ValueError(
                f"{filename}:{number}: expected increasing point labels "
                "(time<TAB>time<TAB>label)"
            ) from None
        labels.append((start, name))
    if not labels:
        raise ValueError(f"{filename}: no labels")
    return labels


def split_flac(filename="input.flac", min_silence=0.5, labels_filename=None):
    """Split at exact silence, preserving point labels relative to trimmed audio.

    Labels default to the input's .txt sibling. All cuts and discarded labelled
    regions must be rests (_) or unused data (!); validate before writing files.
    """
    if not math.isfinite(min_silence) or min_silence <= 0:
        raise ValueError("min_silence must be positive and finite")
    source = Path(filename)
    labels = read_labels(labels_filename or source.with_suffix(".txt"))
    times = [time for time, _ in labels]
    info = sf.info(source)
    audio, sample_rate = sf.read(source, dtype="int32", always_2d=True)
    duration = len(audio) / sample_rate
    if times[-1] > duration:
        raise ValueError("Labels extend beyond the recording")
    errors = []

    def check_boundary(frame):
        if frame in (0, len(audio)):
            return
        time = frame / sample_rate
        index = bisect_right(times, time) - 1
        name = labels[index][1] if index >= 0 else "<unlabelled>"
        if name not in SAFE_LABELS:
            errors.append(
                f"Unsafe split/trim boundary at {time:.6f}s: label {name!r}; "
                "expected '_' or '!'"
            )

    def check_discarded(start, end):
        # Also catch an entire phone inside a zero-valued gap. The unlabelled
        # prefix has no labels to lose, but any interior cut still needs a label.
        if start >= end:
            return
        first = max(0, bisect_right(times, start / sample_rate) - 1)
        last = bisect_left(times, end / sample_rate)
        for time, name in labels[first:last]:
            if name not in SAFE_LABELS:
                errors.append(
                    f"Discarded silence {start / sample_rate:.6f}–"
                    f"{end / sample_rate:.6f}s contains label {name!r} "
                    f"at {time:.6f}s"
                )

    silent = np.all(audio == 0, axis=1)
    edges = np.diff(
        np.concatenate(([False], silent, [False])).astype(np.int8)
    )
    silence_starts = np.flatnonzero(edges == 1)
    silence_ends = np.flatnonzero(edges == -1)
    minimum_frames = math.ceil(min_silence * sample_rate)
    segments = []

    def add_segment(start, end):
        active = np.flatnonzero(~silent[start:end])
        if len(active):
            segments.append((start + int(active[0]), start + int(active[-1]) + 1))

    position = 0
    for start, end in zip(silence_starts, silence_ends):
        if end - start >= minimum_frames:
            add_segment(position, start)
            position = end
    add_segment(position, len(audio))

    position = 0
    for start, end in segments:
        check_boundary(start)
        check_boundary(end)
        check_discarded(position, start)
        position = end
    check_discarded(position, len(audio))
    if errors:
        raise ValueError(
            f"Found {len(errors)} splitting validation errors:\n" + "\n".join(errors)
        )

    for count, (start, end) in enumerate(segments, 1):
        start_time, end_time = start / sample_rate, end / sample_rate
        first = bisect_right(times, start_time)
        last = bisect_left(times, end_time)
        output_labels = []
        if first:
            # Retain the label already in effect at the trimmed start.
            output_labels.append((0.0, labels[first - 1][1]))
        output_labels.extend((time - start_time, name) for time, name in labels[first:last])
        output = source.parent / f"{count:03d}_split.flac"
        sf.write(output, audio[start:end], sample_rate, format="FLAC", subtype=info.subtype)
        output.with_suffix(".txt").write_text(
            "".join(f"{time:.6f}\t{time:.6f}\t{name}\n" for time, name in output_labels),
            encoding="utf-8",
        )
        print(output)
    print(f"Created {len(segments)} FLAC/TXT pairs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=split_flac.__doc__)
    parser.add_argument("filename", nargs="?", default="input.flac")
    parser.add_argument("labels", nargs="?", help="point labels (default: input's .txt sibling)")
    parser.add_argument("--min-silence", type=float, default=0.5, help="minimum silence in seconds")
    args = parser.parse_args()
    try:
        split_flac(args.filename, args.min_silence, args.labels)
    except ValueError as error:
        parser.exit(1, f"Error: {error}\n")
