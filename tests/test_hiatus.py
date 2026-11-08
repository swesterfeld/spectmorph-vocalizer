"""Hiatus duration budgets and pitch ramps across the entire transition."""

import ast
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import unittest


class HiatusTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'phomorphdi.py'
        names = {'is_v', 'is_hiatus', 'allocate_hiatus_time', 'lookup_diphone_entry',
                 'strip_syllabic_postfix', 'diphone_bounds', 'PitchBoundary', 'FrequencySpan',
                 'FrequencyTransition', 'build_frequency_transitions', 'find_freq', 'use_direct_pitch'}
        definitions = [node for node in ast.parse(source.read_text()).body
                       if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
        self.env = dict(dataclass=dataclass, find_glissando_freq=lambda ms: None)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), 'exec'), self.env)

    def phone(self, label, sustain, boundary=100):
        return [label, str(boundary), SimpleNamespace(v_time=sustain)]

    def test_long_hiatus_preserves_total_and_boundary_center(self):
        for left, right in [('e', 'o'), ('i', 'a')]:
            pho = [self.phone(left, 1900), self.phone(right, 1800)]
            extensions = self.env['allocate_hiatus_time'](pho)
            self.assertEqual(extensions, {0: 100})
            self.assertEqual([p[-1].v_time for p in pho], [1850, 1750])
            self.assertEqual(sum(p[-1].v_time for p in pho) + 100 + extensions[0], 3800)
            self.assertEqual(pho[0][-1].v_time + (100 + extensions[0]) / 2, 1950)

    def test_short_and_chained_vowels_keep_nonnegative_sustains(self):
        pho = [self.phone('e', 0, 80), self.phone('o', 20), self.phone('a', 200)]
        extensions = self.env['allocate_hiatus_time'](pho)
        self.assertEqual(extensions, {0: 0, 1: 20})
        self.assertEqual([p[-1].v_time for p in pho], [0, 10, 190])
        self.assertEqual(sum(p[-1].v_time for p in pho) + sum(extensions.values()), 220)

    def test_other_phone_boundaries_do_not_borrow_time(self):
        for label in ('_', 'l', 'm=', 'a_I'):
            pho = [self.phone('e', 1900), self.phone(label, 1800)]
            self.assertEqual(self.env['allocate_hiatus_time'](pho), {})
            self.assertEqual([p[-1].v_time for p in pho], [1900, 1800])

    def test_explicit_labels_override_unannotated_recordings(self):
        lines = [(0, '_'), (1, 'e'), (2, 'eo'), (2.16, 'o'), (3, '_')]
        self.env['lines_dict'] = {
            'old': SimpleNamespace(lines=[(0, 'e'), (1, 'o'), (2, '_')]),
            'new': SimpleNamespace(lines=lines)}
        self.env['find_volume_normalization'] = lambda *args: 0.5
        matches = self.env['lookup_diphone_entry']('e', 'o', None)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], 'new')
        self.assertEqual(self.env['diphone_bounds']('e', 'o', matches[0][2:]), (2, 2.16))

    def test_recorded_duration_preserved_and_short_notes_compress(self):
        for target in (164.838, 135.919, 60):
            with self.subTest(target=target):
                pho = [self.phone('e', 1900), self.phone('o', 1800)]
                extension = self.env['allocate_hiatus_time'](pho, {0: target})[0]
                self.assertAlmostEqual(100 + extension, target)
                self.assertAlmostEqual(sum(p[-1].v_time for p in pho) + 100 + extension, 3800)
                self.assertAlmostEqual(pho[0][-1].v_time + (100 + extension) / 2, 1950)
        pho = [self.phone('i', 0, 40), self.phone('a', 0, 40)]
        extension = self.env['allocate_hiatus_time'](pho, {0: 135.919})[0]
        self.assertEqual(40 + extension, 40)
        self.assertEqual([p[-1].v_time for p in pho], [0, 0])

    def test_pitch_fills_hiatus_in_both_directions(self):
        for old_hz, new_hz in [(260, 196), (146, 196)]:
            self.env['m_freqs'] = [self.env['FrequencySpan'](4500, old_hz),
                                   self.env['FrequencySpan'](2000, new_hz)]
            self.env['pitch_boundaries'] = {
                1: self.env['PitchBoundary'](4600, False, 200)}
            self.env['frequency_transitions'] = self.env['build_frequency_transitions']()
            freq = self.env['find_freq']
            self.assertEqual(freq(4400), old_hz)
            self.assertAlmostEqual(freq(4500), (old_hz + new_hz) / 2)
            self.assertEqual(freq(4600), new_hz)
            self.assertNotEqual(freq(4450), old_hz)
            self.assertNotEqual(freq(4550), new_hz)

    def test_hiatus_bypasses_renderer_smoothing_including_endpoint_blocks(self):
        self.env['pitch_boundaries'] = {
            1: self.env['PitchBoundary'](4582.419, False, 164.838),
            2: self.env['PitchBoundary'](5000, False)}
        direct = self.env['use_direct_pitch']
        self.assertFalse(direct(4416, 4417))
        for ms in (4417, 4418, 4500, 4581, 4582):
            self.assertTrue(direct(ms, ms + 1))
        self.assertFalse(direct(4583, 4584))
        self.assertFalse(direct(4999, 5000))
        self.env['find_glissando_freq'] = lambda ms: 130 if ms == 6000 else None
        self.assertTrue(direct(5999, 6000))

    def test_consonants_and_plosives_keep_existing_ramps(self):
        self.env['m_freqs'] = [self.env['FrequencySpan'](500, 130),
                               self.env['FrequencySpan'](500, 196)]
        for plosive, expected in [(False, 40), (True, 0)]:
            self.env['pitch_boundaries'] = {1: self.env['PitchBoundary'](550, plosive)}
            ramp, = self.env['build_frequency_transitions']()
            self.assertEqual(ramp.end_ms - ramp.start_ms, expected)


if __name__ == '__main__':
    unittest.main()
