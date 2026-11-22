import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from voice_config import read_voice_config

ROOT = Path(__file__).resolve().parents[1]


class VoiceConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.voice = self.work / 'voice/test'
        self.voice.mkdir(parents=True)

    def model(self, name):
        for suffix in ('.sm', '.txt', '.volume'):
            (self.voice / (name + suffix)).write_text('0 0.5\n1000 0.5\n')

    def group(self, text="VOICE_MIDI_NOTE=50\nVOICE_SEGMENT_GLOB='*_split.sm' # local models\n"):
        (self.voice / 'voice.sh').write_text(text)

    def test_group_inherits_settings_and_loads_volume_data(self):
        self.model('002_split')
        self.model('001_split')
        self.model('voice')
        self.group()
        segments = read_voice_config(self.voice)
        self.assertEqual(list(segments), ['001_split', '002_split'])
        self.assertEqual(segments['001_split']['VOICE_MIDI_NOTE'], '50')
        result = subprocess.run([sys.executable, '-B', '-c',
            "from utils import list_voice_segments, voice_segment_properties, volumes_dict; "
            "assert list_voice_segments() == ['001_split', '002_split']; "
            "assert voice_segment_properties('002_split')['VOICE_MIDI_NOTE'] == '50'; "
            "assert volumes_dict['001_split'] == [(0, .5), (1, .5)]"],
            cwd=self.work, env={**os.environ, 'VOICE': 'test', 'PYTHONPATH': str(ROOT)},
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_and_disabled(self):
        (self.voice / 'one.sh').write_text('VOICE_MIDI_NOTE=40\n')
        self.group('VOICE_DISABLED=1\nVOICE_SEGMENT_GLOB="missing*.sm"\n')
        self.assertEqual(read_voice_config(self.voice), {'one': {'VOICE_MIDI_NOTE': '40'}})

    def test_synthesis_loads_each_model_without_individual_configs(self):
        self.group()
        for name in ('001_split', '002_split'):
            self.model(name)
            (self.voice / (name + '.txt')).write_text(
                (ROOT / 'voice/sven/voice.txt').read_text())
        score = self.work / 'rest.pho'
        mxparse = self.work / 'score.mxparse'
        mxparse.write_text(
            'TEMPO\nbpm: 120\n\nREST\nstart: 0\nduration: 1\n\n'
            'NOTE\nlyric: baut\nmidi_note: 52\nstart: 1\nduration: 1\n'
            'measure: 1\nbeat: 2\nvolume: (0, 80) (1, 80)\nsfz: None\n\n')
        generated = subprocess.run(
            [sys.executable, '-B', str(ROOT / 'xml-to-pho.py'), 'xml', str(mxparse)],
            capture_output=True, text=True, check=True)
        score.write_text(generated.stdout)
        result = subprocess.run(
            [sys.executable, '-B', str(ROOT / 'phomorphdi.py'), str(score)],
            cwd=self.work, env={**os.environ, 'VOICE': 'test'},
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        loads = [line for line in result.stdout.splitlines() if line.startswith('load ')]
        self.assertEqual(loads, ['load "voice/test/001_split.sm"',
                                 'load "voice/test/002_split.sm"'])

    def test_missing_matches(self):
        self.group()
        with self.assertRaisesRegex(ValueError, 'no models match'):
            read_voice_config(self.voice)

    def test_missing_sidecars(self):
        self.group()
        for suffix in ('.txt', '.volume'):
            with self.subTest(suffix=suffix):
                self.model('001_split')
                (self.voice / ('001_split' + suffix)).unlink()
                with self.assertRaisesRegex(ValueError, 'missing.*001_split'):
                    read_voice_config(self.voice)

    def test_duplicate_selection(self):
        self.group()
        self.model('001_split')
        (self.voice / '001_split.sh').write_text('VOICE_MIDI_NOTE=50\n')
        with self.assertRaisesRegex(ValueError, 'selected by both'):
            read_voice_config(self.voice)

    def test_invalid_pattern(self):
        for pattern in ('../*.sm', '*.txt', ''):
            self.group(f'VOICE_SEGMENT_GLOB="{pattern}"\n')
            with self.assertRaisesRegex(ValueError, 'must match .sm filenames'):
                read_voice_config(self.voice)


if __name__ == '__main__':
    unittest.main()
