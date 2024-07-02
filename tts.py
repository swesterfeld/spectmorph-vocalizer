#!/usr/bin/env python3
import subprocess
import sys

freq = 100
print ("_ 50")
pho = subprocess.run (["espeak-ng", "-v", "de", sys.argv[1], "-x", "-q" ], capture_output=True, text=True)
print (pho.stdout, file=sys.stderr)
print (";;; VOLUME 0.85")
for p in pho.stdout:
  if p != ":" and p != "'" and p != "," and p != "|" and p != "!":
    if p == " " or p == "\n":
      print ("_ 1000")
    else:
      if p == "A":
        p = "a"
      if p == "a" or p == "o" or p == "U":
        print ("%s 350 0 %f 350 %f" % (p, freq, freq))
      else:
        print (p, "50")
print (";;; VOLUME 0.85")
print ("_ 50")
