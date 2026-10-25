About:
======
SpectMorph-Vocalizer performs musicxml to wav conversion with a synthetic 
singing voice. It is currently in an experimental pre-alpha state.

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

Sung-item forced alignment
=========================
`singing_align.py` is an experimental Python aligner for SAMPA transcriptions
of isolated sung items, with duration priors and Audacity label export.
See [ALIGNMENT.md](ALIGNMENT.md) for setup, input conventions and testing.
