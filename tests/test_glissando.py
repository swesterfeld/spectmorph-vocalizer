"""Pitch interpolation tests, independent of installed voice models."""

import ast
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import unittest


class GlissandoTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'phomorphdi.py'
        tree = ast.parse(source.read_text())
        names = {'Glissando', 'build_glissandos', 'find_glissando_freq', 'find_freq', 'musical_time'}
        definitions = [n for n in tree.body
                       if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        self.env = dict(dataclass=dataclass, tempo_points=[])
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), 'exec'), self.env)

    def build(self, links, nuclei, synthesis=None, closing=None):
        self.env['glissandos'] = self.env['build_glissandos'](links, nuclei, synthesis or {}, closing or {})

    def frequency(self, ms):
        return self.env['find_glissando_freq'](ms)

    def test_octave_is_linear_in_semitones(self):
        self.build([(1, 2)], {1: (100, 130), 2: (1100, 260)})
        self.assertEqual(self.frequency(100), 130)
        self.assertAlmostEqual(self.frequency(600), 130 * 2 ** 0.5)
        self.assertEqual(self.frequency(1100), 260)
        self.assertIsNone(self.frequency(99))
        self.assertIsNone(self.frequency(1101))

    def test_chained_glides_meet_at_the_nucleus(self):
        self.build([(1, 2), (2, 3)], {1: (100, 196), 2: (1100, 130), 3: (1600, 196)})
        self.assertAlmostEqual(self.frequency(1100), 130)
        self.assertAlmostEqual(self.frequency(1099.999), self.frequency(1100.001), places=3)
        self.assertAlmostEqual(self.frequency(1350), (130 * 196) ** 0.5)

    def test_synthesis_nuclei_override_consonant_timing(self):
        self.build([(1, 2)], {1: (50, 130), 2: (950, 260)}, {1: 100, 2: 1000})
        self.assertIsNone(self.frequency(75))
        self.assertEqual(self.frequency(100), 130)
        self.assertEqual(self.frequency(1000), 260)

    def test_diphthong_closing_component_holds_target_pitch(self):
        self.build([(1, 2)], {1: (100, 130), 2: (1000, 260)}, closing={1: 700})
        self.assertEqual(self.frequency(700), 260)
        self.assertEqual(self.frequency(900), 260)
        self.assertEqual(self.frequency(1000), 260)

    def test_glide_overrides_normal_short_pitch_ramp(self):
        self.build([(1, 2)], {1: (100, 130), 2: (1000, 260)})
        self.env['m_freqs'] = [SimpleNamespace(frequency_hz=130)]
        self.env['frequency_transitions'] = [SimpleNamespace(start_ms=960, end_ms=1000,
                                                            from_hz=130, to_hz=260)]
        self.assertEqual(self.env['find_freq'](0), 130)
        self.assertAlmostEqual(self.env['find_freq'](550), 130 * 2 ** 0.5)
        self.assertEqual(self.env['find_freq'](1100), 260)

    def test_invalid_endpoints_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no nucleus'):
            self.build([(1, 2)], {1: (100, 130)})
        with self.assertRaisesRegex(ValueError, 'no time'):
            self.build([(1, 2)], {1: (100, 130), 2: (100, 260)})

    def test_accelerando_tracks_beats_without_pitch_steps(self):
        self.env['tempo_points'] = [(0, 0), (1000, 1), (1500, 2), (1750, 3)]
        self.build([(1, 2)], {1: (0, 130), 2: (1750, 260)})
        self.assertAlmostEqual(self.frequency(1000), 130 * 2 ** (1 / 3))
        self.assertAlmostEqual(self.frequency(1500), 130 * 2 ** (2 / 3))
        for ms in (1000, 1500):
            self.assertAlmostEqual(self.frequency(ms - 1e-6), self.frequency(ms + 1e-6), places=5)


if __name__ == '__main__':
    unittest.main()
