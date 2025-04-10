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

with open ("diphone-sven.label", "r") as file:
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

sl_trace_file = open ('tata.txt', 'w')
sl_trace_set = set()

diphone_missing_set = set()

def sl_trace (label):
  out = "%f\t%f\t%s" % (synlist[-1][0], synlist[-1][1], label)
  if out not in sl_trace_set:
    print (out, file=sl_trace_file)
    print ("%s\t%f\t%f" % (out, synlist[-1][2], (synlist[-1][1] - synlist[-1][0]) / (synlist[-1][2] / 1000)), file=sys.stderr)
    sl_trace_set.add (out)

def phone_class (p):
  if p in [ 'a', 'i', 'I', 'e', 'o', 'O', 'u', 'U', 'y', 'Y', '6', '2', '@', 'E' ]:
    return "v"
  if p in  [ "t", "p", "k", "d", "b", "g" ]:
    return "p"
  if p in [ 'n', 'm', 'l', 's', 'Z', 'S', 'f', 'v', 'r', 'h', 'N', 'z', 'j', 'C', 'x' ]:
    return "c"
  raise RuntimeError ("unknown phone class: %s" % p)

def diphone_class (d):
  assert (len (d) == 2)
  return phone_class (d[0]) + phone_class (d[1])

def cons_count (text):
  cc = 0
  for t in text[:-1]: # last char is the same as first char
    if (phone_class (t) != "v"):
      cc += 1
  return cc

print ("\n[", file=sys.stderr)
for rep in range (40):
  # S short part
  # L long part
  # L * 2 + S * 2 == nlen
  if nlen < 50 * 2 * (cons_count (text) + 1): # hardcode: one vowel
    L = nlen / (2 * (cons_count (text) + 1))
    S = L
  else:
    L = nlen / 2 - cons_count (text) * 50
    S = 50
  #print ("plosiv", "a" + "|" + text[0] + "|" + text[0] + "h")
  for d in tsplit:
    diphone_missing = True
    dclass = diphone_class (d)
    if dclass == "vp":
      for x in range (len (lines)):
        tri = lines[x:x+3]
        # example: a | t | th
        if tri[0][1] == d[0] and tri[1][1] == d[1] and tri[2][1] == d[1] + "h":
          ct = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((ct, tri[1][0], L, 1))
          sl_trace (d + "1")
          end = (tri[1][0] + tri[2][0]) / 2
          synlist.append ((tri[1][0], end, S, 1))
          sl_trace (d + "2")
          diphone_missing = False
          break
    elif dclass == "pv":
      for x in range (len (lines)):
        tri = lines[x:x+3]
        # example: t | th | a
        if tri[0][1] == d[0] and tri[1][1] == d[0] + "h" and tri[2][1] == d[1]:
          #nextt = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((tri[1][0] - 0.02, tri[2][0], S, 2))
          sl_trace (d + "1")
          nextend = tri[2][0] + 0.3
          synlist.append ((tri[2][0], nextend, L, 1))
          sl_trace (d + "2")
          diphone_missing = False
          break
    elif dclass == "pp":
      for x in range (len (lines)):
        quad = lines[x:x+4]
        # example: k | kh | t | th
        if quad[0][1] == d[0] and quad[1][1] == d[0] + "h" and quad[2][1] == d[1] and quad[3][1] == d[1] + "h":
          #synlist.append ((quad[1][0] - 0.02, quad[2][0], S))
          synlist.append ((quad[1][0], quad[2][0], S, 0.001))
          sl_trace (d + "1")
          synlist.append (((quad[2][0] + quad[3][0]) / 2 + 0.05, (quad[2][0] + quad[3][0]) / 2 + 0.1, S, 1))
          sl_trace (d + "2")
          diphone_missing = False
          break
    elif dclass == "vc":
      for x in range (len (lines)):
        tri = lines[x:x+3]
        # example a S
        if tri[0][1] == d[0] and tri[1][1] == d[1]:
          ct = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((ct, tri[1][0], L, 1))
          sl_trace (d + "1")
          synlist.append ((tri[1][0], (tri[1][0] + tri[2][0]) / 2, S, 1))
          sl_trace (d + "2")
          diphone_missing = False
          break
    elif dclass == "cp":
      for x in range (len (lines)):
        tri = lines[x:x+3]
        if tri[0][1] == d[0] and tri[1][1] == d[1] and tri[2][1] == d[1] + "h":
          ct = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((ct, tri[1][0], S, 1))
          sl_trace (d + "1")
          end = (tri[1][0] + tri[2][0]) / 2
          synlist.append ((tri[1][0], end, S, 1))
          sl_trace (d + "2")
          diphone_missing = False
          break
    elif dclass == "cv":
      for x in range (len (lines)):
        tri = lines[x:x+3]
        # example: S a
        if tri[0][1] == d[0] and tri[1][1] == d[1]:
          ct = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((ct, tri[1][0], S, 1))
          sl_trace (d + "1")
          end = (tri[1][0] + tri[2][0]) / 2
          synlist.append ((tri[1][0], end, L, 1))
          sl_trace (d + "2")
          diphone_missing = False
          break
    elif dclass == "pc":
      for x in range (len (lines)):
        tri = lines[x:x+3]
        # example: t | th | S
        if tri[0][1] == d[0] and tri[1][1] == d[0] + "h" and tri[2][1] == d[1]:
          #nextt = (tri[0][0] + tri[1][0]) / 2
          synlist.append ((tri[1][0] - 0.02, tri[2][0], S, 2))
          sl_trace (d + "1")
          nextend = tri[2][0] + 0.1
          synlist.append ((tri[2][0], nextend, S, 1))
          sl_trace (d + "2")
          diphone_missing = False
          break

    if diphone_missing:
      diphone_missing_set.add (d)
  acc += nlen
  if acc > 500:
    nlen *= 0.85
    acc = 0
print ("]\n", file=sys.stderr)
#for s in synlist:
#  print (s)
if diphone_missing_set:
  for d in diphone_missing_set:
    print ("missing diphone %s" % d, file=sys.stderr)
  sys.exit (1)
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
