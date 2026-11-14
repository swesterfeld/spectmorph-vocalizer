"""Regression coverage for original notes split by tempo changes."""

import ast
import json
from math import log2
from enum import Enum
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class TempoFragmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((ROOT / 'xml-to-pho.py').read_text())
        names = {'SfzState', 'load_mxparse', 'reconstruct_notes'}
        definitions = [node for node in tree.body
                       if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        cls.env = dict(Enum=Enum, re=re)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), 'xml-to-pho.py', 'exec'), cls.env)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.parser = Path(cls.tmp.name) / 'mxmlparse'
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) +
                       ['-std=c++20', str(ROOT / 'src/mxmlparse.cc'), '-o', str(cls.parser)], check=True)

    def note(self, note_id=1, start=0, duration=1, **kwargs):
        note = dict(type='note', note_id=note_id, start=start, duration=duration,
                    midi_note=60, volume=[(0, 80), (duration, 80)],
                    sfz=self.env['SfzState'].NONE, accent=True)
        note.update(kwargs)
        return note

    def reconstruct(self, score):
        return self.env['reconstruct_notes'](score)

    def test_tempo_and_volume_points_use_each_fragments_tempo(self):
        score = [dict(type='tempo', bpm=60), self.note(lyric='la'),
                 dict(type='tempo', bpm=120), self.note(start=1, volume=[(0, 100), (1, 110)])]
        notes = self.reconstruct(score)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['duration_ms'], 1500)
        self.assertEqual(notes[0]['duration'], 2)
        self.assertEqual(notes[0]['beat_time_ms'], [(0, 0), (1000, 1), (1500, 2)])
        self.assertEqual(notes[0]['volume_ms'], [(0, 80), (1000, 80), (1000, 100), (1500, 110)])
        self.assertTrue(notes[0]['accent'])

    def test_original_tied_notes_keep_accent_boundaries(self):
        notes = self.reconstruct([self.note(), self.note(note_id=2, start=1),
                                  self.note(note_id=3, start=2, accent=False)])
        self.assertEqual(len(notes), 3)
        self.assertEqual([n['accent'] for n in notes], [True, True, False])

    def test_same_note_id_requires_consistent_pitch(self):
        with self.assertRaisesRegex(AssertionError, 'inconsistent pitch for note_id 1'):
            self.reconstruct([self.note(), self.note(start=1, midi_note=62)])

    def test_same_note_id_requires_contiguous_fragments(self):
        for start in (0.5, 1.5):
            with self.subTest(start=start):
                with self.assertRaisesRegex(AssertionError, 'non-contiguous fragments for note_id 1'):
                    self.reconstruct([self.note(), self.note(start=start)])

    def test_sfz_onset_is_preserved_but_continuations_merge(self):
        sfz = self.env['SfzState']
        notes = self.reconstruct([self.note(), self.note(start=1, sfz=sfz.START),
                                  self.note(start=2, sfz=sfz.CONTINUE)])
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[1]['sfz'], sfz.START)
        self.assertEqual(notes[1]['duration_ms'], 1000)
        self.assertNotIn('accent', notes[1])

    def test_fermata_timing_and_legacy_files(self):
        notes = self.reconstruct([self.note(fermata=True, staccato=True),
                                  self.note(start=1, fermata=True, staccato=True)])
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['duration_ms'], 1750)
        self.assertEqual(notes[0]['volume_ms'][-1][0], 1750)
        self.assertTrue(notes[0]['staccato'])
        legacy = [self.note(), self.note(start=1)]
        for note in legacy:
            del note['note_id']
        self.assertEqual(len(self.reconstruct(legacy)), 2)

    def test_missing_lyric_reports_bar_and_beat(self):
        mxparse = Path(self.tmp.name) / 'missing-lyric.mxparse'
        mxparse.write_text('REST\nstart: 0\nduration: 1\n\n'
                          'NOTE\nmidi_note: 63\nstart: 1\nduration: 1\n'
                          'measure: 3\nbeat: 3\nvolume: (0, 80) (1, 80)\nsfz: None\n')
        result = subprocess.run([sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml', str(mxparse)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip(), 'no lyric, note at bar 3 beat 3')

    def test_glissando_preserves_lyric_after_extension(self):
        mxparse = Path(self.tmp.name) / 'glissando.mxparse'
        subprocess.run([str(self.parser), str(ROOT / 'testxml/glissando-test.xml'), str(mxparse)],
                       stdout=subprocess.DEVNULL, check=True)
        notes = self.env['load_mxparse'](mxparse)
        note = next(n for n in notes if n.get('measure') == 3 and n.get('beat') == 3)
        self.assertEqual(note['lyric'], 'vi:')
        result = subprocess.run([sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml', str(mxparse)],
                                capture_output=True, text=True, check=True)
        phones = [line.split() for line in result.stdout.splitlines()
                  if line and not line.startswith(('meta', ';'))]
        self.assertTrue(any(a[0] == 'v' and b[0] == 'i' and a[-1] == b[-1]
                            for a, b in zip(phones, phones[1:])))

    def test_invalid_phoneme_reports_bar_and_beat(self):
        mxparse = Path(self.tmp.name) / 'invalid-lyric.mxparse'
        mxparse.write_text('NOTE\nlyric: q\nmidi_note: 60\nstart: 0\nduration: 1\n'
                          'measure: 7\nbeat: 2\nvolume: (0, 80) (1, 80)\nsfz: None\n')
        result = subprocess.run([sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml', str(mxparse)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip(), 'phoneme missing: q, note at bar 7 beat 2')

    def parse_glissando(self, xml):
        mxparse = Path(self.tmp.name) / 'glissando-markers.mxparse'
        subprocess.run([str(self.parser), str(xml), str(mxparse)],
                       stdout=subprocess.DEVNULL, check=True)
        return [n for n in self.env['load_mxparse'](mxparse) if n['type'] == 'note']

    def test_sffz_survives_musicxml_to_pho(self):
        tree = ET.parse(ROOT / 'testxml/glissando-test.musicxml')
        measure = tree.find('.//measure')
        note = measure.find('note')
        for marking in ('sfz', 'sffz'):
            with self.subTest(marking=marking):
                direction = ET.Element('direction')
                dynamics = ET.SubElement(ET.SubElement(direction, 'direction-type'), 'dynamics')
                ET.SubElement(dynamics, marking)
                measure.insert(list(measure).index(note), direction)
                xml = Path(self.tmp.name) / 'sforzando.musicxml'
                tree.write(xml)
                notes = self.parse_glissando(xml)
                self.assertEqual(notes[0].get('sffz', False), marking == 'sffz')
                result = subprocess.run(
                    [sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml',
                     str(Path(self.tmp.name) / 'glissando-markers.mxparse')],
                    capture_output=True, text=True, check=True)
                markers = [line.split()[1] for line in result.stdout.splitlines()
                           if line.startswith(('meta sfz ', 'meta sffz '))]
                self.assertEqual(markers, [marking])
                measure.remove(direction)

    def test_glissando_start_stop_and_chained_slides(self):
        notes = self.parse_glissando(ROOT / 'testxml/glissando-test.musicxml')
        self.assertEqual([(n.get('glissando_start'), n.get('glissando_stop')) for n in notes],
                         [([1], None), (None, [1]), ([1], None), ([1], [1]), (None, [1])])

    def test_glissando_elements_and_multiple_notations(self):
        tree = ET.parse(ROOT / 'testxml/glissando-test.musicxml')
        for slide in tree.findall('.//slide'):
            slide.tag = 'glissando'
            slide.attrib.pop('number')  # Omitted numbers default to 1.
        for note in tree.findall('.//note'):
            notations = note.find('notations')
            if notations is not None:
                # Ensure the parser does not inspect only the first block.
                note.insert(list(note).index(notations), ET.Element('notations'))
        xml = Path(self.tmp.name) / 'glissando-elements.musicxml'
        tree.write(xml)
        notes = self.parse_glissando(xml)
        self.assertEqual([(n.get('glissando_start'), n.get('glissando_stop')) for n in notes],
                         [([1], None), (None, [1]), ([1], None), ([1], [1]), (None, [1])])

    def test_tempo_split_does_not_duplicate_glissando_endpoints(self):
        tree = ET.parse(ROOT / 'testxml/glissando-test.musicxml')
        measure = tree.find('.//measure')
        sound = ET.Element('sound', tempo='90')
        ET.SubElement(sound, 'offset').text = '-4'
        measure.insert(list(measure).index(measure.find('forward')) + 1, sound)
        xml = Path(self.tmp.name) / 'glissando-tempo.musicxml'
        tree.write(xml)
        notes = self.parse_glissando(xml)
        self.assertEqual(notes[0]['note_id'], notes[1]['note_id'])
        self.assertEqual(notes[0]['glissando_start'], [1])
        self.assertNotIn('glissando_start', notes[1])
        self.assertEqual(sum('glissando_start' in n for n in notes), 3)
        self.assertEqual(sum('glissando_stop' in n for n in notes), 3)

    def render_glissando_script(self, xml, expected_links):
        self.parse_glissando(xml)
        mxparse = Path(self.tmp.name) / 'glissando-markers.mxparse'
        result = subprocess.run([sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml', str(mxparse)],
                                capture_output=True, text=True, check=True)
        links = [line for line in result.stdout.splitlines() if line.startswith('meta glissando ')]
        self.assertEqual(len(links), expected_links)
        pho = Path(self.tmp.name) / 'glissando.pho'
        pho.write_text(result.stdout)
        # Script generation needs labels and normalization values, not audio.
        # Use real labels with constant test volumes; never modify user voices.
        voice = Path(self.tmp.name) / 'voice/sven'
        voice.mkdir(parents=True, exist_ok=True)
        for source in (ROOT / 'voice/sven').iterdir():
            if source.suffix in ('.sh', '.txt'):
                shutil.copyfile(source, voice / source.name)
            if source.suffix == '.txt':
                times = [float(line.split()[0]) for line in source.read_text().splitlines() if line.strip()]
                (voice / (source.stem + '.volume')).write_text(f'0 0.5\n{max(times) * 1000 + 1000} 0.5\n')
        debug = Path(self.tmp.name) / 'glissando.json'
        rendered = subprocess.run([sys.executable, '-B', str(ROOT / 'phomorphdi.py'), str(pho),
                                   '-s', '1', '--debug', str(debug)], cwd=self.tmp.name,
                                  env={**os.environ, 'VOICE': 'sven'}, capture_output=True, text=True)
        self.assertEqual(rendered.returncode, 0, rendered.stderr[-3000:])
        self.assertIn('freq-glissando ', rendered.stdout)
        data = json.loads(debug.read_text())
        frequency_column = data['columns'].index('freq')
        return [row[frequency_column] for row in data['samples']]

    def test_glissando_pipeline_generates_sampled_pitch(self):
        frequencies = self.render_glissando_script(ROOT / 'testxml/glissando-test.musicxml', 3)
        # The nucleus follows the incoming ta diphone, 50 ms after the beat.
        # The destination is a merged vowel, so its nucleus stays on the beat.
        self.assertAlmostEqual(frequencies[2050], 130.81, places=2)
        self.assertAlmostEqual(frequencies[2525], (130.81 * 261.63) ** 0.5, places=2)
        self.assertAlmostEqual(frequencies[3000], 261.63, places=2)
        self.assertAlmostEqual(frequencies[4050], 196, places=2)
        self.assertAlmostEqual(frequencies[4525], (196 * 130.81) ** 0.5, places=2)
        self.assertAlmostEqual(frequencies[5000], 130.81, places=2)
        self.assertAlmostEqual(frequencies[5250], (130.81 * 196) ** 0.5, places=2)
        self.assertAlmostEqual(frequencies[5500], 196, places=2)

    def test_advanced_glissando_follows_accelerando(self):
        frequencies = self.render_glissando_script(ROOT / 'testxml/gliss-test-advanced.musicxml', 4)
        # A tied note postpones the first glide until beat 3.
        self.assertAlmostEqual(frequencies[2500], 130.81, places=2)
        self.assertAlmostEqual(frequencies[3500], (130.81 * 261.63) ** 0.5, places=2)
        # Bar 3 starts at 6000 ms, with its nucleus at 6050 ms (0.025 beats).
        # The first tempo change is 1.25 beats into this four-beat glissando.
        self.assertAlmostEqual(frequencies[8500], 196 * (130.81 / 196) ** (1.225 / 3.975), places=2)
        self.assertAlmostEqual(frequencies[10375], 130.81, places=2)
        cents = [1200 * log2(f) for f in frequencies[6100:10375]]
        steps = [b - a for a, b in zip(cents, cents[1:])]
        self.assertTrue(all(-1 < step < 0 for step in steps))
        self.assertGreater(abs(steps[-100]), 4 * abs(steps[100]))

    def parse_tempo_fixture(self, directions):
        xml = Path(self.tmp.name) / 'tempo-target.musicxml'
        xml.write_text('<score-partwise><part id="P1"><measure number="1">'
                       '<attributes><divisions>4</divisions></attributes>' + directions +
                       '<note><pitch><step>C</step><octave>4</octave></pitch>'
                       '<duration>20</duration><lyric><text>la</text></lyric></note>'
                       '</measure></part></score-partwise>')
        output = Path(self.tmp.name) / 'tempo-target.mxparse'
        subprocess.run([str(self.parser), str(xml), str(output)],
                       stdout=subprocess.DEVNULL, check=True)
        bpm = 120
        result = {}
        for event in self.env['load_mxparse'](output):
            if event['type'] == 'tempo':
                bpm = event['bpm']
            elif event['type'] == 'note':
                result[event['start']] = bpm
        return result

    def tempo_mark(self, bpm, offset=0, unit='quarter', dots=0):
        return (f'<direction><direction-type><metronome><beat-unit>{unit}</beat-unit>'
                + '<beat-unit-dot/>' * dots +
                f'<per-minute>{bpm}</per-minute></metronome></direction-type>'
                f'<offset>{offset}</offset></direction>')

    def test_ramps_target_next_printed_tempo(self):
        for word, start, target, exported in [('accel.', 60, 120, 240),
                                               ('ritardando', 120, 60, 30)]:
            with self.subTest(word=word):
                result = self.parse_tempo_fixture(
                    f'<sound tempo="{start}"/>' + self.tempo_mark(start) +
                    f'<direction><direction-type><words>{word}</words></direction-type>'
                    '<direction-type><dashes type="start" number="1"/></direction-type>'
                    '<offset>4</offset></direction>' +
                    '<direction><direction-type><dashes type="stop" number="1"/></direction-type>'
                    '<offset>16</offset></direction>' +
                    f'<sound tempo="{exported}"><offset>8</offset></sound>' +
                    f'<sound tempo="{exported}"><offset>12</offset></sound>' +
                    self.tempo_mark(target, 16))
                self.assertEqual(result[0], start)
                self.assertEqual(result[1], start)
                self.assertAlmostEqual(result[2], start + (target - start) / 3, places=5)
                self.assertAlmostEqual(result[3], start + 2 * (target - start) / 3, places=5)
                self.assertEqual(result[4], target)

    def test_dorico_ramp_uses_default_before_later_written_tempo(self):
        for word, start, samples, target in [('accel.', 60, [80, 100], 180),
                                             ('rit.', 120, [100, 80], 60)]:
            with self.subTest(word=word):
                result = self.parse_tempo_fixture(
                    f'<sound tempo="{start}"/>' + self.tempo_mark(start) +
                    f'<direction><direction-type><words>{word}</words></direction-type></direction>' +
                    f'<sound tempo="{samples[0]}"><offset>4</offset></sound>' +
                    f'<sound tempo="{samples[1]}"><offset>8</offset></sound>' +
                    self.tempo_mark(target, 16))
                self.assertEqual(result[0], start)
                end_tempo = start * (1.25 if word == 'accel.' else 0.75)
                self.assertEqual(result[1], (start + end_tempo) / 2)
                self.assertEqual(result[2], end_tempo)
                self.assertEqual(result[4], target)

    def test_dashes_determine_ramp_length_and_hold_target(self):
        for word, start, target in [('accel.', 60, 180), ('rit.', 120, 60)]:
            with self.subTest(word=word):
                result = self.parse_tempo_fixture(
                    self.tempo_mark(start) +
                    f'<direction><direction-type><words>{word}</words></direction-type>'
                    '<direction-type><dashes type="start" number="2"/></direction-type>'
                    '<offset>4</offset></direction>'
                    '<direction><direction-type><dashes type="stop" number="1"/></direction-type>'
                    '<offset>8</offset></direction>'
                    '<direction><direction-type><dashes type="continue" number="2"/></direction-type>'
                    '<offset>8</offset></direction>'
                    '<direction><direction-type><dashes type="stop" number="2"/></direction-type>'
                    '<offset>12</offset></direction>' + self.tempo_mark(target, 16))
                self.assertEqual(result[0], start)
                self.assertEqual(result[1], start)
                end_tempo = start * (1.25 if word == 'accel.' else 0.75)
                self.assertEqual(result[2], (start + end_tempo) / 2)
                self.assertEqual(result[3], end_tempo)
                self.assertEqual(result[4], target)

    def test_non_tempo_dashes_do_not_override_tempo_span(self):
        # Both instructions start at the same beat; the crescendo stops later.
        # Also cover dash elements preceding the tempo text in their direction.
        for dash_first in (False, True):
            with self.subTest(dash_first=dash_first):
                words = '<direction-type><words>accel.</words></direction-type>'
                dash = '<direction-type><dashes type="start" number="1"/></direction-type>'
                result = self.parse_tempo_fixture(
                    self.tempo_mark(120) + '<direction>' +
                    (dash + words if dash_first else words + dash) + '</direction>'
                    '<direction><direction-type><words>cresc.</words></direction-type>'
                    '<direction-type><dashes type="start" number="2"/></direction-type></direction>'
                    '<direction><direction-type><dashes type="stop" number="1"/></direction-type>'
                    '<offset>8</offset></direction>'
                    '<direction><direction-type><dashes type="stop" number="2"/></direction-type>'
                    '<offset>12</offset></direction>' + self.tempo_mark(180, 16))
                self.assertEqual(result[1], 135)
                self.assertEqual(result[2], 150)
                self.assertNotIn(3, result)
                self.assertEqual(result[4], 180)

    def test_dashes_without_following_tempo_use_percentage_target(self):
        for word, target in [('accel.', 150), ('rit.', 90)]:
            with self.subTest(word=word):
                result = self.parse_tempo_fixture(
                    self.tempo_mark(120) +
                    f'<direction><direction-type><words>{word}</words></direction-type>'
                    '<direction-type><dashes type="start"/></direction-type></direction>'
                    '<direction><direction-type><dashes type="stop"/></direction-type>'
                    '<offset>12</offset></direction>')
                self.assertEqual(result[0], 120)
                self.assertEqual(result[1.5], (120 + target) / 2)
                self.assertEqual(result[3], target)

    def test_tempo_equivalence_supplies_ramp_target(self):
        for nested in (False, True):
            for ramp_end in (12, 16):
                with self.subTest(nested=nested, ramp_end=ramp_end):
                    sound = '<sound tempo="300"/>'
                    equivalence = (
                        '<direction><direction-type><metronome>'
                        '<beat-unit>quarter</beat-unit><beat-unit>half</beat-unit>'
                        '</metronome></direction-type><offset>16</offset>' +
                        (sound if nested else '') + '</direction>')
                    # Standalone sound comes after the equivalence on purpose.
                    if not nested:
                        equivalence += '<sound tempo="300"><offset>16</offset></sound>'
                    result = self.parse_tempo_fixture(
                        '<sound tempo="120"/>' + self.tempo_mark(120) +
                        '<direction><direction-type><words>accel.</words></direction-type>'
                        '<direction-type><dashes type="start"/></direction-type></direction>'
                        '<direction><direction-type><dashes type="stop"/></direction-type>' +
                        f'<offset>{ramp_end}</offset></direction>' + equivalence)
                    self.assertEqual(result[4], 300)
                    if ramp_end == 12:
                        self.assertEqual(result[1.5], 210)
                        self.assertEqual(result[3], 300)
                    else:
                        self.assertEqual(result[2], 210)

    def test_dorico_equivalence_after_sampled_ramp(self):
        # Like accel-tempogleichung.musicxml: the last ramp sample precedes
        # the equivalence by twice the sampling interval.
        result = self.parse_tempo_fixture(
            '<sound tempo="120"/>' + self.tempo_mark(120) +
            '<direction><direction-type><words>molto accel.</words></direction-type></direction>' +
            ''.join(f'<sound tempo="{120 + i * 5}"><offset>{i * 2}</offset></sound>'
                    for i in range(1, 7)) +
            '<sound tempo="300"><offset>16</offset></sound>'
            '<direction><direction-type><metronome><beat-unit>quarter</beat-unit>'
            '<beat-unit>half</beat-unit></metronome></direction-type>'
            '<offset>16</offset></direction>')
        self.assertEqual(result[1.5], 210)
        self.assertEqual(result[3], 300)
        self.assertEqual(result[4], 300)

    def test_a_tempo_restores_tempo_after_ramp(self):
        for word, endpoint in [('accel.', 150), ('rit.', 90)]:
            for with_sound in (False, True):
                for return_offset in (12, 16):
                    with self.subTest(word=word, with_sound=with_sound, return_offset=return_offset):
                        result = self.parse_tempo_fixture(
                            '<sound tempo="120"/>' + self.tempo_mark(120) +
                            f'<direction><direction-type><words>{word}</words></direction-type>'
                            '<direction-type><dashes type="start"/></direction-type></direction>'
                            '<direction><direction-type><dashes type="stop"/></direction-type>'
                            '<offset>12</offset></direction>'
                            '<direction><direction-type><words> A tempo </words></direction-type>' +
                            f'<offset>{return_offset}</offset>' +
                            ('<sound tempo="120"/>' if with_sound else '') + '</direction>')
                        self.assertEqual(result[1.5], (120 + endpoint) / 2)
                        self.assertEqual(result[return_offset / 4], 120)
                        if return_offset == 16:
                            self.assertEqual(result[3], endpoint)

    def test_dorico_a_tempo_is_not_overwritten_by_ramp_hold(self):
        result = self.parse_tempo_fixture(
            '<sound tempo="120"/>' + self.tempo_mark(120) +
            '<direction><direction-type><words>accel.</words></direction-type></direction>' +
            ''.join(f'<sound tempo="{120 + i * 5}"><offset>{i * 2}</offset></sound>'
                    for i in range(1, 7)) +
            '<sound tempo="120"><offset>16</offset></sound>'
            '<direction><direction-type><words>a tempo</words></direction-type>'
            '<offset>16</offset></direction>')
        self.assertEqual(result[1.5], 135)
        self.assertEqual(result[3], 150)
        self.assertEqual(result[4], 120)

    def test_tempo_change_classifier(self):
        # Include the parser in one translation unit to exercise the classifier
        # directly: integration alone cannot distinguish RIT from ACCEL.
        source = Path(self.tmp.name) / 'tempo-classifier.cc'
        source.write_text(
            '#define main mxmlparse_main\n'
            f'#include "{ROOT / "src/mxmlparse.cc"}"\n'
            '#undef main\n'
            'int main(int argc, char **argv) {\n'
            '  for (int i = 1; i < argc; ++i) {\n'
            '    switch (parse_tempo_change(argv[i])) {\n'
            '      case TempoChange::RIT: std::cout << "RIT\\n"; break;\n'
            '      case TempoChange::ACCEL: std::cout << "ACCEL\\n"; break;\n'
            '      case TempoChange::NONE: std::cout << "NONE\\n"; break;\n'
            '    }\n  }\n}\n')
        executable = Path(self.tmp.name) / 'tempo-classifier'
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) +
                       ['-std=c++20', str(source), '-o', str(executable)], check=True)
        groups = {
            'RIT': ['ritardando', 'rit', 'rit.', 'ritard.', 'rallentando', 'rall.', ' RIT. ',
                    'foo rit', 'rit me', 'rit .', 'rit poco', 'poco meno rit.',
                    'unknown\tritardando\nwords', 'rit. accel.', 'ritenuto'],
            'ACCEL': ['accelerando', 'accelerando.', 'accel', 'accel.', ' ACCEL. ',
                      'foo accel. bar', 'accel. rit.'],
            'NONE': ['', '   ', '.', 'rit?', 'rit/x', 'rit..', 'ritardandos', 'foo bar'],
        }
        for modifier in ('poco', 'molto', 'meno'):
            groups['RIT'].extend([f'{modifier} rit.', f' {modifier.upper()}  ritardando ',
                                  f'{modifier}. rit', f'rit {modifier}', f'{modifier} rit me'])
            groups['ACCEL'].extend([f'{modifier} accel.', f'{modifier}\taccelerando'])
            groups['NONE'].extend([modifier, f'{modifier}rit', f'{modifier} rit?'])
        cases = [(text, expected) for expected, texts in groups.items() for text in texts]
        result = subprocess.run([str(executable)] + [text for text, _ in cases],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.splitlines(), [expected for _, expected in cases])

    def test_ramp_instruction_matches_known_words(self):
        accepted = ['rit', 'rit.', 'ritard', 'ritardando', 'rall.',
                    'rallentando', 'accel', 'accelerando.', '  RIT.  ',
                    'poco accel.', 'molto rit.', 'meno accelerando',
                    'foo rit', 'rit me', 'rit poco']
        rejected = ['rit?', 'rit/x', 'rit..', 'ritardandos', 'accelerated']
        for word in accepted + rejected:
            with self.subTest(word=word):
                result = self.parse_tempo_fixture(
                    '<sound tempo="120"/>' + self.tempo_mark(120) +
                    f'<direction><direction-type><words>{word}</words></direction-type>'
                    '<direction-type><dashes type="start"/></direction-type></direction>'
                    '<direction><direction-type><dashes type="stop"/></direction-type>'
                    '<offset>16</offset></direction>'
                    '<sound tempo="110"><offset>8</offset></sound>' +
                    self.tempo_mark(60, 16))
                self.assertEqual(result[2], 90 if word in accepted else 110)

    def test_ramp_without_exported_steps_and_dotted_metronome(self):
        result = self.parse_tempo_fixture(
            self.tempo_mark(60) +
            '<direction><direction-type><words>accel.</words></direction-type></direction>' +
            self.tempo_mark(80, 16, 'eighth', 1))
        self.assertEqual(result[0], 60)
        self.assertEqual(result[2], 60)
        self.assertEqual(result[4], 60)  # dotted eighth = 80 means quarter = 60
        result = self.parse_tempo_fixture(
            self.tempo_mark(60) +
            '<direction><direction-type><words>accel.</words></direction-type></direction>' +
            self.tempo_mark(80, 16, 'half', 1))
        self.assertEqual(result[2], 150)
        self.assertEqual(result[4], 240)

    def test_ramp_without_next_mark_uses_default_target(self):
        result = self.parse_tempo_fixture(
            '<sound tempo="60"/>' + self.tempo_mark(60) +
            '<direction><direction-type><words>accel.</words></direction-type></direction>'
            '<sound tempo="75"><offset>8</offset></sound>'
            '<sound dynamics="80"/>')
        self.assertEqual(result[0], 60)
        self.assertEqual(result[1], 67.5)
        self.assertEqual(result[2], 75)

    def test_nested_sound_tempo_offsets(self):
        result = self.parse_tempo_fixture(
            '<sound tempo="60"/>'
            '<direction><offset>4</offset><sound tempo="90"/></direction>'
            '<direction><offset>4</offset><sound tempo="120"><offset>8</offset></sound></direction>')
        self.assertEqual(result, {0: 60, 1: 90, 2: 120})

    def test_accelerando_musicxml_to_pho(self):
        xml = ROOT / 'testxml/akzent-accel.musicxml'
        expected_accents = len(ET.parse(xml).findall('.//note/notations/articulations/accent'))
        mxparse = Path(self.tmp.name) / 'accel.mxparse'
        subprocess.run([str(self.parser), str(xml), str(mxparse)], stdout=subprocess.DEVNULL, check=True)
        raw = self.env['load_mxparse'](mxparse)
        notes = self.reconstruct(raw)
        original_notes = [n for n in notes if n['type'] == 'note']
        self.assertEqual(len(original_notes), expected_accents)
        self.assertEqual(len({n['note_id'] for n in original_notes}), expected_accents)

        # Independently integrate each parser fragment before reconstruction.
        expected_ms = 0
        bpm = 120
        durations = {}
        for event in raw:
            if event['type'] == 'tempo':
                bpm = event['bpm']
            else:
                duration = event['duration'] * 60000 / bpm
                expected_ms += duration
                if event['type'] == 'note':
                    durations[event['note_id']] = durations.get(event['note_id'], 0) + duration
        self.assertAlmostEqual(sum(n['duration_ms'] for n in notes), expected_ms)
        for note in original_notes:
            self.assertAlmostEqual(note['duration_ms'], durations[note['note_id']])

        result = subprocess.run([sys.executable, str(ROOT / 'xml-to-pho.py'), 'xml', str(mxparse)],
                                capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        self.assertEqual(sum(line.startswith('meta accent ') for line in lines), expected_accents)
        phones = [line.split() for line in lines if line and not line.startswith(('meta', ';'))]
        self.assertEqual(sum(p[0] == 'l' for p in phones), expected_accents)
        self.assertEqual(sum(p[0] == 'a' for p in phones), expected_accents)
        # This score ends on a note, so pho includes a 500 ms release rest.
        # pho rounds every duration to two decimal places.
        self.assertEqual(phones[-1][0], '_')
        self.assertAlmostEqual(sum(float(p[1]) for p in phones), expected_ms + 500,
                               delta=len(phones) * 0.005)


if __name__ == '__main__':
    unittest.main()
