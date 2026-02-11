#!/usr/bin/env python3

import sys

nlen = 1000
acc = 0
print ("rest 1")
for i in range (40):
  print ("50 %f %s" % (int (nlen / 500 * 64) / 64, sys.argv[1]))
  acc += nlen
  if acc > 500:
    nlen *= 0.85
    acc = 0
print ("rest 1")
