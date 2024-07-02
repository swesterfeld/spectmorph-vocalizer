#!/bin/bash
tts.py "$@" > tts.pho
phomorphdi.py tts.pho $(soxi -D voice/sven.flac) > tts.script
src/smscript voice/sven.smplan tts.script tts.wav
./apply-accent.py tts.pho tts.wav tts.wav
