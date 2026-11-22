import math
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def split_flac(filename="input.flac", min_silence=0.5):
    source = Path(filename)
    info = sf.info(source)
    audio, sample_rate = sf.read(
        source, dtype="int32", always_2d=True
    )

    silent = np.all(audio == 0, axis=1)
    edges = np.diff(
        np.concatenate(([False], silent, [False])).astype(np.int8)
    )
    silence_starts = np.flatnonzero(edges == 1)
    silence_ends = np.flatnonzero(edges == -1)

    minimum_frames = math.ceil(min_silence * sample_rate)
    count = 0

    def save_segment(start, end):
        nonlocal count
        segment = audio[start:end]

        # Trim exact silence at the segment's edges.
        active = np.flatnonzero(np.any(segment != 0, axis=1))
        if not len(active):
            return

        segment = segment[active[0]:active[-1] + 1]
        count += 1
        output = source.parent / f"{count:03d}_split.flac"
        sf.write(
            output,
            segment,
            sample_rate,
            format="FLAC",
            subtype=info.subtype,
        )
        print(output)

    position = 0
    for start, end in zip(silence_starts, silence_ends):
        if end - start >= minimum_frames:
            save_segment(position, start)
            position = end

    save_segment(position, len(audio))
    print(f"Created {count} files.")


if __name__ == "__main__":
    split_flac(sys.argv[1] if len(sys.argv) > 1 else "input.flac")
