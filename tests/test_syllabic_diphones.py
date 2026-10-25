"""Diphone extraction from sustained syllabic consonant recordings."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class SyllabicDiphoneTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'phomorphdi.py'
        names = {'is_v', 'is_non_released', 'phone_class', 'diphone_bounds',
                 'strip_syllabic_postfix', 'lookup_diphone_entry',
                 'find_volume_normalization'}
        definitions = [node for node in ast.parse(source.read_text()).body
                       if isinstance(node, ast.FunctionDef) and node.name in names]
        self.env = dict(errors=[], args=SimpleNamespace(pho='test.pho'),
                        volume_factor=lambda *args: 0.5,
                        volume_factor_syllabic=lambda *args: 0.25)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), 'exec'), self.env)

    def test_syllabic_recordings_supply_consonant_diphones(self):
        for phone in ('m', 'n', 'l'):
            with self.subTest(phone=phone):
                lines = [(0, '_'), (1, phone + '='), (2, 'S'), (2.2, '_')]
                self.env['lines_dict'] = {'test': SimpleNamespace(lines=lines)}
                matches = self.env['lookup_diphone_entry'](phone, 'S', None)
                self.assertEqual(matches, [['test', 0.25] + lines[1:]])
                start, end = self.env['diphone_bounds'](phone, 'S', matches[0][2:])
                self.assertAlmostEqual(start, 1.85)
                self.assertAlmostEqual(end, 2.1)
                incoming = self.env['lookup_diphone_entry']('_', phone, None)
                start, end = self.env['diphone_bounds']('_', phone, incoming[0][2:])
                self.assertAlmostEqual(end, 1.15)

    def test_short_syllabic_recordings_use_midpoint(self):
        bounds = self.env['diphone_bounds']
        self.assertEqual(bounds('m', 'S', [(0, 'm='), (0.2, 'S'), (0.4, '_')])[0], 0.1)
        self.assertAlmostEqual(bounds('S', 'm', [(0, 'S'), (0.2, 'm='), (0.4, '_')])[1], 0.3)

    def test_ordinary_consonants_keep_midpoint(self):
        start, end = self.env['diphone_bounds']('m', 'S', [(0, 'm'), (1, 'S'), (2, '_')])
        self.assertEqual((start, end), (0.5, 1.5))

    def test_vowels_remain_limited(self):
        self.assertEqual(self.env['diphone_bounds']('a', 'i', [(0, 'a'), (1, 'i'), (2, '_')]), (0.85, 1.15))


if __name__ == '__main__':
    unittest.main()
