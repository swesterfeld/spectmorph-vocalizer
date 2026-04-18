#!/usr/bin/env python3
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


V = [ "i:", "i", "I", "y:", "y", "Y", "u:", "u", "U",
      "e:", "e", "E:", "E", "2:", "2", "9", "o:", "o", "O",
      "a:", "a", "@", "6",
      "m=", "n=", "l=" ]
C = [ ("p_}", 50), ("t_}", 50), ("k_}", 50),
      ("p", 50), ("b", 50), ("t", 50), ("d", 50), ("k", 50), ("g", 50), ("?", 50),
      ("m", 50), ("n", 50), ("N", 50),
      ("f", 50), ("v", 50), ("s", 50), ("z", 50), ("S", 50), ("Z", 50), ("C", 50), ("j", 50), ("x", 50), ("R", 50), ("h", 50),
      ("l", 50),
      ("r", 50),
      ("w", 50), ("T", 50), ("D", 50) ]

def is_syllabic_consonant (c):
  return c.endswith ("=")

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
    if not re.match (r'^[a-zA-Z@0-9=:?_}]+$', l):
      raise RuntimeError ("failed to process lyric: lyric contains invalid char: lyric = '%s', char = '%s'" % (lyric, l))

def diphthong_split (d):
  Vs = d.split ('_')
  if len (Vs) == 2 and all (v in V for v in Vs):
    return Vs
  return None

def canonical_v (v): # FIXME m_= -> m=
  if v.endswith(':'):
    return v[:-1]
  return v

def cvc_split (s):
  check_lyric (s)
  Cs = []
  Cs2 = []
  while True:
    has_c = False
    for c_candidate_pair in C:
      c_candidate = c_candidate_pair[0] # cut length
      if s[0:len(c_candidate)] == c_candidate and s[len(c_candidate):len(c_candidate)+1] != "=":
        Cs.append (s[0:len(c_candidate)])
        s = s[len(c_candidate):]
        has_c = True
        continue
    if not has_c:
      break
  has_v = False
  for v_candidate in V:
    if s[0:len(v_candidate)] == v_candidate:
      v = canonical_v (s[0:len(v_candidate)])
      s = s[len(v_candidate):]
      has_v = True
      break
  if not has_v:
    raise RuntimeError ("phoneme missing: %s" % s)
  # diphthong matching: vv (optional second vowel)
  for v_candidate in V:
    if s[0:len(v_candidate)] == v_candidate:
      v2 = canonical_v (s[0:len(v_candidate)])
      s = s[len(v_candidate):]
      if is_syllabic_consonant (v) or is_syllabic_consonant (v2):
        raise RuntimeError ("Syllabic consonants should not be used with a vowel in the same syllable.")
      v += "_" + v2
      break
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
        Cs2.append (s[0:len(c_candidate)])
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
  # constify diphthongs with 50ms (should this be 100?)
  if diphthong_split (c):
    return (c, 50)
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
    length += c_pair[1] * 2
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
  print ("use xml-to-pho.py txt or xml-to-pho.py xml <musicxml> [ <debug_notes> ]")
  sys.exit (1)

# Load the MusicXML file
def load_mxparse (filepath):
  """
  Load and parse an mxparse-style text file containing NOTE and REST blocks.

  Parameters:
      filepath (str): Path to the text file.

  Returns:
      list of dict: A list of parsed NOTE and REST entries.
  """
  entries = []
  current_entry = None
  current_type = None

  # Regular expression to capture volume pairs like (0, 80)
  volume_pattern = re.compile(r"\((\d+),\s*(\d+)\)")

  with open (filepath, "r", encoding="utf-8") as file:
    for line in file:
      line = line.strip()

      # Skip empty lines
      if not line:
        continue

      # Detect block types
      if line in {"NOTE", "REST", "TEMPO"}:
        # Save the previous entry
        if current_entry is not None:
          entries.append(current_entry)

        current_type = line
        current_entry = {"type": current_type.lower()}
        continue

      # Parse key-value pairs
      if ":" in line and current_entry is not None:
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()

        if key in {"start", "duration", "divisions"}:
          current_entry[key] = int(value)

        elif key == "volume":
          matches = volume_pattern.findall(value)
          current_entry[key] = [
            (int(t), int(v)) for t, v in matches
          ]

        elif key in {"bpm"}:
          current_entry[key] = float(value)

        else:
          # Handles fields like lyric and pitch
          current_entry[key] = value

  # Append the last parsed entry
  if current_entry is not None:
    entries.append(current_entry)

  return entries

def pitch_to_frequency(pitch: str) -> float:
  """
  Convert a MusicXML pitch string (e.g., 'D3', 'C#4', 'Bb5')
  into its corresponding frequency in Hz.

  Parameters:
      pitch (str): The pitch string in scientific pitch notation.

  Returns:
      float: Frequency in Hertz.
  """
  # Mapping of note names to semitone offsets within an octave
  note_map = {
    "C": 0, "C#": 1, "Db": 1,
    "D": 2, "D#": 3, "Eb": 3,
    "E": 4,
    "F": 5, "F#": 6, "Gb": 6,
    "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10,
    "B": 11
  }

  # Parse the pitch string
  match = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d+)", pitch.strip())
  if not match:
    raise ValueError(f"Invalid pitch format: {pitch}")

  note, accidental, octave = match.groups()
  note_name = (note.upper() + accidental)
  octave = int(octave)

  if note_name not in note_map:
    raise ValueError(f"Invalid note: {note_name}")

  # Compute MIDI note number (C4 = 60)
  midi_number = (octave + 1) * 12 + note_map[note_name]

  # Convert MIDI note to frequency
  frequency = 440.0 * (2 ** ((midi_number - 69) / 12))

  return frequency

score = load_mxparse (sys.argv[2])

if len (sys.argv) > 3:
  debug_notes_file = open (sys.argv[3], "w")
else:
  debug_notes_file = sys.stderr

def set_tempo (quarter_length, tempo):
  global ms_per_beat
  print (";;; SET TEMPO %s" % tempo)
  ms_per_beat = 60000.0 / tempo / quarter_length

# default
set_tempo (1, 120)
volume = 0.55 # mf

last_note = None
last_rest = None

class MelismaState (Enum):
  NONE = 1
  START = 2
  MIDDLE = 3
  END = 4

class VolumeState (Enum):
  CONST = 1
  START = 2
  END = 3
  NONE = 4

class Note:
  pass

class Rest:
  pass

last_note_rest_offset = -1
polyphony_errors = 0
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

for element in score:
  if element["type"] == "tempo":
    set_tempo (element["divisions"], element["bpm"])

# Extract information from the score
for element in score:
  print (";;;", element)
  if element["type"] == "rest" or element["type"] == "note":
    """
    if isinstance (element, music21.tempo.MetronomeMark):
      if element.numberSounding:
        tempo_change_sounding += [ element ]
      if (element.number):
        set_tempo (element.referent.quarterLength, element.number)
    """
    qoffset16 = round (quarter_offset * 4)
    if len (tempo_change_sounding) and qoffset16 > round (tempo_change_sounding[0].offset * 4):
      telement = tempo_change_sounding[0]
      set_tempo (telement.referent.quarterLength, telement.numberSounding)
      tempo_change_sounding = tempo_change_sounding[1:]
    print (";;; quarter_offset: ", quarter_offset)
    if element["type"] == "note":
      """
      if last_note_rest_offset == element:
        print ("polyphony error, bar %d" % element.measureNumber, file=sys.stderr)
        polyphony_errors += 1
      """
      last_note_rest_offset = element["start"]
      note_duration_ms = element["duration"] * ms_per_beat
      quarter_offset += element["duration"]
      freq = pitch_to_frequency (element["pitch"])
      # melisma: extend last vowel over new note without lyric
      if "lyric" not in element and last_note and last_note.freq != freq:
        element["lyric"] = last_note.lyric
        if last_note.melisma_state == MelismaState.NONE:
          last_note.melisma_state = MelismaState.START
          melisma_state = MelismaState.END
        elif last_note.melisma_state == MelismaState.END:
          last_note.melisma_state = MelismaState.MIDDLE
          melisma_state = MelismaState.END
      else:
        melisma_state = MelismaState.NONE
      if "lyric" not in element:
        if last_note:
          assert (last_note.freq == freq)
          last_note.ms += note_duration_ms
        else:
          raise RuntimeError ("no lyric, note at measure measure %d beat %d" % (element.measureNumber, element.beat))
      else:
        has_accent = False
        has_staccato = False
        if "articulation" in element:
          """
          if art.name == "accent":
            has_accent = True
          print (";;;", art.name)
          TODO: support other articulations
          """
          if element["articulation"] == "staccato":
            has_staccato = True
        note = Note()
        lyric = element["lyric"]
        note.lyric = lyric
        if lyric == "$":
          for i in range (cv_16_skip):
            random_cv()
          cv_16_skip = 0
          lyric = random_cv()
        try:
          lyric = cvc_split (lyric)
        except Exception as exception:
          print ("%s, note at measure measure %d beat %d" % (exception, element.measureNumber, element.beat), file=sys.stderr)
          sys.exit (1)
        c_in, v, c_out = lyric
        note.c_in = c_in
        note.v = v
        note.c_out = c_out
        note.ms = note_duration_ms
        note.freq = freq
        note.has_accent = has_accent
        note.has_staccato = has_staccato
        note.volume = element["volume"] # FIXME: melisma
        note.volume_state = volume_state
        note.melisma_state = melisma_state
        """
        note.measure_number = element.measureNumber
        note.beat = element.beat
        TODO: mxmlparse
        """
        note.measure_number = 0
        note.beat = 0
        notes.append (note)
        last_note = note
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
    if element["type"] == "rest":
      """
      if last_note_rest_offset == element.offset:
        print ("polyphony error, bar %d" % element.measureNumber, file=sys.stderr)
        polyphony_errors += 1
      """
      last_note_rest_offset = element["start"]
      length = element["duration"] * ms_per_beat
      if not last_rest:
        new_rest = Rest()
        new_rest.length = length
        notes.append (new_rest)
        last_rest = new_rest
      else:
        last_rest.length += length
      quarter_offset += element["duration"]
      cv_16_skip += round (element["duration"] * 4)
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

if polyphony_errors:
  print ("%d polyphony errors" % polyphony_errors, file=sys.stderr)
  sys.exit (1)

def debug_notes():
  time_ms = 0
  for note in notes:
    if isinstance (note, Note):
      print ("%f\t%f\tN%s" % (time_ms / 1000, time_ms / 1000, "".join (note.c_in + [ note.v ] + note.c_out)), file=debug_notes_file)
      time_ms += note.ms
    elif isinstance (note, Rest):
      print ("%f\t%f\tN_" % (time_ms / 1000, time_ms / 1000), file=debug_notes_file)
      time_ms += note.length
    else:
      raise RuntimeError ("non-note non-rest item in notes?")

debug_notes()

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

notes_melisma = []
for note in notes:
  if isinstance (note, Note) and note.melisma_state == MelismaState.START:
    note.c_out = []
  if isinstance (note, Note) and note.melisma_state == MelismaState.MIDDLE:
    note.c_in = []
    note.c_out = []
  if isinstance (note, Note) and note.melisma_state == MelismaState.END:
    note.c_in = []
  notes_melisma.append (note)

notes = notes_melisma

# staccato: FIXME: may want to collapse multiple rests into one at this point

# append a rest at end of score - this ensures that last note gets printed to pho output
def append_final_rest (notes, length):
  final_rest = Rest()
  final_rest.length = length
  notes.append (final_rest)

append_final_rest (notes, 500)

class RestSegment:
  pass

# rules to compute durations for one note/rest segment
#  - if length of all consonants (Cs) and vowel (v) does not exceed length of segment:
#      shorten vowel, keep consonants at original speed
#  - if length of consonants and vowel exceeds segment length
#      shorten both vowels and consonants to (segment length) to the same length
# returns "vowel length" and "function to compute consonant length from consonant"
def compute_cv_times (Cs, v, ms):
  # use the same minimum length for rests and vowel "a"
  if v == "_":
    v = "a"
  if c_length (Cs + [ v ]) > ms:
    VL = ms / (len (Cs) + 1)
    CL = lambda x : VL
  else:
    VL = ms - c_length (Cs)
    CL = lambda x : c_length ([x])
  return VL, CL

def volume_to_percent_str (volume):
  last_d = volume[-1][0]
  return " ".join (
    "%.2f %.2f" % (d / last_d * 100, vol)
    for d, vol in volume
  )

syllable_counter = 0
syllables = []

def append_note (note, next_note):
  global syllable_counter
  Cs = note.c_out + (next_note.c_in if next_note else [])
  VL, CL = compute_cv_times (Cs, note.v, note.ms)

  syllables.append ((syllable_counter, note.v, VL, note))
  # print ("%s %.2f %.2f %d %s" % (note.v, VL, note.freq, syllable_counter, volume_to_ms (note.volume)))
  for c in note.c_out:
    #print ("%s %.2f %.2f %d %s" % (c, CL (c), note.freq, syllable_counter, volume_to_ms (note.volume)))
    syllables.append ((syllable_counter, c, CL (c), note))
  print()
  syllable_counter += 1
  if next_note:
    print ("meta bar_beat %d %d" % (note.measure_number, note.beat))
    for c in next_note.c_in:
      #print ("%s %.2f %.2f %d %s" % (c, CL (c), next_note.freq, syllable_counter, volume_to_ms (next_note.volume)))
      syllables.append ((syllable_counter, c, CL (c), next_note))

def append_note_v (note):
  #print ("%s %.2f %.2f %d %s" % (note.v, note.ms, note.freq, syllable_counter, volume_to_ms (note.volume)))
  syllables.append ((syllable_counter, note.v, note.ms, note))

def append_rest (rest, next_note):
  global syllable_counter
  Cs = rest.c_start + (next_note.c_in if next_note else [])
  VL, CL = compute_cv_times (Cs, "_", rest.length)

  for c in rest.c_start:
    #print ("%s %.2f %.2f %d" % (c, CL (c), rest.start_freq, syllable_counter))
    syllables.append ((syllable_counter, c, CL (c), rest.start_freq))
  if rest:
    syllable_counter += 1
    #print ("_ %.2f" % VL)
    syllables.append ((syllable_counter, "_", VL))
  syllable_counter += 1
  if next_note:
    for c in next_note.c_in:
      syllables.append ((syllable_counter, c, CL (c), note))

last_note = None
last_rest = None
for note in notes:
  if isinstance (note, Note):
    if last_note:
      append_note (last_note, note)
    if last_rest:
      append_rest (last_rest, note)
      last_rest = None
    last_note = note
  else:
    if last_note:
      append_note_v (last_note)
      last_rest = RestSegment()
      last_rest.c_start = last_note.c_out
      last_rest.length = note.length
      last_rest.start_freq = last_note.freq
      last_note = None
    elif last_rest:
      last_rest.length += note.length
    else:
      last_rest = RestSegment()
      last_rest.c_start = []
      last_rest.start_freq = 0
      last_rest.length = note.length

# we ensure that the last item in notes is always a rest
assert (last_rest)
append_rest (last_rest, None)

def syllables_to_pho():
  s_len = 0
  s_nr = syllables[0][0]
  s_ms = 0
  s_volume = None
  s_current = []
  for s in syllables:
    if s[0] != s_nr:
      print(";;; @", s_ms)
      if s_volume:
        volume_percent_str = volume_to_percent_str (s_volume)
        print ("meta dynamic", s_nr, volume_percent_str)

      s_ms_elapsed = 0
      for sc in s_current:
        s_ms_elapsed_2 = s_ms_elapsed + sc[2]
        if sc[1] == "_":
          print ("%s %.2f %d" % (sc[1], sc[2], sc[0]))
        elif isinstance (sc[3], float):
          print ("%s %.2f %.2f %s" % (sc[1], sc[2], sc[3], sc[0]))
        else:
          print ("%s %.2f %.2f %s" % (sc[1], sc[2], sc[3].freq, sc[0]))
        s_ms_elapsed += sc[2]

      print()
      s_ms = 0
      s_nr = s[0]
      s_volume = None
      s_current = []
    if (s[1] == "_"):
      s_current.append (s)
    else:
      s_current.append (s)
      if isinstance (s[3], Note):
        s_volume = s[3].volume
      s_ms += s[2]

syllables_to_pho()
