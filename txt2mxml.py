#!/usr/bin/env python3
from music21 import note, stream, duration
import sys

def parse_line(line):
    parts = line.strip().split(maxsplit=2)

    if len(parts) < 2:
        raise ValueError(f"Invalid line: '{line}'")

    pitch_or_rest = parts[0]
    try:
        dur = float(parts[1])
    except ValueError:
        raise ValueError(f"Invalid duration: '{parts[1]}' in line '{line}'")

    lyric = parts[2] if len(parts) == 3 else None

    if pitch_or_rest.lower() == "rest":
        n = note.Rest(quarterLength=dur)
        return n

    try:
        midi_note = int(pitch_or_rest)
    except ValueError:
        raise ValueError(f"Invalid MIDI note: '{pitch_or_rest}' in line '{line}'")

    n = note.Note()
    n.pitch.midi = midi_note
    n.quarterLength = dur
    if lyric:
        n.lyric = lyric.strip('"')  # remove quotes if present
    return n

def text_to_musicxml(input_file_path, output_file_path="output.xml"):
    s = stream.Stream()
    with open(input_file_path, 'r') as f:
        for line in f:
            if line.strip() == "":
                continue  # skip empty lines
            musical_element = parse_line(line)
            s.append(musical_element)
    s.write('musicxml', fp=output_file_path)
    print(f"MusicXML saved to: {output_file_path}")

# example input
# 60 1.0 Hello
# 62 0.5 world
# rest 0.5
# 64 1.0 again
text_to_musicxml (sys.argv[1], sys.argv[2])
