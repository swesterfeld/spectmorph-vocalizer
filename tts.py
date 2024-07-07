#!/usr/bin/env python3
import subprocess
import sys

def is_v (v):
  for vv in [ 'a', 'i', 'I', 'e', 'o', 'O', 'U', '6', '@', 'E' ]:
    if v == vv or v == vv + ':':
      return True
  return v == '_'

freq = 100
print ("_ 50")
pho = subprocess.run (["espeak-ng", "-v", "mb-de2", sys.argv[1], "--pho", "-q" ], capture_output=True, text=True)
print (";;; VOLUME 0.85")
for p in pho.stdout.splitlines():
  s = p.split ('\t')
  if len (s) > 0:
    for x in s[0]:
      if x == "_":
        print ("_ 1000")
      elif x == ":":
        pass
      elif is_v(x):
        print (x,"350 0 80 100 80")
      else:
        print (x, "50")
print (";;; VOLUME 0.85")
print ("_ 50")
