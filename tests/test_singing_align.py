"""Synthetic regression tests; no model download or singer recording needed."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import importlib.util
import json

import numpy as np

from singing_align import (align_durations, detect_regions, phone_spec,
                           read_items, read_regions, write_labels, main,
                           expand_phones, phase_scores, inter_item_labels)


class SingingAlignmentTests(unittest.TestCase):
    def test_stop_phases_and_unreleased_stop(self):
        for stop in ['p', 'b', 't', 'd', 'k', 'g', '?']:
            phases = expand_phones([stop], {})
            self.assertEqual([p.label for p in phases], ['.' + stop, stop])
            self.assertAlmostEqual(sum(p.seconds for p in phases), .1)
            phases = expand_phones([stop + '_}'], {})
            self.assertEqual([p.label for p in phases], ['.' + stop, stop + '_}'])
            self.assertAlmostEqual(sum(p.seconds for p in phases), .1)
        phases = expand_phones('l I p_} m= S t I f t'.split(), {})
        self.assertEqual([p.label for p in phases],
                         ['l', 'I', '.p', 'p_}', 'm=', 'S', '.t', 't', 'I', 'f', '.t', 't'])
        self.assertEqual([p.label for p in expand_phones(['ts', 'pf'], {})], ['ts', 'pf'])

    def test_diphthong_three_phases_and_short_tail(self):
        for source, expected in [('a_U', ['a', 'aU', 'U']), ('aU', ['a', 'aU', 'U']),
                                 ('a_I', ['a', 'aI', 'I']), ('O_Y', ['O', 'OY', 'Y']),
                                 ('e_6', ['e', 'e6', '6'])]:
            phases = expand_phones([source], {})
            self.assertEqual([p.label for p in phases], expected)
            self.assertEqual([p.nucleus for p in phases], [True, False, False])
            self.assertEqual([p.seconds for p in phases], [1., .1, .1])
            self.assertEqual(align_durations(np.zeros((60, 3)), .02,
                                            [p.nucleus for p in phases],
                                            means=[p.seconds for p in phases]),
                             [(0, 50), (50, 55), (55, 60)])

    def test_energy_distinguishes_closure_from_release(self):
        phases = expand_phones(['t'], {})
        # Low-amplitude closure, loud release. Boundaries follow the signal,
        # not the default 60/40 ms duration split.
        samples = np.r_[np.full(80, .0001), np.full(120, .3)]
        scores = phase_scores(np.zeros((10, 2)), samples, phases)
        spans = align_durations(scores, .02, [False, False],
                                means=[p.seconds for p in phases], duration_weight=.05)
        self.assertEqual(spans, [(0, 4), (4, 10)])

    def test_unreleased_plosion_label_does_not_require_energy_rise(self):
        phases = expand_phones(['p_}'], {})
        emissions = np.zeros((10, 2))
        scores = phase_scores(emissions, np.full(200, .001), phases)
        np.testing.assert_array_equal(scores[:, 1], emissions[:, 1])

    def test_silence_fills_gaps_including_touching_items(self):
        self.assertEqual(inter_item_labels([[(1., 2., 'a')], [(4., 5., 'b')], [(5., 6., 'c')]]),
                         [(1., 2., 'a'), (2., 4., '_'), (4., 5., 'b'),
                          (5., 5., '_'), (5., 6., 'c')])
        with self.assertRaises(ValueError):
            inter_item_labels([[(1., 3., 'a')], [(2., 4., 'b')]])

    def test_list_formats_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'items.txt'
            path.write_text('# comment\nWadenkrampf: v a d n= k r a m pf\n'
                            'Wadenkrampf\tv a d n= k r a m pf\na:\n', encoding='utf-8')
            items = read_items(path)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].name, items[1].name)
        self.assertEqual(items[0].phones[3], 'n=')
        self.assertEqual(items[2].phones, ['a:'])

    def test_explicit_syllabicity_and_unknown_symbols(self):
        for phone in ['n=', 'm_m', 'a:', 'a_I', '@']:
            self.assertTrue(phone_spec(phone, {})[1])
        for phone in ['n', 't_}', 'pf']:
            self.assertFalse(phone_spec(phone, {})[1])
        self.assertEqual(phone_spec('n=', {})[0], ['n̩', 'n'])
        with self.assertRaises(ValueError):
            phone_spec('unrecognised', {})
        self.assertEqual(phone_spec('special', {'special': {'ipa': ['a'], 'nucleus': True}}),
                         (['a'], True))

    def test_pauses_vary_and_short_closure_does_not_split(self):
        levels = np.full(700, -90.)
        levels[50:170] = -20.
        levels[100:110] = -90.  # 100 ms closure inside first item.
        levels[260:380] = -20.
        levels[550:670] = -20.
        regions = detect_regions(levels, .01, 7.)
        np.testing.assert_allclose(regions, [[.46, 1.74], [2.56, 3.84], [5.46, 6.74]])
        self.assertEqual(detect_regions([-90.] * 20, .01, .2), [])

    def test_acoustic_boundaries_override_duration_means(self):
        # Actual durations: 140 ms, 860 ms, 120 ms, 1080 ms.
        boundaries = [0, 7, 50, 56, 110]
        emissions = np.full((110, 4), -15.)
        for phone, (a, b) in enumerate(zip(boundaries, boundaries[1:])):
            emissions[a:b, phone] = 0.
        self.assertEqual(align_durations(emissions, .02, [False, True, False, True]),
                         list(zip(boundaries, boundaries[1:])))

    def test_syllabic_consonant_gets_long_duration_without_acoustic_evidence(self):
        spans = align_durations(np.zeros((110, 4)), .02, [False, True, False, True])
        self.assertEqual(spans, [(0, 5), (5, 55), (55, 60), (60, 110)])

    def test_impossible_duration_and_short_audio_fail(self):
        with self.assertRaises(ValueError):
            align_durations(np.zeros((100, 1)), .02, [False])
        with self.assertRaises(ValueError):
            align_durations(np.zeros((1, 2)), .02, [True, True])

    def test_audacity_round_trip_and_bad_intervals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'labels.txt'
            write_labels(path, [(1., 2., 'Sänger'), (4., 5., 'a')])
            self.assertEqual(read_regions(path, 6.), [(1., 2.), (4., 5.)])
            for invalid in ['nan\t2\tx', '2\t1\tx', '0\t7\tx', '1\t3\tx\n2\t4\ty']:
                path.write_text(invalid)
                with self.assertRaises(ValueError):
                    read_regions(path, 6.)

    @unittest.skipUnless(importlib.util.find_spec('soundfile'), 'soundfile not installed')
    def test_wav_pipeline_and_count_mismatch(self):
        import soundfile as sf
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav, text, prefix = root / 'test.wav', root / 'items.txt', root / 'result'
            rate = 22050  # Exercise resampling too.
            samples = np.zeros(rate * 7, dtype=np.float32)
            for start, end in [(1., 2.2), (4., 5.2)]:
                a, b = round(start * rate), round(end * rate)
                samples[a:b] = .2 * np.sin(2 * np.pi * 220 * np.arange(b - a) / rate)
            # Opposite channel polarity must not cancel the voice.
            sf.write(wav, np.column_stack([samples, -samples]), rate)
            text.write_text('one: t a\ntwo: n= s\n')
            args = [str(wav), str(text), '--output-prefix', str(prefix)]
            self.assertEqual(main(args + ['--segments-only']), 0)
            self.assertEqual(len(read_regions(str(prefix) + '.candidates.txt', 7)), 2)
            with patch('singing_align.AcousticModel') as acoustic:
                acoustic.return_value.token_ids.return_value = [0]
                acoustic.return_value.scores.side_effect = lambda samples, ids: np.zeros((64, len(ids)))
                self.assertEqual(main(args), 0)
            raw = Path(str(prefix) + '.phones.txt').read_text().splitlines()
            self.assertEqual([line.split('\t')[2] for line in raw], ['.t', 't', 'a', '_', 'n=', 's'])
            points = [list(map(float, line.split('\t')[:2])) for line in raw]
            self.assertTrue(all(start == end for start, end in points))
            report = json.loads(Path(str(prefix) + '.report.json').read_text())
            phones = report['phones']
            self.assertGreater(phones[3]['end'] - phones[3]['start'], .8)
            self.assertAlmostEqual(points[3][0], phones[2]['end'], places=6)
            for point, phone in zip(points[:3] + points[4:], phones):
                self.assertAlmostEqual(point[0], phone['start'], places=6)
            self.assertEqual(len(read_regions(str(prefix) + '.items.txt', 7)), 2)
            text.write_text('one: t a\n')
            other = root / 'mismatch'
            with patch('singing_align.AcousticModel') as acoustic:
                self.assertEqual(main([str(wav), str(text), '--output-prefix', str(other)]), 1)
                acoustic.assert_not_called()
            self.assertFalse(Path(str(other) + '.phones.txt').exists())


if __name__ == '__main__':
    unittest.main()
