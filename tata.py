#!/usr/bin/env python3

# tata.py $(soxi -D voice/sven.flac) 1 ta > tata.script
# src/smscript voice/sven.smplan tata.script tata.wav

# tata...
# taktak
# dapdap
# pampam
# laklak
# SaSa
# SapSap
# tI
# Il
# b6
# 6t

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

# split text into diphones
text = sys.argv[3]
text += text[0]
tsplit = []
for i in range (len (text) - 1):
  tsplit.append (text[i:i+2])

synlist = []
nlen = 1000
acc = 0

def sl_trace (label):
  pass
  #print ("%f\t%f\t%s" % (synlist[-1][0], synlist[-1][1], label))

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
  #print ("plosiv", "a" + "|" + text[0] + "|" + text[0] + "h")
  for d in tsplit:
    diphone_missing = True
    if d == "a" + text[0]:
      for x in range (len (lines)):
        tri = lines[x:x+3]
        if tri[0][1] == "a" and tri[1][1] == text[0] and tri[2][1] == text[0] + "h":
          ct = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((ct, tri[1][0], L, 1))
          sl_trace ("at1")
          end = (tri[1][0] + tri[2][0]) / 2
          synlist.append ((tri[1][0], end, S, 1))
          sl_trace ("at2")
        diphone_missing = False
    elif d == text[0] + "a":
      for x in range (len (lines)):
        tri = lines[x:x+3]
        if tri[0][1] == text[0] and tri[1][1] == text[0] + "h" and tri[2][1] == "a":
          #nextt = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((tri[1][0] - 0.02, tri[2][0], S, 2))
          sl_trace ("ta1")
          nextend = tri[2][0] + 0.3
          synlist.append ((tri[2][0], nextend, L, 1))
          sl_trace ("ta2")
        diphone_missing = False
    elif d == "ak" or d == "ap":
      for x in range (len (lines)):
        tri = lines[x:x+3]
        if tri[0][1] == "a" and tri[1][1] == d[1] and tri[2][1] == d[1] + "h":
          ct = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((ct, tri[1][0], L, 1))
          sl_trace ("ak1")
          end = (tri[1][0] + tri[2][0]) / 2
          synlist.append ((tri[1][0], end, S, 1))
          sl_trace ("ak2")
        diphone_missing = False
    elif d == "kt" or d == "pd":
      for x in range (len (lines)):
        quad = lines[x:x+4]
        if quad[0][1] == d[0] and quad[2][1] == d[1]:
          #synlist.append ((quad[1][0] - 0.02, quad[2][0], S))
          synlist.append ((quad[1][0], quad[2][0], S, 0.001))
          sl_trace ("kt1")
          synlist.append (((quad[2][0] + quad[3][0]) / 2 + 0.05, (quad[2][0] + quad[3][0]) / 2 + 0.1, S, 1))
          sl_trace ("kt2")
        diphone_missing = False
    if diphone_missing:
      print ("missing diphone %s" % d, file=sys.stderr)
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
  # FIXME print ("global_volume", synlist[phase][3])
