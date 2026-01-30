#!/usr/bin/env python3
import soundfile as sf
import numpy as np
import sys
import math

data, sample_rate = sf.read (sys.argv[1], dtype='float64')

max_val = np.max (np.abs (data))
if max_val > 1e-4:
    data /= max_val

print ("normalize: %f dB" % (20 * math.log10 (1.0 / max_val)))

sf.write (sys.argv[1], data, sample_rate, subtype='PCM_24')
