#!/usr/bin/env python3

import sys

ms=48
beat = 0
beat4 = 0

samples_per_beat = 48000 / float (sys.argv[1]) * 60
for i in range (48*1000*35):
  beat += 1
  if beat >= samples_per_beat:
    beat -= samples_per_beat
    beat4 += 1
    if (beat4 == 4):
      beat4 = 0
  if beat > samples_per_beat / 4:
    print (i/48., -70)
  else:
    if beat4 == 0:
      print (i/48., -10)
    else:
      print (i/48., -20)
