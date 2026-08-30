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
parser.add_argument("--items", type=str, help="Item file")
parser.add_argument("--trace", type=str, help="Trace file")
parser.add_argument("--input-pho", type=str, help="Input pho file")
args = parser.parse_args()

if args.s is not None:
  print (f"seeding RNG with {args.s}", file=sys.stderr)
  random.seed(args.s)

if args.items is not None:
  item_file = open (args.items, "w")
else:
  item_file = sys.stderr

if args.trace is not None:
  trace_file = open (args.trace, "w")
else:
  trace_file = sys.stderr

if args.input_pho is not None:
  input_pho_file = open (args.input_pho, "w")
else:
  input_pho_file = sys.stderr

def is_non_released (x):
  return x in [ "p_}", "t_}", "k_}" ]

def load_labels (segment):
  lines_raw = []
  ignore_labels = []
  properties = {}
  with open ("voice/" + os.getenv ("VOICE") + "/" + segment + ".sh", "r") as file:
    for line in file:
      key, value = line.strip().split ("=", 1)
      properties[key] = value

  with open ("voice/" + os.getenv ("VOICE") + "/" + segment + ".txt", "r") as file:
    for line in file:
      line = line.split()
      lines_raw.append ((float (line[0]), line[2].rstrip(":")))

  lines = []
  i = 0
  while i < len (lines_raw):
    F = lines_raw[i]
    if F[1][0] == '.' and i + 1 < len (lines_raw) and is_non_released (lines_raw[i + 1][1]):
      lines.append ((F[0], "!"))
      i += 1
      F = lines_raw[i]
      lines.append ((F[0], F[1]))
    elif F[1][0] == '.' and i + 1 < len (lines_raw):
      S = lines_raw[i + 1]
      i += 1
      lines.append ((F[0], S[1][0], S[0]))
    else:
      lines.append ((F[0], F[1]))
    i += 1
  return properties, lines

lines_dict = dict()

@dataclass
class Segment:
  note: int
  lines: list[str]
  properties: dict
  number: int = -1

for segment in list_voice_segments():
  properties, lines = load_labels (segment)
  note = int (properties["VOICE_MIDI_NOTE"])
  lines_dict[segment] = Segment (note = note, lines = lines, properties = properties)

lines = None

def volume_factor_syllabic (segment, time_stamp):
  target_volume = 0.25
  return target_volume / time_to_volume (segment, time_stamp)

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
  def __init__ (self):
    self.syl_entries = []

# TODO: could merge
dynamic_dict = {}
accent_dict = {}
sfz_dict = {}

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
            elif x[1] == "dynamic":
              index = int (x[2])
              values = list (map (float, x[3:]))
              assert (len (values) % 2) == 0
              points = list (zip (values[0::2], values[1::2]))
              dynamic_dict[index] = points
            elif x[1] == "accent":
              index = int (x[2])
              accent_dict[index] = True
            elif x[1] == "sfz":
              index = int (x[2])
              sfz_dict[index] = True
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
    parse_line ("_ 50 %d" % (int (pho[-1][-2]) + 1))
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


def is_v (v):
  for vv in [ 'a', 'i', 'I', 'e', 'o', 'O', 'u', 'U', 'y', 'Y', '6', '2', '9', '@', 'E', 'm=', 'n=', 'l=' ]:
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
  if is_non_released (p):
    return "n"
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
    errors += [ "%s: missing diphone %s, bar %d, beat %d" % (args.pho, P1 + " " + P2, pho_entry.bar, pho_entry.beat) ]
    return None
  return possible_matches

def strip_syllabic_postfix (P):
  return P.rstrip ("=")

def lookup_diphone_entry_vv (P1, P2, pho_entry, note):
  P1 = strip_syllabic_postfix (P1)
  P2 = strip_syllabic_postfix (P2)
  global errors
  possible_matches = []
  for segment in lines_dict:
    lines = lines_dict[segment].lines
    for j in range (len (lines) - 1):
      x = lines[j:j+3]
      if x[0][1] == P1 + '_' + P2:
        voice_dynamic = lines_dict[segment].properties.get ("VOICE_DYNAMIC")
        want_dynamic = os.getenv ("DYNAMIC")
        if P1 == P2 and want_dynamic:
          if want_dynamic == voice_dynamic:
            print ("selected dynamic %s for %s_%s" % (want_dynamic, P1, P2), file=sys.stderr)
            possible_matches.append ([segment] + x)
        elif not voice_dynamic:
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
  total_ms = 0
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
      out[-1][-1].syl_entries.append ((int (pho[i][-2]), total_ms))
    else:
      pho[i][-1].last_diph_frac_time = 1
      out.append (pho[i])
    total_ms += float (pho[i][1])
    last = pho[i]
  return out, out_f

pho, m_freqs = prepare_melisma (pho)

def print_input_pho (pho):
  t = 0
  for i in range (len (pho)):
    print ("%f\t%f\tP%s" % (t, t, pho[i][0]), file=input_pho_file)
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

def get_total_ms (items):
  total_ms = 0
  for item in items:
    total_ms += item.ms
  return total_ms

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
      if P1.endswith ("="):
        item.volume_factor = volume_factor_syllabic (mseg, mv[0][0])
      else:
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
    if is_non_released (P2):
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
      elif phone_class (P1) == "n":
        pos1 = m[0][0]
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
      if pho[i][-2] != pho[i + 1][-2]:
        syl_entry_is_present = any (x[0] == int (pho[i + 1][-2]) for x in pho_entry.syl_entries)
        if not syl_entry_is_present:
          pho_entry.syl_entries.append ((int (pho[i + 1][-2]), item.ms + get_total_ms (items)))

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
    print ("%f\t%f\t%s" % (item.pos1, item.pos2, "trace_" + item.lyric), file=trace_file)
    print ("%f\t%f\t%s" % (total_ms / 1000 * time_stretch, (total_ms + item.ms) / 1000 * time_stretch, "I" + item.lyric), file=item_file)
  total_ms += item.ms
print ("TOTAL_MS:", total_ms, file=sys.stderr)

def build_volume_envelope():
  syl_list = []
  for p in pho:
    syl_list += p[-1].syl_entries

  volume_envelope = []
  for i in range (len (syl_list) - 1):
    if syl_list[i][0] + 1 == syl_list[i + 1][0] and syl_list[i][0] in dynamic_dict:
      for syl_pt in dynamic_dict[syl_list[i][0]]:
        frac = syl_pt[0] / 100
        volume_envelope.append (((syl_list[i][1] * (1 - frac) + syl_list[i + 1][1] * frac), syl_pt[1]))

  return volume_envelope

volume_envelope = build_volume_envelope()

def build_sfz_envelope():
  syl_list = []
  for p in pho:
    syl_list += p[-1].syl_entries

  sfz_envelope = []
  for i in range (len (syl_list) - 1):
    if syl_list[i][0] + 1 == syl_list[i + 1][0] and syl_list[i][0] in sfz_dict:
      sfz_envelope.append ((syl_list[i][1], syl_list[i + 1][1]))

  return sfz_envelope

sfz_envelope = build_sfz_envelope()

def build_accent_envelope():
  syl_list = []
  for p in pho:
    syl_list += p[-1].syl_entries

  accent_envelope = []
  for i in range (len (syl_list) - 1):
    if syl_list[i][0] + 1 == syl_list[i + 1][0] and syl_list[i][0] in accent_dict:
      len_ms = syl_list[i + 1][1] - syl_list[i][1]
      # TODO: may want to have more sophisticated length for note length > 250 and length < 1000
      # TODO: ramp into accent
      max_len = min (500, len_ms)
      end_ms = min (syl_list[i][1] + max_len, syl_list[i + 1][1])
      accent_envelope.append ((syl_list[i][1], end_ms))

  return accent_envelope

accent_envelope = build_accent_envelope()

def find_accent (ms):
  for ae in accent_envelope:
    t0_ms = ae[0]
    t1_ms = ae[1]
    if t0_ms <= ms <= t1_ms:
      return min (24 - 24 * (ms - t0_ms) / (t1_ms - t0_ms), 12)
  return 0

def find_sfz_factor (ms):
  def ramp (start, stop, frac):
    print ("ramp", start, stop, frac, start * (1 - frac) + stop * frac, file=sys.stderr)
    return start * (1 - frac) + stop * frac
  sfz_factor = 3
  for sfz in sfz_envelope:
    t0_ms = sfz[0]
    t1_ms = sfz[1]
    duration_ms = sfz[1] - sfz[0]
    if duration_ms > 200:
      attack_ms = 100
      decay_ms = min (500, duration_ms - attack_ms)
    else:
      attack_ms = duration_ms / 2
      decay_ms = duration_ms / 2
    if t0_ms <= ms <= t0_ms + attack_ms:
      frac = (ms - t0_ms) / attack_ms
      return ramp (1, sfz_factor, frac)
    if t0_ms + attack_ms <= ms <= t0_ms + attack_ms + decay_ms:
      frac = (ms - attack_ms - t0_ms) / decay_ms
      return ramp (sfz_factor, 1, frac)
  return 1

def find_volume_midi (ms):
  for i in range (len (volume_envelope) - 1):
    t0_ms, value0 = volume_envelope[i]
    t1_ms, value1 = volume_envelope[i + 1]

    if t0_ms <= ms <= t1_ms:
      if t0_ms == t1_ms:
        return value0
      else:
        frac = (ms - t0_ms) / (t1_ms - t0_ms)
        return value0 + frac * (value1 - value0)
  if ms < volume_envelope[0][0]:
    return volume_envelope[0][1]
  else:
    return volume_envelope[-1][1]

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
    return 50
  raise RuntimeError ("missing fade time %s" % x)

def is_insertion (item):
  if item.type == "M" and not is_diphthong (item.lyric):
    return True
  return False

def item_to_pos (slot, item, pos_ms, volume_factor):
  if is_insertion (item) and item.lyric != "_":
    # TODO: could start at random point in time
    # ping pong loop for the insertion
    loop_len_ms = int ((item.pos2 - item.pos1) * 1000)
    assert (loop_len_ms > 0)
    ping_pong_len_ms = loop_len_ms * 2
    ping_pong_pos_ms = int (pos_ms) % ping_pong_len_ms
    if ping_pong_pos_ms < loop_len_ms:
      # ping part of the ping-pong loop (forward)
      ct = item.pos1 + ping_pong_pos_ms / 1000
    else:
      # pong part of the ping-pong loop (backward)
      ct = item.pos2 - (ping_pong_pos_ms - loop_len_ms) / 1000
  else:
    frac = pos_ms / item.ms
    ct = item.pos1 * (1 - frac) + item.pos2 * frac
  print ("seek", slot, lines_dict[item.segment].number, time_to_pos (item.segment, ct), item.volume_factor * volume_factor)

ms = 0
while True:
  pos_ms, item, last_item, next_item = find_synlist_pos (ms)
  if pos_ms is None:
    break

  print ("high-shelf-gain ", find_accent (ms))

  print ("freq", find_freq (ms))

  volume_midi = find_volume_midi (ms)
  volume_factor = (volume_midi / 127) * (volume_midi / 127) * find_sfz_factor (ms)

  # TODO: morphing can jump from 0 to 1 or back, which is typically inaudible,
  # but should be fixed anyway
  done = False
  if is_insertion (item):
    fade_in = 50
    fade_out = 50
  else:
    # TODO:
    # - is vowel handling reasonable?
    # - diphthong should not use lyric[1]
    fade_in = min (fade_time (item.lyric[0]), item.ms / 2)
    fade_out = min (fade_time (item.lyric[1]), item.ms / 2)

  if last_item and pos_ms < fade_in:
    # morph from last item into this item
    morphing = 0.5 + pos_ms / fade_in / 2
    item_to_pos (0, last_item, last_item.ms + pos_ms, volume_factor)
    item_to_pos (1, item, pos_ms, volume_factor)
    print ("morphing", morphing)
    done = True
  if next_item and item.ms - pos_ms < fade_out:
    # morph from this item into next item
    morphing = 0.5 - (item.ms - pos_ms) / fade_out / 2
    item_to_pos (0, item, pos_ms, volume_factor)
    item_to_pos (1, next_item, pos_ms - item.ms, volume_factor)
    print ("morphing", morphing)
    done = True

  if not done:
    item_to_pos (0, item, pos_ms, volume_factor)
    item_to_pos (1, item, pos_ms, volume_factor)
    print ("morphing", 0)

  frac = pos_ms / item.ms
  ct = item.pos1 * (1 - frac) + item.pos2 * frac
  print ("label \"%s:%.3f\"" % (item.lyric, ct))
  print ("process 48")

  ms += 1 / time_stretch
