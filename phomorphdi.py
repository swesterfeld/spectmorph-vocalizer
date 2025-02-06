#!/usr/bin/env python3

# TODO
#  - detect first note
#  - note end
#  - perfect timing
#  - morph should properly overlap, triphones should extend a bit in the morph range

import sys
import random
from math import log2

assert (len (sys.argv) == 3)

voice_length = float (sys.argv[2])

lines = []
with open ("diphone-sven.label", "r") as file:
  for line in file:
    line = line.split()
    lines.append ((float (line[0]), line[2].rstrip(":")))

pho = []
line_number = 1
with open (sys.argv[1], "r") as file:
  for line in file:
    x = line.split()
    if len (x) > 0:
      #x.append (line_number)
      if x[0][0] != ';':
        pho.append (x)
    line_number += 1

# collapse multiple pause (_) lines into one - this is necessary because
# mbrola does not support long pauses
out = []
last = None
for i in range (len (pho)):
  if last and last[0] == '_' and pho[i][0] == '_':
    out[-1][1] = str (float (out[-1][1]) + float (pho[i][1]))
  else:
    out.append (pho[i])
  last = pho[i]
pho = out

# ensure last diphone ends in a break
if (pho[-1][0] != "_"):
  pho.append (["_", 50])

class Diphone:
  def __repr__ (self):
    s = '<Diphone'
    s += ' bend=%f' % self.bend
    s += ' start_ms=%f' % self.start_ms
    s += ' p1_ms=%f' % self.p1_ms
    s += ' p2_ms=%f' % self.p2_ms
    s += ' pos1=%f' % self.pos1
    s += ' pos2=%f' % self.pos2
    s += ' silent=%s' % self.silent
    s += ' startv=%s' % self.startv
    s += ' endv=%s' % self.endv
    s += ' lyric=%s' % self.lyric
    s += '>'
    return s

def is_v (v):
  for vv in [ 'a', 'i', 'I', 'e', 'o', 'O', 'U', '6', '@', 'E' ]:
    if v == vv or v == vv + ':':
      return True
  return v == '_'

errors = []
start_ms = 0
last_p2_ms = 0
print ("note_on 0 52 100")
diphones = []
last_f = 130.81
for i in range (len (pho)):
  if i + 1 < len (pho):
    P1 = pho[i][0]
    P2 = pho[i + 1][0]
    if is_v (P1):
      P1 = P1[0][0]
    if is_v (P2):
      P2 = P2[0][0]
    ''' staccato: FIXME: do we need this at all?
    if P1 == '_':
      d = Diphone()
      d.start_ms = start_ms
      d.p1_ms = float (pho[i][1])
      d.p2_ms = 0
      d.startv = d.endv = False
      d.pos1 = d.pos2 = 0
      d.lyric = '__'
      d.bend = log2 (last_f / 164.81) * 12 # FIXME
      d.silent = True
      diphones.append (d)
    '''
    if is_v (P1) and is_v (P2) and P2 != '_' and P1 != '_':
      possible_matches = []
      for j in range (len (lines) - 1):
        x = lines[j:j+3]
        if x[0][1] == P1 + '_' + P2:
          possible_matches.append (x)
      if len (possible_matches) == 0:
        # print ("missing diphone %s" % (P1 + P2))
        errors += [ "%s: missing diphone %s" % (sys.argv[1], P1 + P2) ]
      else:
        # since we have a vowel at start, last_f is already the frequency of the vowel
        if len (pho[i + 1]) >= 3:
          # true: vowel -> vowel case (melisma)
          last_f = float (pho[i + 1][3])
        m = random.choice (possible_matches)
        d = Diphone()
        d.lyric = P1 + P2
        d.start_ms = start_ms
        d.p1_ms = float (pho[i][1]) / 2
        d.p2_ms = float (pho[i + 1][1]) / 2
        start_ms += last_p2_ms + d.p1_ms # FIXME: doesn't seem to be the right value
        #print ("%f\t%f\t%s" % (d.start_ms / 1000, d.start_ms / 1000, P1))
        last_p2_ms = d.p2_ms
        d.pos1 = (m[0][0] + m[1][0]) / 2
        d.pos2 = (m[1][0] + m[2][0]) / 2
        d.startv = True
        d.endv = True
        d.bend = log2 (last_f / 164.81) * 12 # FIXME
        d.silent = False
        diphones.append (d)
    else:
      possible_matches = []
      for j in range (len (lines) - 2):
        x = lines[j:j+3]
        if x[0][1] == P1 and x[1][1] == P2:
          possible_matches.append (x)
      if len (possible_matches) == 0:
        #print ("line %d: missing diphone %s" % (pho[i][-1], P1 + P2))
        errors += [ "%s: missing diphone %s" % (sys.argv[1], P1 + P2) ]
      else:
        m = random.choice (possible_matches)
        d = Diphone()
        d.lyric = P1 + P2
        d.start_ms = start_ms
        #print ("%f\t%f\t%s" % (d.start_ms / 1000, d.start_ms / 1000, P1))
        d.p1_ms = float (pho[i][1]) / 2
        d.p2_ms = float (pho[i + 1][1]) / 2
        d.silent = False
        ''' staccato: FIXME: commenting this out now works for melisma.xml but breaks schaut-lang-kurz.xml
        if P1 == '_':
          d.p1_ms = 0
          d.p2_ms *= 2 # FIXME: not sure if this is what we want
        elif P2 == '_':
          d.p1_ms *= 2 # FIXME: not sure if this is what we want
          d.p2_ms = 0
        '''
        start_ms += last_p2_ms + d.p1_ms # FIXME: doesn't seem to be the right value
        last_p2_ms = d.p2_ms
        if len (pho[i]) >= 3:
          last_f = float (pho[i][3])
        if len (pho[i + 1]) >= 3:
          last_f = float (pho[i + 1][3])
        if is_v (pho[i][0]) and P1 != '_':
          d.bend = log2 (last_f / 164.81) * 12
          d.pos1 = m[1][0] - 0.2
          if P2 == '_':
            d.pos2 = m[1][0]
          else:
            d.pos2 = (m[1][0] + m[2][0]) / 2
          d.startv = True
          d.endv = False
          diphones.append (d)
        elif is_v (pho[i + 1][0]):
          if P1 == '_':
            d.pos1 = m[1][0]
          else:
            d.pos1 = (m[0][0] + m[1][0]) / 2
          d.pos2 = m[1][0] + 0.2
          d.startv = False
          d.endv = True
          d.bend = log2 (last_f / 164.81) * 12
          diphones.append (d)
        elif not is_v (pho[i][0]) and not is_v (pho[i + 1][0]):
          d.pos1 = (m[0][0] + m[1][0]) / 2
          d.pos2 = (m[1][0] + m[2][0]) / 2
          d.startv = False
          d.endv = False
          d.bend = log2 (last_f / 164.81) * 12
          diphones.append (d)
        elif P1 == '_' and not is_v (pho[i + 1][0]):
          d.pos1 = m[1][0]
          d.pos2 = (m[1][0] + m[2][0]) / 2
          d.startv = False
          d.endv = False
          d.bend = log2 (last_f / 164.81) * 12
          diphones.append (d)

if errors:
  for e in sorted (set (errors)):
    print (e, file=sys.stderr)
  sys.exit (1)
'''
  if (pho[i][0] == 'a:' or pho[i][0] == 'i:' or pho[i][0] == 'o:') and i + 2 < len (pho):
    v1 = pho[i][0][0]
    c  = pho[i + 1][0]
    v2 = pho[i + 2][0][0]
    possible_matches = []
    for j in range (len (lines) - 2):
      x = lines[j:j+3]
      if x[0][1] == v1 and x[1][1] == c and x[2][1] == v2:
        possible_matches.append (x)
    assert (len (possible_matches) > 0)
    m = random.choice (possible_matches)
    t = Triphone()
    t.lyric = v1 + c + v2
    t.bend = log2 (float (pho[i + 2][3]) / 164.81) * 12
    t.c_ms = float (pho[i + 1][1])
    t.start_ms = start_ms
    t.pos1 = m[0][0]
    t.pos2 = m[2][0]
    t.start_v_ms = float (pho[i][1]) / 2
    t.end_v_ms = float (pho[i + 2][1]) / 2
    triphones.append (t)
    #print (t)
    #print (pho[i])
    #print (pho[i+1])
    #print (pho[i+2])
    start_ms += t.start_v_ms + t.c_ms + t.end_v_ms
'''

for d in diphones:
  print (d, file=sys.stderr)
  #print (t.start_v_ms + t.c_ms + t.end_v_ms, (t.pos2 - t.pos1) * 1000, file=sys.stderr)

def gen_wav_source (start):
  pos = []
  dist = []
  dd = []
  idx = 0
  for d in diphones:
    ms = int (d.p1_ms + d.p2_ms)
    for j in range (ms):
      pos.append (0)
      dist.append (10000)
      dd.append (None)
  p = 0
  for d in diphones:
    ms = int (d.p1_ms + d.p2_ms)
    if d.startv == False and d.endv == False:
      stretch_cc = (d.pos2 - d.pos1) * 1000 / ms
    if d.startv == True and d.endv == True:
      stretch_vv = (d.pos2 - d.pos1) * 1000 / ms
      #print ((d.pos2 - d.pos1) * 1000, ms, stretch_cc, "#P")
    for j in range (-120, ms + 120):
      if idx % 2 == start:
        if d.startv == False and d.endv == True:
          x = d.pos1 + j * 0.001
          if x > d.pos2:
            x = d.pos2
        elif d.startv == True and d.endv == False:
          x = d.pos2 - (ms - j) * 0.001
          if x < d.pos1:
            x = d.pos1
        elif d.startv == False and d.endv == False:
          x = d.pos1 + j * 0.001 * stretch_cc
          if x < d.pos1:
            x = d.pos1
          if x > d.pos2:
            x = d.pos2
        elif d.startv == True and d.endv == True:
          x = d.pos1 + j * 0.001 * stretch_vv
          if x < d.pos1:
            x = d.pos1
          if x > d.pos2:
            x = d.pos2
        dp_dist = min (abs (j), abs (j - ms))
        if p + j >= 0 and p + j < len (pos) and dist[p + j] > dp_dist:
          pos[p + j] = x
          dist[p + j] = dp_dist
          dd[p + j] = d
    p += ms
    '''
    ms1 = int (t.start_v_ms + t.c_ms / 2)     # time: first half of the triphone
    msv1 = ms1 - (t.pos2 - t.pos1) * 1000 / 6 # time: for the first vowel
    ms2 = int (t.end_v_ms + t.c_ms / 2)       # time: second half of the triphone
    msv2 = ms2 - (t.pos2 - t.pos1) * 1000 / 6 # time: for the second vowel
    for j in range (ms):
      if idx % 2 == start:
        if j < msv1:
          # timestretch first vowel using the first 1/3 of the triphone recording
          frac = j / msv1
          x = t.pos1 + frac * (t.pos2 - t.pos1) / 3
        elif j < ms - msv2:
          # play consonant part of the triphose (1/3 of the recording) without stretching
          x = (t.pos1 + t.pos2) / 2 - (ms1 - j) / 1000
        else:
          # timestretch second vowel using the last 1/3 of the triphone recording
          frac = (j - (ms - msv2)) / msv2
          x = t.pos1 + (frac + 2) * (t.pos2 - t.pos1) / 3
        pos.append (x)
      else:
        if len (pos):
          pos.append (pos[-1])
        else:
          pos.append (0)
      d += 1
    '''
    idx += 1
  return pos, dd

def fade_time (x):
  if x in [ 'g', 'b', 'd', 't', 'p', 'k', '?' ]:
    return 0
  if x in [ 'n', 'm', 'l', 's', 'Z', 'S', 'f', 'r', 'h', 'N', 'z' ]:
    return 25
  if is_v (x):
    return 100
  raise RuntimeError ("missing fade time %s" % x)

def gen_morph():
  morph = []
  idx = 0
  for d in diphones:
    ms = int (d.p1_ms + d.p2_ms)
    fade_in_ms = min (fade_time (d.lyric[0]), int (d.p1_ms))
    fade_out_ms = min (fade_time (d.lyric[1]), int (d.p2_ms))
    assert (ms >= fade_in_ms + fade_out_ms)
    for j in range (fade_in_ms):
      if idx % 2 == 0:
        morph.append (0.5 - j / fade_in_ms * 0.5)
      else:
        morph.append (0.5 + j / fade_in_ms * 0.5)
    for j in range (ms - fade_in_ms - fade_out_ms):
      morph.append (idx % 2)
    for j in range (fade_out_ms):
      if idx % 2 == 0:
        morph.append (j / fade_out_ms * 0.5)
      else:
        morph.append (1 - j / fade_out_ms * 0.5)
    idx += 1
  return morph

def gen_bend ():
  bend = []
  b = 0
  for d in diphones:
    ms = int (d.p1_ms + d.p2_ms)
    bend_done = False
    for j in range (ms):
      frac = j / ms
      #if frac > 0.5 and not bend:
      if (j > d.p1_ms):
        b = d.bend
      bend.append (b)
  return bend

ws1, d1 = gen_wav_source (0)
ws2, d2 = gen_wav_source (1)
morph = gen_morph()
bend = gen_bend()

def L (x):
  if x:
    return x.lyric
  else:
    return "_"

def P (ws, dp):
  if dp:
    return "%f %.3f" % (((ws - dp.pos1) / (dp.pos2 - dp.pos1)), ws)
  else:
    return "-"

#for i in range (len (ws1)):
#  print ("%.0f" % bend[i], L (d1[i]), L (d2[i]), morph[i], P (ws1[i], d1[i]), P (ws2[i], d2[i]), "#D")

for i in range (len (ws1)):
  print ("control 0", ws1[i] / voice_length * 2 - 1)
  print ("control 1", ws2[i] / voice_length * 2 - 1)
  print ("control 2", morph[i] * 2 - 1)
  print ("pitch_expression 0 52 %f" % bend[i])
  #print (ws1[i], ws2[i], morph[i], "#X")
  print ("process 48")
