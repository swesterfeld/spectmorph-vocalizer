"""Test accent timing without requiring downloaded voice recordings."""

import ast
from dataclasses import dataclass
from math import cos, pi
from pathlib import Path
from types import SimpleNamespace
import unittest


class AccentTests(unittest.TestCase):
    def setUp(self):
        # phomorphdi is a command-line script with voice-loading side effects.
        source = Path(__file__).resolve().parents[1] / 'phomorphdi.py'
        tree = ast.parse(source.read_text())
        names = {'AccentEnvelope', 'build_accent_envelope', 'find_accent'}
        definitions = [node for node in tree.body
                       if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        self.env = dict(dataclass=dataclass, cos=cos, pi=pi,
                        sfz_nucleus_starts={}, sfz_attack_starts={},
                        volume_closure_times={}, synlist=[])
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), 'exec'), self.env)

    def build(self, entries, accents):
        self.env['pho'] = [[SimpleNamespace(syl_entries=entries)]]
        self.env['accent_dict'] = dict.fromkeys(accents, True)
        self.env['accent_envelope'] = self.env['build_accent_envelope']()
        return self.env['accent_envelope']

    def gain(self, time):
        return self.env['find_accent'](time)

    def assert_continuous(self, times):
        for time in times:
            self.assertAlmostEqual(self.gain(time - 1e-6), self.gain(time + 1e-6), places=5)

    def test_voiced_consonant_peaks_at_nucleus(self):
        self.env['sfz_nucleus_starts'] = {1: 200}
        self.env['sfz_attack_starts'] = {1: 75}
        self.build([(1, 100), (2, 600)], [1])
        self.assertEqual(self.gain(75), 0)
        self.assertLess(self.gain(100), 12)
        self.assertEqual(self.gain(200), 12)
        self.assertEqual(self.gain(600), 0)
        self.assert_continuous([75, 200, 600])

    def test_tied_vowel_keeps_its_own_peak(self):
        self.build([(1, 100), (2, 300), (3, 500)], [1, 2])
        self.assertEqual(self.gain(100), 12)
        self.assertEqual(self.gain(300), 12)
        self.assert_continuous(range(50, 501))
        self.assertTrue(all(0 <= self.gain(t) <= 12 for t in range(550)))

    def test_plosive_jumps_inside_closure_and_holds_until_nucleus(self):
        self.env['volume_closure_times'] = {1: 85}
        self.env['sfz_nucleus_starts'] = {1: 180}
        self.build([(1, 100), (2, 500)], [1])
        self.assertEqual(self.gain(84), 0)
        self.assertEqual(self.gain(85), 12)
        self.assertEqual(self.gain(180), 12)
        self.assert_continuous([180, 500])

    def test_rest_jump_avoids_crossfades(self):
        self.env['synlist'] = [SimpleNamespace(lyric='_', type='M', ms=200),
                               SimpleNamespace(lyric='_a', type='D', ms=100)]
        envelopes = self.build([(1, 300), (2, 700)], [1])
        self.assertTrue(envelopes[0].silent_start)
        self.assertEqual(envelopes[0].start_ms, 100)
        self.assertEqual(self.gain(99), 0)
        self.assertEqual(self.gain(100), 12)
        self.assertEqual(self.gain(300), 12)

    def test_short_rest_and_later_syllables_do_not_allow_jump(self):
        self.env['synlist'] = [SimpleNamespace(lyric='_', type='M', ms=80),
                               SimpleNamespace(lyric='_a', type='D', ms=100)]
        envelopes = self.build([(1, 180), (2, 400)], [1])
        self.assertFalse(envelopes[0].silent_start)
        self.env['synlist'][0].ms = 200
        envelopes = self.build([(1, 500), (2, 700)], [1])
        self.assertFalse(envelopes[0].silent_start)

    def test_no_accent_and_zero_length(self):
        self.build([(1, 100), (2, 300)], [])
        self.assertEqual(self.gain(100), 0)
        self.build([(1, 100), (2, 100)], [1])
        self.assertEqual(self.gain(100), 0)


if __name__ == '__main__':
    unittest.main()
