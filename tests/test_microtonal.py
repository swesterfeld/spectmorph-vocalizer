"""Cent annotations from MusicXML through synthesis frequency commands."""

import ast
from enum import Enum
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MicrotonalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.work = Path(cls.tmp.name)
        cls.parser = cls.work / 'mxmlparse'
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) +
                       ['-std=c++20', str(ROOT / 'src/mxmlparse.cc'), '-o', str(cls.parser)], check=True)
        names = {'SfzState', 'load_mxparse', 'reconstruct_notes'}
        definitions = [node for node in ast.parse((ROOT / 'xml-to-pho.py').read_text()).body
                       if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
        cls.env = dict(Enum=Enum, re=re)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), 'xml-to-pho.py', 'exec'), cls.env)

    def parse(self, xml):
        self.mxparse = self.work / 'score.mxparse'
        subprocess.run([str(self.parser), str(xml), str(self.mxparse)], check=True, capture_output=True)
        return [n for n in self.env['load_mxparse'](self.mxparse) if n['type'] == 'note']

    def synthetic(self, body):
        xml = self.work / 'synthetic.musicxml'
        xml.write_text('<score-partwise><part id="P1"><measure number="1">'
                       '<attributes><divisions>4</divisions></attributes>' + body +
                       '</measure></part></score-partwise>')
        return xml

    def note(self, alter=0, duration=4):
        return (f'<note><pitch><step>C</step><alter>{alter}</alter><octave>3</octave></pitch>'
                f'<duration>{duration}</duration><lyric><text>la</text></lyric></note>')

    def direction(self, text, offset=0):
        return (f'<direction><direction-type><words>{text}</words></direction-type>'
                f'<offset>{offset}</offset></direction>')

    def test_example_adds_cents_to_quarter_tones_and_does_not_persist(self):
        notes = self.parse(ROOT / 'testxml/mikrotonal-test.musicxml')
        self.assertEqual([n['midi_note'] for n in notes],
                         [48, 52, 55, 43, 48, 48.5, 53.5, 53.5, 42.5, 48])

    def test_offsets_order_accidentals_and_unrelated_text(self):
        xml = self.synthetic(self.direction(' +23.5ct ', 4) + self.note(1) + self.note(-1) +
                             self.direction('-17ct') + self.note(0.5) +
                             self.direction('+99ct extra') + self.note() +
                             self.direction('dolce') + self.note() +
                             self.direction('+0ct') + self.note())
        self.assertEqual([n['midi_note'] for n in self.parse(xml)],
                         [49, 47.235, 48.33, 48, 48, 48])
        # A negative offset can attach text after its target note.
        xml = self.synthetic(self.note(-0.5) + self.direction('-25ct', -4))
        self.assertEqual(self.parse(xml)[0]['midi_note'], 47.25)

    def test_cent_range_includes_both_limits(self):
        xml = self.synthetic(self.direction('-2400ct') + self.note() +
                             self.direction('+2400ct') + self.note())
        self.assertEqual([n['midi_note'] for n in self.parse(xml)], [24, 72])

    def test_out_of_range_cents_are_rejected(self):
        for text in ('-2400.01ct', '+2400.01ct', '-2401ct', '+2401ct',
                     '+' + '9' * 400 + 'ct', '-' + '9' * 400 + 'ct'):
            with self.subTest(text=text):
                xml = self.synthetic(self.note() + self.direction(text, -4))
                result = subprocess.run([str(self.parser), str(xml), str(self.work / 'invalid.mxparse')],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn('cent alteration outside -2400..2400ct range', result.stderr)

    def test_adjustment_survives_tempo_fragments(self):
        xml = self.synthetic(self.direction('+37ct') + self.note(1, 8) +
                             '<sound tempo="90"><offset>-4</offset></sound>')
        notes = self.parse(xml)
        self.assertEqual(len(notes), 2)
        self.assertEqual([n['midi_note'] for n in notes], [49.37, 49.37])
        self.assertEqual(notes[0]['note_id'], notes[1]['note_id'])

    def test_synthesis_uses_adjusted_frequencies(self):
        notes = self.parse(ROOT / 'testxml/mikrotonal-test.musicxml')
        result = subprocess.run([sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml', str(self.mxparse)],
                                check=True, capture_output=True, text=True)
        pho = self.work / 'score.pho'
        pho.write_text(result.stdout)
        # Real labels and constant normalization suffice; no audio downloads.
        voice = self.work / 'voice/sven-test'
        voice.mkdir(parents=True, exist_ok=True)
        for source in (ROOT / 'voice/sven-test').iterdir():
            if source.suffix in ('.sh', '.txt'):
                shutil.copyfile(source, voice / source.name)
            if source.suffix == '.txt':
                end = max(float(line.split()[0]) for line in source.read_text().splitlines() if line.strip())
                (voice / (source.stem + '.volume')).write_text(f'0 0.5\n{end * 1000 + 1000} 0.5\n')
        debug = self.work / 'score.json'
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'phomorphdi.py'), str(pho),
                                 '-s', '1', '--debug', str(debug)], cwd=self.work,
                                env={**os.environ, 'VOICE': 'sven-test'}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        data = json.loads(debug.read_text())
        frequency_column = data['columns'].index('freq')
        commands = [float(line.split()[1]) for line in result.stdout.splitlines() if line.startswith('freq ')]
        for note in notes:
            # Sample in the sustained portion, after the boundary transition.
            sample = round((note['start'] + 0.5) * 1000)
            expected = 440 * 2 ** ((note['midi_note'] - 69) / 12)
            self.assertAlmostEqual(data['samples'][sample][frequency_column], expected, delta=0.006)
            self.assertTrue(any(abs(freq - expected) < 0.006 for freq in commands))


if __name__ == '__main__':
    unittest.main()
