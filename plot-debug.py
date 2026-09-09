#!/usr/bin/env python3
"""Plot the self-contained debug data written by phomorphdi.py."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


HELP = """examples:
  %(prog)s debug/sfz-schla.json
  %(prog)s debug/sfz-schla.json --curve sfz
  %(prog)s debug/sfz-schla.json --curve freq
  %(prog)s debug/sfz-schla.json --output /tmp/volume.svg
  %(prog)s debug/sfz-schla.json --gnuplot-script /tmp/volume.gp

curves:
  volume      Global gain (volume_midi / 127)^2 * sfz, before per-segment
              normalization and morphing. This is a synthesis control value,
              not measured audio loudness.
  sfz         Sforzando multiplier.
  volume_midi Dynamics envelope in MIDI units.
  freq        Synthesis frequency in Hz.

The x axis uses milliseconds. Vertical lines and labels mark synthesis items
(diphones, inserted vowels and pauses). Samples come directly from the render
loop at its 1 ms output interval.

For interactive plots, use the right mouse button to select a zoom region and
press 'u' to undo zoom. Close the window to exit. SVG files are static.

Rendering with gen-wavs.sh automatically writes debug/<piece>.json. Existing
renders must be regenerated once. For direct phomorphdi.py usage, pass
--debug PATH; its parent directory must already exist. The versioned JSON is
self-contained and can be moved independently of the checkout. Its named
columns and curve metadata allow additional sampled curves without plotter
changes.

Plotting requires Python 3 and gnuplot with a GUI terminal (for example
gnuplot-qt on Debian/Ubuntu). A generated gnuplot script can be run with:
  gnuplot /tmp/volume.gp
"""


def quote(text):
    """Quote a gnuplot string, including SAMPA labels and paths."""
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '') + '"'


def make_plot(data, curve, title, output=None):
    if data['version'] != 1:
        raise ValueError('unsupported debug data version')
    metadata = data['curves'][curve]
    column = data['columns'].index(curve)
    time_column = data['columns'].index('time_ms')
    if not data['samples']:
        raise ValueError('debug data contains no samples')
    lines = []
    if output:
        lines += ['set terminal svg size 1400,600 noenhanced',
                  'set output ' + quote(output)]
    lines += ['set title ' + quote(title) + ' noenhanced',
              'set xlabel "Time (ms)"',
              'set ylabel ' + quote(metadata['label'] + ' (' + metadata['unit'] + ')'),
              'set grid', 'set yrange [0:*]', 'unset key']
    for item in data['items']:
        start, end = float(item['start_ms']), float(item['end_ms'])
        lines += [f'set arrow from {start},graph 0 to {start},graph 1 nohead lc rgb "#bbbbbb"',
                  f'set label {quote(item["label"])} at {(start + end) / 2},graph 0.95 center rotate by 90 noenhanced']
    if data['items']:
        end = float(data['items'][-1]['end_ms'])
        lines += [f'set arrow from {end},graph 0 to {end},graph 1 nohead lc rgb "#bbbbbb"',
                  f'set xrange [0:{end}]']
    lines += ['$curve << EOD']
    for sample in data['samples']:
        lines.append(f'{float(sample[time_column])} {float(sample[column])}')
    lines += ['EOD', 'plot $curve using 1:2 with lines lw 2 notitle']
    if not output:
        # Keep gnuplot alive: a persisted window alone cannot replot for zoom.
        lines += ['set mouse', 'pause mouse close']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('data', type=Path, help='debug/<piece>.json from gen-wavs.sh')
    parser.add_argument('--curve', default='volume', help='Curve name (default: volume)')
    parser.add_argument('--list', action='store_true', help='List available curves')
    parser.add_argument('--output', type=Path, help='Save an SVG instead of opening a window')
    parser.add_argument('--gnuplot-script', type=Path, help='Write a standalone .gp file instead of running gnuplot')
    args = parser.parse_args()
    try:
        data = json.loads(args.data.read_text())
        if args.list:
            for name, metadata in data['curves'].items():
                print(f'{name}: {metadata["label"]} ({metadata["unit"]})')
            return 0
        if args.curve not in data['curves']:
            parser.error('unknown curve; available: ' + ', '.join(data['curves']))
        script = make_plot(data, args.curve, args.data.stem, args.output)
        if args.gnuplot_script:
            args.gnuplot_script.write_text(script)
        else:
            command = ['gnuplot']
            subprocess.run(command, input=script, text=True, check=True)
    except FileNotFoundError as error:
        if error.filename == 'gnuplot':
            print('gnuplot is missing; install gnuplot (with a GUI terminal for interactive plots).', file=sys.stderr)
        else:
            print(error, file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.CalledProcessError) as error:
        print(f'Cannot plot debug data: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
