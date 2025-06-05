#!/usr/bin/env python3
from scipy.io import wavfile
import numpy as np
import sys

sample_rate, int_data = wavfile.read (sys.argv[1])

# normalize
try:
  int_data = int_data.astype (np.float64)
  max_val = np.max (np.abs (int_data))
  if max_val > 1e-4:
    int_data /= max_val
except:
  print ("normalization failed")

wavfile.write (sys.argv[1], sample_rate, int_data)
