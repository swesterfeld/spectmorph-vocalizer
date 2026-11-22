About:
======
SpectMorph-Vocalizer performs musicxml to wav conversion with a synthetic 
singing voice. It is currently in an experimental pre-alpha state.

Tempo changes
=============
Numeric MusicXML metronome marks define the written tempo (including dotted
beat units). `rit.`, `ritardando`, `rall.`, `rallentando`, `accel.` and
`accelerando` lead linearly in beats from the current tempo over their marked
range. The ramp ends at its numbered dash stop (MuseScore) or the end of its
regularly spaced, monotonic sound-tempo samples (Dorico). A numeric metronome
mark at that endpoint supplies the target BPM; otherwise the target is 125%
of the starting BPM for accelerando or 75% for ritardando. Tempo equivalences
(such as quarter = half) use the exported `sound tempo` at the same position
as an explicit tempo change. An equivalence following a ramp also supplies
that ramp's target BPM, without extending its inferred range. That tempo is held
until the next instruction. `a tempo` restores its exported playback tempo,
or the tempo before the ramp when no playback value is provided. It is not
used as the ramp's target. If neither range is available, the next numeric
mark determines the endpoint; without either, exported tempos are kept.
Direction text is split on whitespace; the first known tempo word is used,
ignoring case and allowing an optional trailing period. Unknown words (such
as `poco`, `molto` and `meno`) are ignored. Exported `sound tempo` samples
within the range are adjusted; if no samples exist, sixteenth-note steps
are generated.

Microtonal pitch
===============
MusicXML direction text such as `+23ct` or `-17.5ct` adjusts the note at that
musical position by the given number of cents. The adjustment is added to the
ordinary and quarter-tone accidentals.  It applies only to the actual note, not
to following notes.

Debug curves
============
Rendering creates `debug/<piece>.json`; plot it with:

```sh
./gen-wavs.sh testxml/sfz-schla.musicxml
./plot-debug.py debug/sfz-schla.json
```

See `./plot-debug.py --help` for curves, zoom controls and export options.

Hiatus transition labels
========================

Voice labels can mark a vowel transition explicitly with the concatenated
vowel names, for example `e`, `eo`, `o` or `i`, `ia`, `a`. The transition
starts at the `eo`/`ia` marker and ends at the following vowel's start.

Sung-item forced alignment
=========================
`singing_align.py` is an experimental Python aligner for SAMPA transcriptions
of isolated sung items, with duration priors and Audacity label export.
See [ALIGNMENT.md](ALIGNMENT.md) for setup, input conventions and testing.

Local voice groups
==================
To load the split recordings in `voice/sven-test/`, use this configuration
in `voice/sven-test/voice.sh`:

```sh
VOICE_MIDI_NOTE=50
VOICE_SEGMENT_GLOB='*_split.sm'
```

The wildcard is relative to the voice directory. Each matching `.sm` file
loads with its matching `.txt` labels and `.volume` data, in filename order.
All matches inherit the settings in the `.sh` file; separate `.sh` files for
each recording are unnecessary. A wildcard configuration replaces the usual
segment named after that configuration (so this example does not also load
`voice.sm`). Run with `./gen-wavs.sh -v sven-test your-score.musicxml`.

These are pre-built local files: wildcard groups bypass hash-based downloads
and do not require FLAC files for synthesis. Missing matches or sidecars are
reported as errors. `VOICE_DISABLED=1` disables the whole group. Other `.sh`
configurations can define additional groups or individual segments, but must
not select the same segment twice. Configurations without `VOICE_SEGMENT_GLOB`
continue to load the segment with the same basename as the `.sh` file.
