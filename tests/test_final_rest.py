"""Keep ending rests through phoneme generation and synthesis timing."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FinalRestTests(unittest.TestCase):
    def render(self, rest_durations):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            mxparse = work / 'score.mxparse'
            score = ('TEMPO\nbpm: 120\n\nREST\nstart: 0\nduration: 1\n\n'
                     'NOTE\nlyric: baut\nmidi_note: 52\nstart: 1\nduration: 1\n'
                     'measure: 1\nbeat: 2\nvolume: (0, 80) (1, 80)\nsfz: None\n\n')
            start = 2
            for duration in rest_durations:
                score += f'REST\nstart: {start}\nduration: {duration / 500}\n\n'
                start += duration / 500
            mxparse.write_text(score)
            result = subprocess.run([sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml', str(mxparse)],
                                    capture_output=True, text=True, check=True)
            phones = [line.split() for line in result.stdout.splitlines()
                      if line and not line.startswith(('meta', ';'))]
            self.assertEqual(phones[-1][0], '_')
            expected = 1000 + (sum(rest_durations) if rest_durations else 500)
            self.assertAlmostEqual(sum(float(p[1]) for p in phones), expected, places=2)
            pho = work / 'score.pho'
            pho.write_text(result.stdout)
            voice = work / 'voice/sven'
            voice.mkdir(parents=True)
            for source in (ROOT / 'voice/sven').iterdir():
                if source.suffix in ('.sh', '.txt'):
                    shutil.copyfile(source, voice / source.name)
                if source.suffix == '.txt':
                    end = max(float(line.split()[0]) for line in source.read_text().splitlines() if line.strip())
                    (voice / (source.stem + '.volume')).write_text(f'0 0.5\n{end * 1000 + 1000} 0.5\n')
            items = work / 'items.txt'
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'phomorphdi.py'), str(pho),
                                     '-s', '1', '--items', str(items)], cwd=work,
                                    env={**os.environ, 'VOICE': 'sven'}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            last_item = items.read_text().splitlines()[-1].split()
            self.assertEqual(last_item[2], 'I_')
            self.assertAlmostEqual(float(last_item[1]) * 1000, expected, places=2)

    def test_explicit_final_rests(self):
        for duration in (50, 200, 500):
            with self.subTest(duration=duration):
                self.render([duration])

    def test_consecutive_final_rests(self):
        self.render([200, 300])

    def test_note_ending_gets_release_rest(self):
        self.render([])


if __name__ == '__main__':
    unittest.main()
