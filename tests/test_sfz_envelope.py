"""Check sforzando gain and decay without loading voice recordings."""
import ast
from dataclasses import dataclass
from math import cos, pi
from pathlib import Path
from types import SimpleNamespace
import unittest


class SfzTests(unittest.TestCase):
    def test_sffz_has_stronger_peak_and_returns_to_base(self):
        source = Path(__file__).resolve().parents[1] / 'phomorphdi.py'
        names = {'SfzEnvelope', 'build_sfz_envelope', 'find_sfz_factor'}
        definitions = [node for node in ast.parse(source.read_text()).body
                       if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        env = dict(dataclass=dataclass, cos=cos, pi=pi,
                   pho=[[SimpleNamespace(syl_entries=[(1, 100), (2, 800), (3, 1500)])]],
                   sfz_dict={1: 5, 2: 7.5}, sfz_plosive_onsets=set(), synlist=[],
                   sfz_attack_starts={1: 50, 2: 750}, sfz_nucleus_starts={})
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), 'exec'), env)
        env['sfz_envelope'] = env['build_sfz_envelope']()
        gain = lambda t: env['find_sfz_factor'](t, 80)
        self.assertEqual(gain(100), 5)
        self.assertEqual(gain(800), 7.5)
        self.assertGreater(gain(775), gain(75))
        self.assertGreater(gain(1050), gain(350))
        for t in (0, 50, 600, 750, 1300, 1500):
            self.assertEqual(gain(t), 1)
