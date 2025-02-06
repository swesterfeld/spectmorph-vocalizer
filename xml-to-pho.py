#!/usr/bin/env python3
from music21 import converter, note, stream, tempo, articulations, dynamics
import random
import sys
import re
from enum import Enum

''' original (for mbrola)
RND_V_p_matrix = [ ("a:", (190, 50, 5, 40, 2)),
                   ("E:", (160, 10, 30, 30, 5)),
                   ("i:", (160, 50, 35, 13, 30)),
                   ("o:", (160, 45, 20, 20, 40)),
                   ("u:", (180, 20, 50, 40, 40)) ]
RND_C = [ "n", "b", "d", "g", "m", "l", "s" ]
RND_V = [ "a:", "E:", "i:", "o:", "u:"]
'''

# for sven.flac
RND_V_p_matrix = [ ("a:", (190, 50, 5 )),
                   ("i:", (160, 50, 35 )),
                   ("o:", (180, 20, 50 )) ]
RND_C = [ "n", "b", "d", "g", "m", "l", "s" ]
RND_V = [ "a:", "i:", "o:" ]


V = [ "i:", "i", "I", "y:", "Y", "u:", "U",
      "e:", "E:", "E", "2:", "9", "o:", "o", "O",
      "a:", "a", "@", "6"]
C = [ ("p", 50), ("b", 50), ("t", 50), ("d", 50), ("k", 50), ("g", 50), ("?", 50),
      ("m", 50), ("n", 50), ("N", 50),
      ("f", 50), ("v", 50), ("s", 50), ("z", 50), ("S", 100), ("Z", 50), ("C", 50), ("j", 50), ("x", 50), ("R", 50), ("h", 50),
      ("l", 50),
      ("r", 50),
      ("w", 50), ("T", 50), ("D", 50) ]

random.seed (10)

history = []
last_v = "a:"
cv_16_skip = 0
def random_cv():
    global last_v
    global history
    while True:
        c = random.choice (RND_C)
        for V_p_candidate in RND_V_p_matrix:
            if V_p_candidate[0] == last_v:
                V_p = V_p_candidate[1]
        v = random.choices (RND_V, V_p)[0]
        if (c,v) not in history[-1:]:
            last_v = v
            history.append ((c, v))
            return c + v

def check_lyric (lyric):
  print (lyric, file=sys.stderr)
  for l in lyric:
    if l == '\n' or l == '\t':
      raise RuntimeError ("failed to process lyric: lyric contains newline: lyric = '%s'" % lyric)
    if not re.match (r'^[a-zA-Z@0-9:?]+$', l):
      raise RuntimeError ("failed to process lyric: lyric contains invalid char: lyric = '%s', char = '%s'" % (lyric, l))

def cvc_split (s):
  check_lyric (s)
  Cs = []
  Cs2 = []
  while True:
    has_c = False
    for c_candidate_pair in C:
      c_candidate = c_candidate_pair[0] # cut length
      if s[0:len(c_candidate)] == c_candidate:
        Cs += s[0:len(c_candidate)]
        s = s[len(c_candidate):]
        has_c = True
        continue
    if not has_c:
      break
  has_v = False
  for v_candidate in V:
    if s[0:len(v_candidate)] == v_candidate:
      v = s[0:len(v_candidate)]
      s = s[len(v_candidate):]
      has_v = True
      break
  if not has_v:
    raise RuntimeError ("phoneme missing: %s" % s)
  while len (s):
    has_cv = False
    for v_candidate in V:
      if s[0:len(v_candidate)] == v_candidate:
        Cs2 += s[0:len(v_candidate)]
        s = s[len(v_candidate):]
        has_cv = True
        continue
    for candidate_pair in C:
      c_candidate = candidate_pair[0] # cut length
      if s[0:len(c_candidate)] == c_candidate:
        Cs2 += s[0:len(c_candidate)]
        s = s[len(c_candidate):]
        has_cv = True
        continue
    if not has_cv:
      raise RuntimeError ("phoneme missing: %s" % s)
  return Cs, v, Cs2

def search_c (c):
  # constify vocals with 50ms
  for v_candidate in V:
    if v_candidate == c:
      return  (c, 50)
  for c_candidate in C:
    if c_candidate[0] == c:
      return c_candidate
  return None

def c_length (Cs):
  length = 0
  for c in Cs:
    c_pair = search_c (c)
    if c_pair is None:
      raise RuntimeError ("%s: consonant missing: %s" % (sys.argv[2], c))
    length += c_pair[1]
  return length

if sys.argv[1] == "txt":
  out = ""
  for l in range (20):
    for i in range (30):
      cv = random_cv()
      out += cv.replace (':', '').lower() + " "
    out += "\n\n\n"
  print (out)
  sys.exit (0)

if sys.argv[1] != "xml":
  print ("use xml-to-pho.py txt or xml-to-pho.py xml <musicxml>")
  sys.exit (1)

# Load the MusicXML file
score = converter.parse (sys.argv[2], format='musicxml')

def set_tempo (quarter_length, tempo):
  global ms_per_beat
  print (";;; SET TEMPO %s" % tempo)
  ms_per_beat = 60000.0 / tempo / quarter_length

# default
set_tempo (1, 120)
volume = 0.55 # mf

last_note = None
last_rest = None

class VolumeState (Enum):
  CONST = 1
  START = 2
  END = 3
  NONE = 4

class Note:
  pass

class Rest:
  pass

# Note -> Note:
#   skip = c_length (note.c_out + next_note.c_in)
# Note -> Rest:
#   skip = 0
#   rest_ms -= note.c_out
def print_note (note, skip):
  print (";;; ACCENT", note.has_accent)
  for c in note.c_in:
    print ("%s %.2f" % (c, c_length ([c])))
  if note.volume_state == VolumeState.CONST:
    print (";;; VOLUME", note.volume)
  if note.volume_state == VolumeState.START:
    print (";;; START_VOLUME", note.volume)
  #if note.volume_state == VolumeState.END:
  #  print (";;; END_VOLUME", note.volume)
  print ("%s %.2f 0 %.2f 100 %.2f" % (note.v, note.ms - skip, note.freq, note.freq))
  for c in note.c_out:
    print ("%s %.2f" % (c, c_length ([c])))
  print (";;; ACCENT", False)
  print()

tempo_change_sounding = []
quarter_offset = 0
cresc = None
dim = None
in_cresc = False
in_dim = False
volume_state = VolumeState.CONST

dynamic_list = []
cresc_list = []
dim_list = []

notes = []

for part in score.parts:
  for element in part.flatten():
    if isinstance (element, dynamics.Dynamic):
      dynamic_list.append (element)
    if isinstance (element, dynamics.Crescendo):
      cresc_list.append (element)
    if isinstance (element, dynamics.Diminuendo):
      dim_list.append (element)

# Extract information from the score
for part in score.parts:
  part_name = part.partName if part.partName else "de2"
  print (";;; VOICE", part_name)
  for element in part.flatten():
    print (";;;", element)
    if isinstance (element, dynamics.Dynamic):
      volume = element.volumeScalar
    if isinstance (element, note.Rest) or isinstance (element, note.Note):
      cresc_found = False
      if not in_cresc:
        for cresc_candidate in cresc_list:
          if element.id == cresc_candidate.getFirst().id:
            print (";;; START CRESC")
            in_cresc = True
            volume_state = VolumeState.START
            cresc = cresc_candidate
      if in_cresc and element.id == cresc.getLast().id:
        print (";;; END CRESC")
        volume_state = VolumeState.END
        in_cresc = False
      dim_found = False
      if not in_dim:
        for dim_candidate in dim_list:
          if element.id == dim_candidate.getFirst().id:
            print (";;; START DIM")
            in_dim = True
            volume_state = VolumeState.START
            dim = dim_candidate
      if in_dim and element.id == dim.getLast().id:
        print (";;; END DIM")
        volume_state = VolumeState.END
        in_dim = False
    if isinstance (element, tempo.MetronomeMark):
      if element.numberSounding:
        tempo_change_sounding += [ element ]
      if (element.number):
        set_tempo (element.referent.quarterLength, element.number)
    qoffset16 = round (quarter_offset * 4)
    if len (tempo_change_sounding) and qoffset16 > round (tempo_change_sounding[0].offset * 4):
      telement = tempo_change_sounding[0]
      set_tempo (telement.referent.quarterLength, telement.numberSounding)
      tempo_change_sounding = tempo_change_sounding[1:]
    print (";;; quarter_offset: ", quarter_offset)
    if isinstance (element, note.Note):
      note_duration_ms = element.duration.quarterLength * ms_per_beat
      quarter_offset += element.duration.quarterLength
      freq = element.pitch.frequency
      # melisma: extend last vowel over new note without lyric
      if (element.lyric is None) and last_note and not last_note.c_out:
        element.lyric = last_note.v
      if element.lyric is None:
        if last_note:
          assert (last_note.freq == freq)
          last_note.ms += note_duration_ms
        else:
          print ("no lyric")
          sys.exit (1)
      else:
        has_accent = False
        has_staccato = False
        for art in element.articulations:
          if art.name == "accent":
            has_accent = True
          if art.name == "staccato":
            has_staccato = True
          print (";;;", art.name)
        lyric = element.lyric
        if lyric == "$":
          for i in range (cv_16_skip):
            random_cv()
          cv_16_skip = 0
          lyric = random_cv()
        lyric = cvc_split (lyric)
        c_in, v, c_out = lyric
        new_note = Note()
        new_note.c_in = c_in
        new_note.v = v
        new_note.c_out = c_out
        new_note.ms = note_duration_ms
        new_note.freq = freq
        new_note.has_accent = has_accent
        new_note.has_staccato = has_staccato
        new_note.volume = volume
        new_note.volume_state = volume_state
        notes.append (new_note)
        last_note = new_note
        '''
        if last_note:
          skip = c_length (last_note.c_out + c_in)
          print_note (last_note, skip)
        if last_rest:
          last_rest -= c_length (c_in)
          while last_rest > 15000:
            print ("_ 10000.00")
            last_rest -= 10000
          print ("_ %.2f\n" % last_rest)
        last_note = Note()
        last_note.c_in = c_in
        last_note.v = v
        last_note.c_out = c_out
        last_note.ms = note_duration_ms
        last_note.freq = freq
        last_note.has_accent = has_accent
        last_note.has_staccato = has_staccato
        last_note.volume = volume
        last_note.volume_state = volume_state
        if volume_state == VolumeState.START:
          volume_state = VolumeState.NONE
        if volume_state == VolumeState.END:
          volume_state = VolumeState.CONST
        '''
        last_rest = None
    if isinstance (element, note.Rest):
      length = element.duration.quarterLength * ms_per_beat
      if not last_rest:
        new_rest = Rest()
        new_rest.length = length
        notes.append (new_rest)
        last_rest = new_rest
      else:
        last_rest.length += length
      quarter_offset += element.duration.quarterLength
      cv_16_skip += round (element.duration.quarterLength * 4)
      last_note = None
      '''
      if last_note:
        skip = 0
        print_note (last_note, skip) FIXME: comment more
        last_rest = length - c_length (last_note.c_out)
        last_note = None
      elif last_rest:
        last_rest += length
      else:
        last_rest = length
      '''

# staccato: replace notes with note-rest (duration 50% each)
notes_with_staccato = []
for note in notes:
  if isinstance (note, Note) and note.has_staccato:
    length = note.ms / 2
    note.ms = length
    notes_with_staccato.append (note)
    rest = Rest()
    rest.length = length
    notes_with_staccato.append (rest)
  else:
    notes_with_staccato.append (note)

notes = notes_with_staccato

# staccato: FIXME: may want to collapse multiple rests into one at this point

last_note = None
for this_note in notes:
  if isinstance (this_note, Note):
    # print ("note: %f %f %s" % (this_note.freq, this_note.ms, this_note.c_in + [ this_note.v ] + this_note.c_out))
    # print ("note: %f %f %s" % (note.freq, note.ms, note.c_in + [ note.v ] + note.c_out))
    if last_note:
      skip = c_length (last_note.c_out + this_note.c_in)
      print_note (last_note, skip)
    last_note = this_note
  else:
    if last_note:
      skip = 0
      print_note (last_note, skip)
      last_note = None
    print ("_ %.2f" % this_note.length)
