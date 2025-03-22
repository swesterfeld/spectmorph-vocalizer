#!/usr/bin/env python3

# tata.py $(soxi -D voice/sven.flac) 1 ta > tata.script
# src/smscript voice/sven.smplan tata.script tata.wav

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

text = sys.argv[3]
synlist = []
nlen = 1000
acc = 0
for rep in range (40):
  # S short part
  # L long part
  # L * 2 + S * 2 == nlen
  if nlen < 200:
    L = nlen / 4
    S = nlen / 4
  else:
    L = nlen / 2 - 50
    S = 50
  for x in range (len (lines)):
    tri = lines[x:x+3]
    if tri[0][1] == "a" and tri[1][1] == text[0] and tri[2][1] == text[0] + "h":
      ct = (tri[0][0] + tri[1][0]) / 2
      synlist.append ((ct, tri[1][0], L))
      end = (tri[1][0] + tri[2][0]) / 2
      synlist.append ((tri[1][0], end, S))
  for x in range (len (lines)):
    tri = lines[x:x+3]
    if tri[0][1] == text[0] and tri[1][1] == text[0] + "h" and tri[2][1] == "a":
      #nextt = (tri[0][0] + tri[1][0]) / 2
      synlist.append ((tri[1][0] - 0.02, tri[2][0], S))
      nextend = tri[2][0] + 0.3
      synlist.append ((tri[2][0], nextend, L))
  acc += nlen
  if acc > 500:
    nlen *= 0.85
    acc = 0
#for s in synlist:
#  print (s)
phase = 0
ms = 0
ct = synlist[0][0]
for i in range (1000 * 1000):
  ratio = (synlist[phase][1] - synlist[phase][0]) * 1000 / synlist[phase][2]
  print ("#", ratio)
  ct += sp / 1000 * ratio
  if ct > synlist[phase][1]:
    phase += 1
    if (phase >= len (synlist)):
      sys.exit (0)
    ct = synlist[phase][0]

  print ("control 0", ct / voice_length * 2 - 1)
  print ("control 1", 0)
  print ("control 2", -1)
  #print (ws1[i], ws2[i], morph[i], "#X")
  print ("process 48")
