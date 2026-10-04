"""Regression coverage for original notes split by tempo changes."""

import ast
from enum import Enum
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class TempoFragmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((ROOT / 'xml-to-pho.py').read_text())
        names = {'SfzState', 'load_mxparse', 'reconstruct_notes'}
        definitions = [node for node in tree.body
                       if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        cls.env = dict(Enum=Enum, re=re)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), 'xml-to-pho.py', 'exec'), cls.env)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.parser = Path(cls.tmp.name) / 'mxmlparse'
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) +
                       ['-std=c++20', str(ROOT / 'src/mxmlparse.cc'), '-o', str(cls.parser)], check=True)

    def note(self, note_id=1, start=0, duration=1, **kwargs):
        note = dict(type='note', note_id=note_id, start=start, duration=duration,
                    midi_note=60, volume=[(0, 80), (duration, 80)],
                    sfz=self.env['SfzState'].NONE, accent=True)
        note.update(kwargs)
        return note

    def reconstruct(self, score):
        return self.env['reconstruct_notes'](score)

    def test_tempo_and_volume_points_use_each_fragments_tempo(self):
        score = [dict(type='tempo', bpm=60), self.note(lyric='la'),
                 dict(type='tempo', bpm=120), self.note(start=1, volume=[(0, 100), (1, 110)])]
        notes = self.reconstruct(score)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['duration_ms'], 1500)
        self.assertEqual(notes[0]['duration'], 2)
        self.assertEqual(notes[0]['volume_ms'], [(0, 80), (1000, 80), (1000, 100), (1500, 110)])
        self.assertTrue(notes[0]['accent'])

    def test_original_tied_notes_keep_accent_boundaries(self):
        notes = self.reconstruct([self.note(), self.note(note_id=2, start=1),
                                  self.note(note_id=3, start=2, accent=False)])
        self.assertEqual(len(notes), 3)
        self.assertEqual([n['accent'] for n in notes], [True, True, False])

    def test_same_note_id_requires_consistent_pitch(self):
        with self.assertRaisesRegex(AssertionError, 'inconsistent pitch for note_id 1'):
            self.reconstruct([self.note(), self.note(start=1, midi_note=62)])

    def test_same_note_id_requires_contiguous_fragments(self):
        for start in (0.5, 1.5):
            with self.subTest(start=start):
                with self.assertRaisesRegex(AssertionError, 'non-contiguous fragments for note_id 1'):
                    self.reconstruct([self.note(), self.note(start=start)])

    def test_sfz_onset_is_preserved_but_continuations_merge(self):
        sfz = self.env['SfzState']
        notes = self.reconstruct([self.note(), self.note(start=1, sfz=sfz.START),
                                  self.note(start=2, sfz=sfz.CONTINUE)])
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[1]['sfz'], sfz.START)
        self.assertEqual(notes[1]['duration_ms'], 1000)
        self.assertNotIn('accent', notes[1])

    def test_fermata_timing_and_legacy_files(self):
        notes = self.reconstruct([self.note(fermata=True, staccato=True),
                                  self.note(start=1, fermata=True, staccato=True)])
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['duration_ms'], 1750)
        self.assertEqual(notes[0]['volume_ms'][-1][0], 1750)
        self.assertTrue(notes[0]['staccato'])
        legacy = [self.note(), self.note(start=1)]
        for note in legacy:
            del note['note_id']
        self.assertEqual(len(self.reconstruct(legacy)), 2)

    def test_accelerando_musicxml_to_pho(self):
        xml = ROOT / 'testxml/akzent-accel.musicxml'
        expected_accents = len(ET.parse(xml).findall('.//note/notations/articulations/accent'))
        mxparse = Path(self.tmp.name) / 'accel.mxparse'
        subprocess.run([str(self.parser), str(xml), str(mxparse)], stdout=subprocess.DEVNULL, check=True)
        raw = self.env['load_mxparse'](mxparse)
        notes = self.reconstruct(raw)
        original_notes = [n for n in notes if n['type'] == 'note']
        self.assertEqual(len(original_notes), expected_accents)
        self.assertEqual(len({n['note_id'] for n in original_notes}), expected_accents)

        # Independently integrate each parser fragment before reconstruction.
        expected_ms = 0
        bpm = 120
        durations = {}
        for event in raw:
            if event['type'] == 'tempo':
                bpm = event['bpm']
            else:
                duration = event['duration'] * 60000 / bpm
                expected_ms += duration
                if event['type'] == 'note':
                    durations[event['note_id']] = durations.get(event['note_id'], 0) + duration
        self.assertAlmostEqual(sum(n['duration_ms'] for n in notes), expected_ms)
        for note in original_notes:
            self.assertAlmostEqual(note['duration_ms'], durations[note['note_id']])

        result = subprocess.run([sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml', str(mxparse)],
                                capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        self.assertEqual(sum(line.startswith('meta accent ') for line in lines), expected_accents)
        phones = [line.split() for line in lines if line and not line.startswith(('meta', ';'))]
        self.assertEqual(sum(p[0] == 'l' for p in phones), expected_accents)
        self.assertEqual(sum(p[0] == 'a' for p in phones), expected_accents)
        # pho rounds every duration to two decimal places.
        self.assertAlmostEqual(sum(float(p[1]) for p in phones), expected_ms, delta=len(phones) * 0.005)


if __name__ == '__main__':
    unittest.main()
