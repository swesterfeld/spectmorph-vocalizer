#!/usr/bin/env python3

import sys
import math
from scipy.io import wavfile
import numpy as np

SR, signal = wavfile.read (sys.argv[1])

print ("# %f seconds audio" % (len (signal) / SR))

ms = SR // 1000
assert (ms * 1000 == SR)

start = 0

while start < len (signal):
  energy = np.mean (signal[start:start + ms * 30] ** 2)

  if energy > 0:
    print (start / ms, 10 * math.log10 (energy))
  else:
    print (start / ms, -200)
  start += ms * 10

