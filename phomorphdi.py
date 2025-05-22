#!/usr/bin/env python3

# TODO
#  - detect first note
#  - note end
#  - perfect timing
#  - morph should properly overlap, triphones should extend a bit in the morph range

import sys
import random
from math import log2
from utils import time_to_volume, time_to_control

assert (len (sys.argv) == 3)

voice_length = float (sys.argv[2])

lines = []
ignore_labels = []
with open ("diphone-sven.label", "r") as file:
  for line in file:
    line = line.split()
    if line[2] in ["dh", "bh", "th", "gh", "kh", "ph", "?h" ]:
      ignore_labels.append (line[2])
    else:
      lines.append ((float (line[0]), line[2].rstrip(":")))

if ignore_labels:
  print ("ignore labels", set (ignore_labels), file=sys.stderr)

def volume_factor (time_stamp, text):
  assert (is_v (text) and len (text) == 1)
  if text in [ "@", "6" ]:
    target_volume = 0.35
  else:
    target_volume = 0.5

  return target_volume / time_to_volume (time_stamp)

class PhoEntry:
  pass

def load_pho (filename):
  pho = []
  with open (filename, "r") as file:
    line_number = 1
    bar = 1
    beat = 1
    for line in file:
      def parse_line (line):
        nonlocal line_number
        nonlocal bar, beat
        x = line.split()
        if len (x) > 0:
          if x[0] == "meta":
            if x[1] == "bar_beat":
              bar = int (x[2])
              beat = int (x[3])
          elif x[0][0] != ';':
            pho_entry = PhoEntry()
            pho_entry.bar = bar
            pho_entry.beat = beat
            pho_entry.line_number = line_number
            if x[0] == "_":
              pho_entry.freq = None
            else:
              pho_entry.freq = float (x[2])
            x.append (pho_entry)
            pho.append (x)
        line_number += 1
      parse_line (line)
  # ensure last diphone ends in a break
  if (pho[-1][0] != "_"):
    parse_line ("_ 50")
  return pho

pho = load_pho (sys.argv[1])

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
    s += ' vfact=%.3f' % self.volume_factor
    s += ' startv=%s' % self.startv
    s += ' endv=%s' % self.endv
    s += ' lyric=%s' % self.lyric
    s += '>'
    return s

  def __init__ (self):
    self.volume_factor = 1

def is_v (v):
  for vv in [ 'a', 'i', 'I', 'e', 'o', 'O', 'u', 'U', 'y', 'Y', '6', '2', '@', 'E' ]:
    if v == vv or v == vv + ':':
      return True
  return v == '_'

def diphthong_split (d):
  Vs = d.split ('_')
  if len (Vs) == 2 and all ((is_v (v) and v != '_') for v in Vs):
    return Vs
  return None

def is_diphthong (d):
  return diphthong_split (d) is not None

def vowel_insertion (pho):
  # for long vowels, we use steady state vowel recordings, so that
  #
  # 500 a ...
  # =>
  # 100 a ...
  # 300 a_a ...
  # 100 a ...
  #
  # FIXME: should loop in the synthesis / diphone part, not stretch
  vi_pho = []
  for p in pho:
    if is_v (p[0]) and p[0] != "_" and float (p[1]) > 300:
      vi_pho.append ([p[0], str (100)] + p[2:])
      vi_pho.append ([p[0], str (float (p[1]) - 200)] + p[2:])
      vi_pho.append ([p[0], str (100)] + p[2:])
    else:
      vi_pho.append (p)
  return vi_pho

#pho = vowel_insertion (pho)

def validate_durations (pho):
  l = 1
  for p in pho:
    if float (p[1]) <= 0:
      raise RuntimeError ("pho file contains negative duration %s, line %d" % (p, l))
    l += 1

validate_durations (pho)

errors = []
synlist = []

print ("note_on 0 52 100")

def lookup_diphone_entry (P1, P2, pho_entry):
  global errors
  possible_matches = []
  for j in range (len (lines) - 2):
    x = lines[j:j+3]
    if x[0][1] == P1 and x[1][1] == P2:
      possible_matches.append (x)
  if len (possible_matches) == 0:
    #print ("line %d: missing diphone %s" % (pho[i][-1], P1 + P2))
    errors += [ "%s: missing diphone %s, bar %d, beat %d" % (sys.argv[1], P1 + P2, pho_entry.bar, pho_entry.beat) ]
    return None
  return possible_matches

def lookup_diphone_entry_vv (P1, P2, pho_entry):
  global errors
  possible_matches = []
  for j in range (len (lines) - 1):
    x = lines[j:j+3]
    if x[0][1] == P1 + '_' + P2:
      possible_matches.append (x)
  if len (possible_matches) == 0:
    # print ("missing diphone %s" % (P1 + P2))
    errors += [ "%s: missing diphone %s, bar %d, beat %d" % (sys.argv[1], P1 + P2, pho_entry.bar, pho_entry.beat) ]
    return None
  return possible_matches

items = []
last_f = 130.81

class Item:
  pass

for i in range (len (pho)):
  pho[i][-1].v_time = 0
  if is_v (pho[i][0]):
    print ("XM", pho[i][0], pho[i][1], file=sys.stderr)
    if float (pho[i][1]) > 200:
      pho[i][-1].v_time = float (pho[i][1]) - 100
      pho[i][1] = "100"
  if is_diphthong (pho[i][0]):
    print ("XM", pho[i][0], pho[i][1], file=sys.stderr)
    assert (float (pho[i][1]) > 200)  # FIXME
    pho[i][-1].v_time = float (pho[i][1]) - 100
    pho[i][1] = "100"
  #if i + 1 < len (pho):
  #  print ("XD", pho[i][0] + pho[i + 1][0], pho[i][1], pho[i + 1][1], file=sys.stderr)

#for i in range (len (pho)):
#  pho[i][1] = str (float (pho[i][1]) - pho[i][-1].v_time)
#  print (">", pho[i][0], pho[i][1], file=sys.stderr)

print ("============================================", file=sys.stderr)
for i in range (len (pho)):
  if pho[i][0] == "_":
    item = Item()
    item.pos1 = 0
    item.pos2 = 0.001
    item.type = "M"
    item.volume_factor = 1
    item.ms = pho[i][-1].v_time
    item.lyric = "_"
    item.bend = log2 (last_f / 164.81) * 12
    items.append (item)
  elif is_v (pho[i][0]):
    pho_entry = pho[i][-1]
    P1 = pho[i][0]
    P1 = P1[0][0]
    print ("M", pho[i][0], file=sys.stderr)
    possible_matchesv = lookup_diphone_entry_vv (P1, P1, pho[i][-1])
    if possible_matchesv:
      mv = random.choice (possible_matchesv)
      pos1 = mv[0][0] # FIXME should be before a_a marker
      pos2 = mv[1][0]
      item = Item()
      item.volume_factor = volume_factor (mv[0][0], P1)
      if pho_entry.freq:
        last_f = pho_entry.freq
      item.pos1 = pos1
      item.pos2 = pos2
      item.type = "M"
      item.ms = pho[i][-1].v_time
      item.lyric = pho[i][0]
      item.bend = log2 (last_f / 164.81) * 12
      items.append (item)
  elif is_diphthong (pho[i][0]):
    pho_entry = pho[i][-1]
    Vs = diphthong_split (pho[i][0])
    print ("M", Vs, file=sys.stderr)
    possible_matchesv = lookup_diphone_entry_vv (Vs[0], Vs[1], pho[i][-1])
    if possible_matchesv:
      # take the longest diphthong recording available to maximize quality
      mv = max (possible_matchesv, key = lambda x: x[1][0] - x[0][0])
      item = Item()
      item.pos1 = mv[0][0]
      item.pos2 = mv[1][0]
      item.volume_factor = volume_factor (mv[0][0], Vs[0]) # FIXME: could ramp for different volumes for Vs
      if pho_entry.freq:
        last_f = pho_entry.freq
      item.type = "M"
      item.ms = pho[i][-1].v_time
      item.lyric = pho[i][0]
      item.bend = log2 (last_f / 164.81) * 12
      items.append (item)
  if i + 1 < len (pho):
    P1 = pho[i][0]
    if is_diphthong (P1):
      P1 = diphthong_split (P1)[1]
    if is_v (P1):
      P1 = P1[0][0]

    P2 = pho[i + 1][0]
    if is_diphthong (P2):
      P2 = diphthong_split (P2)[0]
    if is_v (P2):
      P2 = P2[0][0]

    print ("D", P1 + P2, file=sys.stderr)
    pho_entry = pho[i][-1]
    next_pho_entry = pho[i + 1][-1]

    possible_matches = lookup_diphone_entry (P1, P2, pho[i][-1])
    if possible_matches:
      m = random.choice (possible_matches)
      item = Item()
      item.lyric = P1 + P2
      item.type = "D"
      item.ms = (float (pho[i][1]) + float (pho[i + 1][1])) / 2
      pos1 = (m[0][0] + m[1][0]) / 2
      pos2 = (m[1][0] + m[2][0]) / 2
      item.pos1 = pos1
      item.pos2 = pos2
      # volume normalization:
      #  - if we have a vowel in our diphone, we use it for volume normalization
      #  - this does not volume normalize diphones without vowels (such as St),
      #    so it is still important to have a consistent overall volume
      item.volume_factor = 1
      if is_v (P1) and P1 != '_':
        item.volume_factor = volume_factor ((m[0][0] + m[1][0]) / 2, P1)
      if is_v (P2) and P2 != '_':
        item.volume_factor = volume_factor ((m[1][0] + m[2][0]) / 2, P2)
      if pho_entry.freq:
        last_f = pho_entry.freq
      #if next_pho_entry.freq:
      #  last_f = next_pho_entry.freq
      item.bend = log2 (last_f / 164.81) * 12

      items.append (item)

if errors:
  for e in sorted (set (errors)):
    print (e, file=sys.stderr)

total_ms = 0
for item in items:
  print ("ITEM:", item.lyric, item.type, item.ms, file=sys.stderr)
  total_ms += item.ms
  if item.ms > 0:
    synlist.append ((item.pos1, item.pos2, item.ms, item.volume_factor, item.bend))
    print ("%f\t%f\t%s" % (item.pos1, item.pos2, "trace_" + item.lyric), file=sys.stderr)
print ("TOTAL_MS:", total_ms, file=sys.stderr)

phase = 0
ms = 0
ct = synlist[0][0]
sp = 1.0
for i in range (1000 * 1000):
  ratio = (synlist[phase][1] - synlist[phase][0]) * 1000 / synlist[phase][2]
  print ("#", ratio)
  ct += sp / 1000 * ratio
  if ct > synlist[phase][1]:
    phase += 1
    if (phase >= len (synlist)):
      sys.exit (0)
    ct = synlist[phase][0]

  print ("control 0", time_to_control (ct))
  print ("control 1", 0)
  print ("control 2", -1)
  #print (ws1[i], ws2[i], morph[i], "#X")
  print ("pitch_expression 0 52 %f" % synlist[phase][4])
  print ("volume 0", synlist[phase][3])
  print ("process 48")
  # FIXME print ("global_volume", synlist[phase][3])

sys.exit (0)

errors = []
start_ms = 0
last_p2_ms = 0
print ("note_on 0 52 100")
diphones = []
last_f = 130.81
pause_fade_ms = 50
for i in range (len (pho)):
  if i + 1 < len (pho):
    P1 = pho[i][0]
    P2 = pho[i + 1][0]
    if is_v (P1):
      P1 = P1[0][0]
    if is_v (P2):
      P2 = P2[0][0]
    pho_entry = pho[i][-1]
    next_pho_entry = pho[i + 1][-1]
    if P1 == '_' and (float (pho[i][1]) > pause_fade_ms):
      d = Diphone()
      d.start_ms = start_ms
      # FIXME: this is not right if the first note is a rest (as it doesn't get shortened by both sides of the rest)
      d.p1_ms = max (float (pho[i][1]) - pause_fade_ms, 0)
      d.p2_ms = 0
      d.startv = d.endv = False
      d.pos1 = d.pos2 = 0
      d.lyric = '__'
      d.bend = log2 (last_f / 164.81) * 12 # FIXME
      d.silent = True
      diphones.append (d)
    if is_v (P1) and is_v (P2) and P2 != '_' and P1 != '_':
      possible_matches = []
      for j in range (len (lines) - 1):
        x = lines[j:j+3]
        if x[0][1] == P1 + '_' + P2:
          possible_matches.append (x)
      if len (possible_matches) == 0:
        # print ("missing diphone %s" % (P1 + P2))
        errors += [ "%s: missing diphone %s, bar %d, beat %d" % (sys.argv[1], P1 + P2, pho_entry.bar, pho_entry.beat) ]
      else:
        # we have a vowel at start & end, so there is a next frequency (melisma)
        # vowel -> vowel case (melisma)
        last_f = next_pho_entry.freq
        assert (last_f)
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
        d.volume_factor = volume_factor (m[1][0], P1)
        diphones.append (d)
    else:
      possible_matches = []
      for j in range (len (lines) - 2):
        x = lines[j:j+3]
        if x[0][1] == P1 and x[1][1] == P2:
          possible_matches.append (x)
      if len (possible_matches) == 0:
        #print ("line %d: missing diphone %s" % (pho[i][-1], P1 + P2))
        errors += [ "%s: missing diphone %s, bar %d, beat %d" % (sys.argv[1], P1 + P2, pho_entry.bar, pho_entry.beat) ]
      else:
        m = random.choice (possible_matches)
        d = Diphone()
        d.lyric = P1 + P2
        d.start_ms = start_ms
        #print ("%f\t%f\t%s" % (d.start_ms / 1000, d.start_ms / 1000, P1))
        d.p1_ms = float (pho[i][1]) / 2
        d.p2_ms = float (pho[i + 1][1]) / 2
        d.silent = False
        if P1 == '_':
          d.p1_ms = min (d.p1_ms, pause_fade_ms / 2)
        elif P2 == '_':
          d.p2_ms = min (d.p2_ms, pause_fade_ms / 2)
        start_ms += last_p2_ms + d.p1_ms # FIXME: doesn't seem to be the right value
        last_p2_ms = d.p2_ms
        if pho_entry.freq:
          last_f = pho_entry.freq
        if next_pho_entry.freq:
          last_f = next_pho_entry.freq

        # volume normalization:
        #  - if we have a vowel in our diphone, we use it for volume normalization
        #  - this does not volume normalize diphones without vowels (such as St),
        #    so it is still important to have a consistent overall volume
        if is_v (pho[i][0]) and P1 != '_':
          d.volume_factor = volume_factor ((m[0][0] + m[1][0]) / 2, P1)
        if is_v (pho[i + 1][0]) and P2 != '_':
          d.volume_factor = volume_factor ((m[1][0] + m[2][0]) / 2, P2)

        if is_v (pho[i][0]) and P1 != '_':
          d.bend = log2 (last_f / 164.81) * 12
          d.pos1 = max (m[1][0] - 0.2, (m[0][0] + m[1][0]) / 2)
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
          d.pos2 = min (m[1][0] + 0.2, (m[1][0] + m[2][0]) / 2)
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

# for removing zero length diphones from synthesis list; however
# FIXME: the followings steps need to be reimplemented in a way that is sample accurate
# (i.e. support sub-millisecond timing information)
def diphone_ms_not_zero (d):
  ms = int (d.p1_ms + d.p2_ms)
  return ms > 0

for d in diphones:
  if diphone_ms_not_zero (d):
    x = ""
  else:
    x = "*"

  print (d, x, file=sys.stderr)
  # diphone tracing example for audacity
  #if d.lyric in [ "St", "tI", "Il", "Ss", "l_" ]:
  #  print ("%f\t%f\t%s" % (d.pos1, d.pos2, "trace_" + d.lyric), file=sys.stderr)
  #print (t.start_v_ms + t.c_ms + t.end_v_ms, (t.pos2 - t.pos1) * 1000, file=sys.stderr)

diphones = list (filter (diphone_ms_not_zero, diphones))

def gen_wav_source (start):
  pos = []
  vol = []
  dist = []
  dd = []
  idx = 0
  for d in diphones:
    ms = int (d.p1_ms + d.p2_ms)
    for j in range (ms):
      pos.append (0)
      vol.append (1)
      dist.append (10000)
      dd.append (None)
  p = 0
  for d in diphones:
    ms = int (d.p1_ms + d.p2_ms)
    if d.startv == False and d.endv == False:
      stretch_cc = (d.pos2 - d.pos1) * 1000 / ms
    elif d.startv == True and d.endv == True:
      stretch_vv = (d.pos2 - d.pos1) * 1000 / ms
      #print ((d.pos2 - d.pos1) * 1000, ms, stretch_cc, "#P")
    else:
      # if the whole c->v or v->c transition can be played at normal speed, use stretch=1
      # otherwise we want to speed up the transition in order to maintain tempo
      stretch = max ((d.pos2 - d.pos1) * 1000 / ms, 1)
      print (stretch, file=sys.stderr)
    for j in range (-120, ms + 120):
      if idx % 2 == start:
        if d.startv == False and d.endv == True:
          x = d.pos1 + j * 0.001 * stretch
          if x > d.pos2:
            x = d.pos2
        elif d.startv == True and d.endv == False:
          x = d.pos2 - (ms - j) * 0.001 * stretch
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
          vol[p + j] = d.volume_factor
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
  return pos, dd, vol

def fade_time (x):
  if x in [ 'g', 'b', 'd', 't', 'p', 'k', '?' ]:
    return 0
  if x in [ 'n', 'm', 'l', 's', 'Z', 'S', 'f', 'v', 'r', 'h', 'N', 'z', 'j', 'C', 'x' ]:
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

ws1, d1, vol1 = gen_wav_source (0)
ws2, d2, vol2 = gen_wav_source (1)
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
  print ("control 0", time_to_control (ws1[i]))
  print ("control 1", time_to_control (ws2[i]))
  print ("control 2", morph[i] * 2 - 1)
  print ("volume 0", vol1[i])
  print ("volume 1", vol2[i])
  print ("pitch_expression 0 52 %f" % bend[i])
  #print (ws1[i], ws2[i], morph[i], "#X")
  print ("process 48")
