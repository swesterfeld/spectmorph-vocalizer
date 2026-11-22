"""Run with: python3 -m unittest discover -s tmp -p test_split.py"""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile as sf

from split import read_labels, split_flac


class SplitTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / "recording.flac"
        self.labels = self.source.with_suffix(".txt")
        self.audio = np.zeros((25600, 2), dtype=np.int16)
        self.audio[800:8000] = [1000, -2000]
        self.audio[16000:24000] = [-3000, 4000]
        sf.write(self.source, self.audio, 8000, subtype="PCM_16")
        self.write_labels([(0, '_'), (.2, 'a'), (.8, '_'),
                           (1.5, '!'), (2.1, 'E'), (2.8, '_')])

    def write_labels(self, rows):
        self.labels.write_text(''.join(f'{t:.6f}\t{t:.6f}\t{label}\n' for t, label in rows))

    def split(self):
        with contextlib.redirect_stdout(io.StringIO()):
            split_flac(self.source)

    def test_audio_and_shifted_labels(self):
        self.split()
        for number, start, end, expected in [
            (1, 800, 8000, [(0, '_'), (.1, 'a'), (.7, '_')]),
            (2, 16000, 24000, [(0, '!'), (.1, 'E'), (.8, '_')]),
        ]:
            output = self.source.parent / f'{number:03d}_split.flac'
            audio, rate = sf.read(output, dtype='int16', always_2d=True)
            self.assertEqual(rate, 8000)
            self.assertEqual(sf.info(output).subtype, 'PCM_16')
            np.testing.assert_array_equal(audio, self.audio[start:end])
            self.assertEqual(read_labels(output.with_suffix('.txt')), expected)

    def test_unsafe_cut_writes_nothing(self):
        self.write_labels([(0, '_'), (.2, 'a'), (1.1, '_')])
        with self.assertRaisesRegex(ValueError, 'Unsafe.*1.000000s'):
            self.split()
        self.assertEqual(list(self.source.parent.glob('*_split.*')), [])

    def test_phone_inside_discarded_gap_writes_nothing(self):
        self.write_labels([(0, '_'), (1.2, 't'), (1.3, '_')])
        with self.assertRaisesRegex(ValueError, 'Discarded silence.*label'):
            self.split()
        self.assertEqual(list(self.source.parent.glob('*_split.*')), [])

    def test_boundary_at_safe_label_start(self):
        self.write_labels([(0, '_'), (.2, 'a'), (1, '_'), (2, '!')])
        self.split()
        self.assertEqual(read_labels(self.source.parent / '002_split.txt'), [(0, '!')])

    def test_reports_all_boundaries_and_discarded_labels(self):
        self.write_labels([(0, 'a'), (1.2, 't'), (1.3, 'k'), (2.5, 'E')])
        with self.assertRaises(ValueError) as caught:
            self.split()
        message = str(caught.exception)
        for time in (.1, 1, 2, 3):
            self.assertIn(f'Unsafe split/trim boundary at {time:.6f}s', message)
        for time, name in [(0, 'a'), (1.2, 't'), (1.3, 'k'), (2.5, 'E')]:
            self.assertIn(f"contains label {name!r} at {time:.6f}s", message)
        self.assertIn('Found 9 splitting validation errors:', message)
        self.assertEqual(list(self.source.parent.glob('*_split.*')), [])

    def test_unlabelled_cut_is_rejected(self):
        self.write_labels([(.2, '_')])
        with self.assertRaisesRegex(ValueError, 'unlabelled'):
            self.split()

    def test_invalid_labels(self):
        for contents in ['0\t1\t_\n', 'nan\tnan\t_\n',
                         '1\t1\t_\n0\t0\t!\n', '']:
            with self.subTest(contents=contents):
                self.labels.write_text(contents)
                with self.assertRaises(ValueError):
                    read_labels(self.labels)

    def test_silent_recording(self):
        sf.write(self.source, np.zeros(8000), 8000)
        self.write_labels([(0, '!')])
        self.split()
        self.assertEqual(list(self.source.parent.glob('*_split.*')), [])


if __name__ == '__main__':
    unittest.main()
