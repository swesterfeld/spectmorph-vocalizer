#!/usr/bin/env python3

# tata.py $(soxi -D voice/sven.flac) 1

#243.503731	243.503731	t
#243.632267	243.632267	a


#264.884632	264.884632	a
#265.514565	265.514565	t


import sys

sp = float (sys.argv[2])
voice_length = float (sys.argv[1])

print ("note_on 0 52 100")
ct = 243.503731

for i in range (10 * 1000):
  if ct < 264:
    if ct < 243.632267:
      ct += 1 / 1000
    else:
      ct = 264.884632
  else:
    ct += sp / 1000
    if ct > 265.514565:
      ct = 243.503731
  sp *= 1.001
  print ("control 0", ct / voice_length * 2 - 1)
  print ("control 1", 0)
  print ("control 2", -1)
  #print (ws1[i], ws2[i], morph[i], "#X")
  print ("process 48")
