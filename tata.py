#!/usr/bin/env python3

# tata.py $(soxi -D voice/sven.flac) 1 > tata.script
# src/smscript voice/sven.smplan tata.script tata.wav

#243.503731	243.503731	t
#243.632267	243.632267	a


#264.884632	264.884632	a
#265.514565	265.514565	t


import sys

sp = float (sys.argv[2])
voice_length = float (sys.argv[1])

lines = []
with open ("plosive.label", "r") as file:
  for line in file:
    line = line.split()
    lines.append ((float (line[0]), line[2].rstrip(":")))

print ("note_on 0 52 100")
#ct = 243.503731

text = "ta"
for x in range (len (lines)):
  tri = lines[x:x+3]
  if tri[0][1] == "a" and tri[1][1] == text[0] and tri[2][1] == text[0] + "h":
    #print (tri[0][0], tri[0][1], tri[1][0], tri[1][1], tri[2][0], tri[2][1])
    ct = (tri[0][0] + tri[1][0]) / 2
    start = ct
    end = (tri[1][0] + tri[2][0]) / 2
  if tri[0][1] == text[0] and tri[1][1] == text[0] + "h" and tri[2][1] == "a":
    nextt = (tri[0][0] + tri[1][0]) / 2
    nextend = tri[2][0] + 0.3

phase = 0
for i in range (10 * 1000):
  ct += sp / 1000
  #ct += .3 / 1000
  '''
  sp *= 1.001
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
  '''
  if ct > end and phase == 0:
    ct = nextt
    phase = 1
  if ct > nextend and phase == 1:
    ct = start
    phase = 0

  print ("control 0", ct / voice_length * 2 - 1)
  print ("control 1", 0)
  print ("control 2", -1)
  #print (ws1[i], ws2[i], morph[i], "#X")
  print ("process 48")
