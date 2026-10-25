"""Alternative transcriptions normalize before phoneme timing is assigned."""

import ast
from pathlib import Path
import re
import unittest


class TranscriptionSubstitutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / 'xml-to-pho.py'
        names = {'check_lyric', 'canonical_v', 'is_syllabic_consonant', 'cvc_split',
                 'search_c', 'c_length', 'diphthong_split'}
        definitions = [node for node in ast.parse(source.read_text()).body
                       if (isinstance(node, ast.FunctionDef) and node.name in names)
                       or (isinstance(node, ast.Assign) and any(
                           isinstance(target, ast.Name) and target.id in {'V', 'C'}
                           for target in node.targets))]
        cls.env = dict(re=re)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), 'exec'), cls.env)

    def test_diphthong_alternatives_preserve_surrounding_consonants(self):
        for lyric, expected in [('baut', (['b'], 'a_U', ['t'])),
                                ('bai', (['b'], 'a_I', [])),
                                ('ba:ut', (['b'], 'a_U', ['t']))]:
            with self.subTest(lyric=lyric):
                self.assertEqual(self.env['cvc_split'](lyric), expected)

    def test_glides_and_chained_substitution(self):
        for lyric, vowel in [('bie', 'e'), ('biE', 'E'), ('bio', 'o'), ('bIo', 'o')]:
            with self.subTest(lyric=lyric):
                onset, nucleus, coda = self.env['cvc_split'](lyric + 't')
                self.assertEqual((onset, nucleus, coda), (['b', 'j'], vowel, ['t']))
                self.assertEqual(self.env['c_length'](onset), 200)
        self.assertEqual(self.env['cvc_split']('Io'), (['j'], 'o', []))

    def test_canonical_and_unrelated_transcriptions_are_unchanged(self):
        for lyric, expected in [('baUt', (['b'], 'a_U', ['t'])),
                                ('baIt', (['b'], 'a_I', ['t'])),
                                ('bi:t', (['b'], 'i', ['t'])),
                                ('bOyt', (['b'], 'O_y', ['t'])),
                                ('m=', ([], 'm=', []))]:
            with self.subTest(lyric=lyric):
                self.assertEqual(self.env['cvc_split'](lyric), expected)


if __name__ == '__main__':
    unittest.main()
