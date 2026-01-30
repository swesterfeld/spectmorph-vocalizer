#!/usr/bin/env python3

# TODO
#  - detect first note
#  - note end
#  - perfect timing
#  - morph should properly overlap, triphones should extend a bit in the morph range

import sys
import os
import random
import argparse
from math import log2
from dataclasses import dataclass
from utils import time_to_volume, time_to_pos, list_voice_segments

# Set up parser
parser = argparse.ArgumentParser (description = "phomorphdi")
parser.add_argument ("pho", help = "Input .ph file")
parser.add_argument("-s", type=int, help="Optional seed")
args = parser.parse_args()

if args.s is not None:
  print (f"seeding RNG with {args.s}", file=sys.stderr)
  random.seed(args.s)


def load_labels (segment):
  lines_raw = []
  ignore_labels = []
  with open ("voice/" + os.getenv ("VOICE") + "/" + segment + ".sh", "r") as file:
    for line in file:
      line = line.split ("=")
      if (line[0] == "VOICE_MIDI_NOTE"):
        note = int (line[1])

  with open ("voice/" + os.getenv ("VOICE") + "/" + segment + ".txt", "r") as file:
    for line in file:
      line = line.split()
      lines_raw.append ((float (line[0]), line[2].rstrip(":")))

  lines = []
  i = 0
  while i < len (lines_raw):
    F = lines_raw[i]
    if F[1][0] == '.' and i + 1 < len (lines_raw):
      S = lines_raw[i + 1]
      i += 1
      lines.append ((F[0], S[1][0], S[0]))
    else:
      lines.append ((F[0], F[1]))
    i += 1
  return note, lines

lines_dict = dict()

@dataclass
class Segment:
  note: str
  lines: list[str]
  number: int = -1

for segment in list_voice_segments():
  note, lines = load_labels (segment)
  lines_dict[segment] = Segment (note = note, lines = lines)

lines = None

def volume_factor (segment, time_stamp, text):
  assert (is_v (text) and len (text) == 1)
  if text in [ "@", "6" ]:
    target_volume = 0.35
  else:
    target_volume = 0.5

  return target_volume / time_to_volume (segment, time_stamp)

def freq_to_note (freq):
  return 69 + 12 * log2 (freq/440)

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

pho = load_pho (args.pho)

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
  for vv in [ 'a', 'i', 'I', 'e', 'o', 'O', 'u', 'U', 'y', 'Y', '6', '2', '9', '@', 'E' ]:
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

def phone_class (p):
  if p in [ 'a', 'i', 'I', 'e', 'o', 'O', 'u', 'U', 'y', 'Y', '6', '2', '9', '@', 'E' ]:
    return "v"
  if p in  [ "?", "t", "p", "k", "d", "b", "g" ]:
    return "p"
  if p in [ 'n', 'm', 'l', 's', 'Z', 'S', 'f', 'v', 'r', 'h', 'N', 'z', 'j', 'C', 'x' ]:
    return "c"
  if p in [ "_" ]:
    return "_"
  raise RuntimeError ("unknown phone class: %s" % p)

# if we have a vowel in our diphone, use it for volume normalization:
#   _n | al | _ => use a
#   _a | Su | _ => use u
#
# otherwise: use closest vowel
#   _a | st | ro => use a
#   _S | tr | u_ => use u
#   _i | St | u_ => use i (prefer vowel before)
def find_volume_normalization (segment, lines, j):
  best_dist = 10
  best_match = None
  # search for a vowel at or before index j
  for i in range (10):
    candidate = j - i
    if candidate >= 0:
      if lines[candidate][1] in [ "_", "!" ]: # stop searching if we hit rest or !
        break
      if is_v (lines[candidate][1]):
        best_dist = i
        best_match = candidate
        break
  # search for a vowel at or after index j + 1
  for i in range (10):
    if i < best_dist:
      candidate = j + 1 + i
      if candidate + 1 < len (lines):
        if lines[candidate][1] in [ "_", "!" ]: # stop searching if we hit rest or !
          break
        if is_v (lines[candidate][1]):
          best_match = candidate
          break
  if not best_match:
    for i in range (-10, 10):
      if i == 0 or i == 1:
        print (" * ", lines[j + i], file=sys.stderr)
      else:
        print ("   ", lines[j + i], file=sys.stderr)
    raise RuntimeError ("search for volume normalization for diphone failed")
  return volume_factor (segment, (lines[best_match][0] + lines[best_match + 1][0]) / 2, lines[best_match][1])

def lookup_diphone_entry (P1, P2, pho_entry):
  global errors
  possible_matches = []
  for segment in lines_dict:
    lines = lines_dict[segment].lines
    for j in range (len (lines) - 2):
      x = lines[j:j+3]
      if x[0][1] == P1 and x[1][1] == P2:
        vnorm = find_volume_normalization (segment, lines, j)
        possible_matches.append ([segment, vnorm] + x)
  if len (possible_matches) == 0:
    #print ("line %d: missing diphone %s" % (pho[i][-1], P1 + P2))
    errors += [ "%s: missing diphone %s, bar %d, beat %d" % (args.pho, P1 + P2, pho_entry.bar, pho_entry.beat) ]
    return None
  return possible_matches

def lookup_diphone_entry_vv (P1, P2, pho_entry, note):
  global errors
  possible_matches = []
  for segment in lines_dict:
    lines = lines_dict[segment].lines
    for j in range (len (lines) - 1):
      x = lines[j:j+3]
      if x[0][1] == P1 + '_' + P2:
        possible_matches.append ([segment] + x)
  # find best note distance
  distance = 128
  for p in possible_matches:
    distance = min (abs (note - lines_dict[p[0]].note), distance)
  # use only best distance matches
  filtered_matches = []
  for p in possible_matches:
    if abs (note - lines_dict[p[0]].note) <= distance:
      filtered_matches.append (p)
  possible_matches = filtered_matches
  if len (possible_matches) == 0:
    # print ("missing diphone %s" % (P1 + P2))
    errors += [ "%s: missing diphone %s, bar %d, beat %d" % (args.pho, P1 + "_" + P2, pho_entry.bar, pho_entry.beat) ]
    return None
  return possible_matches

items = []

class Item:
  pass

# prepare for melisma:
#  - merge repeated vowels into one
#  - build a list to be able to find the frequency for a given time
def prepare_melisma (pho):
  out = []
  out_f = []
  last = None
  last_f = 130.81
  for i in range (len (pho)):
    pho_entry = pho[i][-1]
    if pho_entry.freq:
      last_f = pho_entry.freq
    if pho[i][0] == "_" and i + 1 < len (pho):
      # for rests, we have no frequency, but we want the end of the last note
      # have the old frequency, and the start of the new note have the new
      # frequency, so we put the frequency jump into the middle of the rest,
      # which usually should be inaudible
      out_f.append ((float (pho[i][1]) / 2, last_f))
      next_f = pho[i + 1][-1].freq
      out_f.append ((float (pho[i][1]) / 2, next_f))
    else:
      out_f.append ((float (pho[i][1]), last_f))

    V_last = V_current = None
    if last and is_v (last[0]):
      V_last = last[0]
      V_last = V_last[0].rstrip (":")
    if last and is_diphthong (last[0]):
      V_last = last[0]

    if is_v (pho[i][0]):
      V_current = pho[i][0]
      V_current = V_current[0].rstrip (":")
    if is_diphthong (pho[i][0]):
      V_current = pho[i][0]

    if last and V_last and V_current and V_last == V_current:
      out[-1][1] = str (float (out[-1][1]) + float (pho[i][1]))
      out[-1][-1].last_diph_frac_time = float (pho[i][1]) / float (out[-1][1])
    else:
      pho[i][-1].last_diph_frac_time = 1
      out.append (pho[i])
    last = pho[i]
  return out, out_f

pho, m_freqs = prepare_melisma (pho)

def print_input_pho (pho):
  t = 0
  for i in range (len (pho)):
    print ("%f\t%f\tinput_pho_%s" % (t, t, pho[i][0]), file=sys.stderr)
    t += float (pho[i][1]) / 1000

print_input_pho (pho)

for i in range (len (pho)):
  pho[i][-1].v_time = 0
  # FIXME: "_" is not really a vowel insertion, but not using insertions here
  # blurs attack/release next to the "_"
  if is_v (pho[i][0]):
    print ("XM", pho[i][0], pho[i][1], file=sys.stderr)
    if float (pho[i][1]) > 200:
      if i == 0:
        pho[i][-1].v_time = float (pho[i][1]) - 50
      else:
        pho[i][-1].v_time = float (pho[i][1]) - 100
      pho[i][1] = "100"
  if is_diphthong (pho[i][0]):
    print ("XM", pho[i][0], pho[i][1], pho[i][-1].last_diph_frac_time, file=sys.stderr)
    if (float (pho[i][1]) > 200):
      pho[i][-1].v_time = float (pho[i][1]) - 100
      pho[i][1] = "100"
    else:
      pho[i][-1].v_time = float (pho[i][1]) / 2
      pho[i][1] = str (pho[i][-1].v_time)
  #if i + 1 < len (pho):
  #  print ("XD", pho[i][0] + pho[i + 1][0], pho[i][1], pho[i + 1][1], file=sys.stderr)

#for i in range (len (pho)):
#  pho[i][1] = str (float (pho[i][1]) - pho[i][-1].v_time)
#  print (">", pho[i][0], pho[i][1], file=sys.stderr)

print ("============================================", file=sys.stderr)
for i in range (len (pho)):
  if pho[i][0] == "_":
    item = Item()
    item.segment = "voice"
    item.pos1 = 0
    item.pos2 = 0.001
    item.type = "M"
    item.volume_factor = 0
    item.ms = pho[i][-1].v_time
    item.lyric = "_"
    items.append (item)
  elif is_v (pho[i][0]) and pho[i][-1].v_time > 0:
    pho_entry = pho[i][-1]
    P1 = pho[i][0]
    P1 = P1[0][0]
    note = freq_to_note (pho_entry.freq)
    print ("M", pho[i][0], round (freq_to_note (pho_entry.freq), 3), file=sys.stderr)
    possible_matchesv = lookup_diphone_entry_vv (P1, P1, pho[i][-1], note)
    if possible_matchesv:
      mv = random.choice (possible_matchesv)
      mseg = mv[0]
      mv = mv[1:]
      pos1 = mv[0][0] # FIXME should be before a_a marker
      pos2 = mv[1][0]
      item = Item()
      item.volume_factor = volume_factor (mseg, mv[0][0], P1)
      item.segment = mseg
      item.pos1 = pos1
      item.pos2 = pos2
      item.type = "M"
      item.ms = pho[i][-1].v_time
      item.lyric = pho[i][0]
      items.append (item)
  elif is_diphthong (pho[i][0]):
    pho_entry = pho[i][-1]
    Vs = diphthong_split (pho[i][0])
    print ("M", Vs, file=sys.stderr)
    note = freq_to_note (pho_entry.freq)
    possible_matches_v = lookup_diphone_entry_vv (Vs[0], Vs[0], pho[i][-1], note)
    possible_matches_d = lookup_diphone_entry_vv (Vs[0], Vs[1], pho[i][-1], note)
    if possible_matches_v and possible_matches_d:
      # FIXME: which is better here: a relative length for the last diphone segment
      # (like pho_entry last_diph_frac_time) or some kind of absolute time?
      time2 = min (pho[i][-1].v_time * pho[i][-1].last_diph_frac_time, 200)
      time1 = pho[i][-1].v_time - time2

      mv = random.choice (possible_matches_v)
      mseg = mv[0]
      mv = mv[1:]
      item = Item()
      item.segment = mseg
      item.pos1 = mv[0][0] # FIXME should be before a_a marker
      item.pos2 = mv[1][0]
      item.volume_factor = volume_factor (mseg, mv[0][0], Vs[0]) # FIXME: could ramp for different volumes for Vs
      item.type = "M"
      item.ms = time1
      item.lyric = Vs[0]
      items.append (item)

      # take the longest diphthong recording available to maximize quality
      md = max (possible_matches_d, key = lambda x: x[2][0] - x[1][0])
      mseg = md[0]
      md = md[1:]

      item = Item()
      item.segment = mseg
      item.pos1 = md[0][0]
      item.pos2 = md[1][0]
      item.volume_factor = volume_factor (mseg, md[0][0], Vs[0]) # FIXME: could ramp for different volumes for Vs
      item.type = "M"
      item.ms = time2
      item.lyric = pho[i][0]
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
      mseg = m[0]
      vnorm = m[1]
      m = m[2:]
      item = Item()
      item.segment = mseg
      item.lyric = P1 + P2
      item.type = "D"
      item.ms = (float (pho[i][1]) + float (pho[i + 1][1])) / 2
      if phone_class (P1) == "p":
        pos1 = m[0][2]
      elif phone_class (P1) == "v":
        pos1 = max ((m[0][0] + m[1][0]) / 2, m[1][0] - 0.150)
      else:
        pos1 = (m[0][0] + m[1][0]) / 2
      if phone_class (P2) == "p":
        pos2 = (m[1][0] + m[1][2]) / 2
      elif phone_class (P2) == "v":
        pos2 = min ((m[1][0] + m[2][0]) / 2, m[1][0] + 0.150)
      elif phone_class (P2) == "_":
        pos2 = min ((m[1][0] + m[2][0]) / 2, m[1][0] + 0.025)
      else:
        pos2 = (m[1][0] + m[2][0]) / 2
      item.pos1 = pos1
      item.pos2 = pos2
      item.volume_factor = vnorm
      items.append (item)

if errors:
  for e in sorted (set (errors)):
    print (e, file=sys.stderr)
  sys.exit (1)

time_stretch = 1
total_ms = 0
for item in items:
  if item.ms > 0:
    compression = (item.pos2 - item.pos1) * 1000 / item.ms
  else:
    compression = 1
  print ("ITEM: %-5s %-5s %7.2f %7.2f %7.2f" % (item.type, item.lyric, item.ms, compression, item.volume_factor), file=sys.stderr)
  if item.ms > 0:
    synlist.append (item)
    print ("%f\t%f\t%s" % (item.pos1, item.pos2, "trace_" + item.lyric), file=sys.stderr)
    print ("%f\t%f\t%s" % (total_ms / 1000 * time_stretch, (total_ms + item.ms) / 1000 * time_stretch, "item_" + item.lyric), file=sys.stderr)
  total_ms += item.ms
print ("TOTAL_MS:", total_ms, file=sys.stderr)

def find_freq (ms):
  elapsed = 0
  for duration, freq in m_freqs:
    last_freq = freq
    if ms < elapsed + duration:
      return freq
    elapsed += duration
  return last_freq

def find_synlist_pos (ms):
  elapsed = 0
  for i in range (len (synlist)):
    item = synlist[i]
    duration = item.ms
    if ms < elapsed + duration:
      if i > 0:
        last_item = synlist[i - 1]
      else:
        last_item = None
      if i < len (synlist) - 1:
        next_item = synlist[i + 1]
      else:
        next_item = None
      return ms - elapsed, item, last_item, next_item
    elapsed += duration
  return None, None, None, None

segment_number = 0
for segment in lines_dict:
  print ("load \"voice/" + os.getenv ("VOICE") + "/" + segment + ".sm\"")
  lines_dict[segment].number = segment_number
  segment_number += 1

def fade_time (x):
  if x in [ 'g', 'b', 'd', 't', 'p', 'k', '?' ]:
    return 0
  if x in [ 'n', 'm', 'l', 's', 'Z', 'S', 'f', 'v', 'r', 'h', 'N', 'z', 'j', 'C', 'x' ]:
    return 25
  if is_v (x):
    return 100
  raise RuntimeError ("missing fade time %s" % x)

def is_insertion (item):
  if item.type == "M" and not is_diphthong (item.lyric):
    return True
  return False

ms = 0
insert_ms_morph = 100
while True:
  pos_ms, item, last_item, next_item = find_synlist_pos (ms)
  if pos_ms is None:
    break

  frac = pos_ms / item.ms
  ct = item.pos1 * (1 - frac) + item.pos2 * frac

  print ("freq", find_freq (ms))

  # TODO: morphing can jump from 0 to 1 or back, which is typically inaudible,
  # but should be fixed anyway
  done = False
  if is_insertion (item) and last_item and item.lyric != "_":
    if item.ms >= 2 * insert_ms_morph:
      if pos_ms < insert_ms_morph:
        morphing = 1 - pos_ms / insert_ms_morph
        x = pos_ms / 1000
        print ("seek", 0, lines_dict[item.segment].number, time_to_pos (item.segment, ct), item.volume_factor)
        print ("seek", 1, lines_dict[last_item.segment].number, time_to_pos (last_item.segment, last_item.pos2 + x), last_item.volume_factor)
        print ("morphing", morphing)
        done = True
      elif next_item and item.ms - pos_ms < insert_ms_morph:
        morphing = 1 - (item.ms - pos_ms) / insert_ms_morph
        x = (item.ms - pos_ms) / 1000
        print ("seek", 0, lines_dict[item.segment].number, time_to_pos (item.segment, ct), item.volume_factor)
        print ("seek", 1, lines_dict[next_item.segment].number, time_to_pos (next_item.segment, next_item.pos1 - x), next_item.volume_factor)
        print ("morphing", morphing)
        done = True
    else:
      # if insertion is not long enough for morphing in and out of the inserted vowel,
      # simply morph end of last segment with start of next segment
      #
      # TODO: maybe not generated an insertion at all for such cases
      a = last_item.pos2 + pos_ms / 1000
      b = next_item.pos1 - (item.ms - pos_ms) / 1000
      morphing = pos_ms / item.ms
      print ("seek", 0, lines_dict[last_item.segment].number, time_to_pos (last_item.segment, a), last_item.volume_factor)
      print ("seek", 1, lines_dict[next_item.segment].number, time_to_pos (next_item.segment, b), next_item.volume_factor)
      print ("morphing", morphing)
      done = True
  if not is_insertion (item):
    # TODO:
    # - is vowel handling reasonable?
    # - diphthong should not use lyric[1]
    fade_in = min (fade_time (item.lyric[0]), item.ms / 2)
    fade_out = min (fade_time (item.lyric[1]), item.ms / 2)
    if last_item and not is_insertion (last_item) and pos_ms < fade_in:
      # morph from last item into this item
      morphing = 0.5 + pos_ms / fade_in / 2
      x = pos_ms / 1000
      print ("seek", 0, lines_dict[last_item.segment].number, time_to_pos (last_item.segment, last_item.pos2 + x), last_item.volume_factor)
      print ("seek", 1, lines_dict[item.segment].number, time_to_pos (item.segment, ct), item.volume_factor)
      print ("morphing", morphing)
      done = True
    elif next_item and not is_insertion (next_item) and item.ms - pos_ms < fade_out:
      # morph from this item into next item
      morphing = 0.5 - (item.ms - pos_ms) / fade_out / 2
      x = (item.ms - pos_ms) / 1000
      print ("seek", 0, lines_dict[item.segment].number, time_to_pos (item.segment, ct), item.volume_factor)
      print ("seek", 1, lines_dict[next_item.segment].number, time_to_pos (next_item.segment, next_item.pos1 - x), next_item.volume_factor)
      print ("morphing", morphing)
      done = True

  if not done:
    print ("seek", 0, lines_dict[item.segment].number, time_to_pos (item.segment, ct), item.volume_factor)
    print ("seek", 1, lines_dict[item.segment].number, time_to_pos (item.segment, ct), item.volume_factor)
    print ("morphing", 0)

  print ("process 48")

  ms += 1 / time_stretch

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
        errors += [ "%s: missing diphone %s, bar %d, beat %d" % (argv[1], P1 + P2, pho_entry.bar, pho_entry.beat) ]
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
