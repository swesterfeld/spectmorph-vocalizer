#!/usr/bin/env python3
from scipy.io import wavfile
import numpy as np
import sys

sample_rate, int_data = wavfile.read (sys.argv[2])

time_samples_since_start = 0
x = 0
xx = ""
f = open (sys.argv[1], "r")
accent = False
accent_list = []
dynamic_volume = 0.55 # mf
dynamic_volume_list = []
for line in f.readlines():
  spl = line.split()
  if len (spl) > 2 and spl[1] == "ACCENT":
    accent = (spl[2] == "True")
  if len (spl) > 2 and (spl[1] == "VOLUME" or spl[1] == "START_VOLUME" or spl[1] == "END_VOLUME"):
    dynamic_volume = float (spl[2])
    xx = spl[1]
  if len (spl) > 1 and spl[0] != ";;;":
    #print ("%f %s" % (float (spl[1]), accent))
    if xx != "":
      dynamic_volume_list.append ((time_samples_since_start, dynamic_volume, xx, spl[0]))
      xx = ""
    time_ms = float (spl[1])
    time_samples = int (time_ms / 1000 * sample_rate)
    time_samples_since_start += time_samples
    for t in range (time_samples):
      accent_list.append (3 if accent else 1)

def get_accent (time):
  time = int (time)
  if time >= len (accent_list):
    time = len (accent_list) - 1
  return accent_list[time]

def get_volume (time):
  start = 0
  end = 0
  start_volume = 0
  end_volume = 0
  for x in dynamic_volume_list:
    if (time > x[0]):
      start = x[0]
      start_volume = x[1]
    else:
      if end == 0:
        end = x[0]
        end_volume = x[1]
  dist = end - start
  volume = start_volume + (time - start) / dist * (end_volume - start_volume)
  #print (time, start, end, start_volume, end_volume, volume)
  return volume

#for x in dynamic_volume_list:
    #print (x)
slope = 1 / (sample_rate * 0.040)
offset = sample_rate * 0.025

volume = 1
dyn_volume = 0.55
old_dyn_target = -1 # force init
for x in range (int_data.shape[0]):
  target = get_accent (x + offset)
  dyn_target = get_volume (x)
  if old_dyn_target != dyn_target:
    dyn_slope = (dyn_target - dyn_volume) / (sample_rate * 0.040)
    old_dyn_target = dyn_target
    dyn_steps = (sample_rate * 0.040)
  if volume < target:
    volume += slope
  if volume > target:
    volume -= slope
  if dyn_steps > 0:
    dyn_volume += dyn_slope
    dyn_steps -= 1
  int_data[x] *= volume / 3 * dyn_volume * dyn_volume
  #print (x, volume, dyn_volume)
  # print (x, volume, target)

# normalize
try:
  int_data = int_data.astype (np.float64)
  max_val = np.max (np.abs (int_data))
  if max_val > 1e-4:
    int_data /= max_val
except:
  print ("normalization failed")

wavfile.write (sys.argv[3], sample_rate, int_data)
