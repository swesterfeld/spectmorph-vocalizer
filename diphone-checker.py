#!/usr/bin/env python3

import sys
import re

def is_v (v):
  return v in [ 'a', 'i', 'I', 'e', 'o', 'O', 'u', 'U', 'y', 'Y', '6', '2', '9', '@', 'E' ]

import re

def validate_diphone(s: str) -> bool:
  s1 = s.split ("_")
  if len (s1) == 2 and is_v (s1[0]) and is_v (s1[1]):
    return True

  pattern = r'^(?:[\w@?] [\w@?]|\w_\} [\w?])$'
  return bool(re.match(pattern, s))

def load_want_diphones (filename):
  want_diphones = []
  with open (filename, "r") as file:
    for line in file:
      line = line.strip()
      assert validate_diphone (line)
      want_diphones.append (line)
  return want_diphones

def load_wordlist (filename):
  wordlist = []
  with open (filename, "r") as file:
    for line in file:
      re_match = re.match (r'''([-'.,\w\(\) ]+):[ \t]+([\w@?_ ]+)$''', line, re.UNICODE)
      if not re_match:
        raise RuntimeError ("%s: line %s doesn't match" % (filename, line))

      letters = re_match.groups()[1]
      letters = letters.split()

      normalized_letters = []
      for l in letters:
        if l == "dZ":
          normalized_letters.extend (["d", "Z"])
        elif l == "pf":
          normalized_letters.extend (["p", "f"])
        elif l == "ts":
          normalized_letters.extend (["t", "s"])
        elif l == "tS":
          normalized_letters.extend (["t", "S"])
        else:
          normalized_letters.append (l)
      letters = normalized_letters

      for l in letters:
        if len (l) != 1 and len (l) != 3:
          raise RuntimeError ("bad sampa: %s" % l)

      # every word starts with silence and ends with silence
      # (irgnore word start/end for diphthongs though)
      if len (letters[0]) == 1:
        letters = [ "_" ] + letters
      if len (letters[-1]) == 1:
        letters = letters + [ "_" ]
      diphones = []

      for i in range (len (letters)):
        if i + 1 < len (letters) and len (letters[i]) == 1 and len (letters[i+1]) == 1:
          diphones.append (letters[i] + " " + letters[i+1])
        if len (letters[i]) == 3 and i > 0 and i < len (letters) - 1 and letters[i] != '?':
          # diphthong, like a_U
          # only usable if in the middle of a word
          # no ? at start
          diphones.append (letters[i])
      wordlist.append ((re_match.groups()[0], re_match.groups()[1], diphones))
  return wordlist

if sys.argv[1] == "gen-script":  # gen-script <want-diphones> <wordlist>
  want_diphones = load_want_diphones (sys.argv[2])
  have_diphones = []

  wordlist = load_wordlist (sys.argv[3])

  while True:
    best_word = None
    best_score = 0
    best_new_diphones = None
    for word in wordlist:
      score = 0
      new_diphones = []
      if len (word[1]) > 2 and len (word[1]) < 20:
        for pair in word[2]:
          if not pair in have_diphones:
            if not pair in new_diphones:
              if pair in want_diphones:
                score += 1
                new_diphones.append (pair)
      if len (word[1]) > 10 and new_diphones:
        score += 10
      score -= len (word[1]) / 20
      if score > best_score:
        best_score = score
        best_word = word
        best_new_diphones = new_diphones

    if best_word is None:
      break

    print ("%-30s%s" % (best_word[0] + ":", best_word[1]), flush = True)
    #print ("%.2f" % best_score, best_new_diphones, len (have_diphones), len (want_diphones))
    #print ()
    have_diphones += best_new_diphones

  for d in want_diphones:
    if not d in have_diphones:
      print ("%s: missing." % d)
  sys.exit (0)

if sys.argv[1] == "test-script": # <want-diphones> <script>...
  want_diphones = load_want_diphones (sys.argv[2])
  have_diphones = []
  wordlist = []
  for i in range (3, len (sys.argv)):
    wordlist_part = load_wordlist (sys.argv[i])
    wordlist += wordlist_part
  for word in wordlist:
    print ("%-30s%s" % (word[0] + ":", word[1]))
    new_diphones = []
    for pair in word[2]:
      if not pair in have_diphones:
        if not pair in new_diphones:
          if pair in want_diphones:
            new_diphones.append (pair)
    print ("%-30s%s" % ("new diphones:", ", ".join (new_diphones)))
    print ()
    have_diphones += new_diphones

  for d in want_diphones:
    if d in have_diphones:
      print ("%s: done." % d)

  for d in want_diphones:
    if not d in have_diphones:
      print ("%s: missing." % d)

def diphthong_split (d):
  Vs = d.split ('_')
  if len (Vs) == 2 and all ((is_v (v) and v != '_') for v in Vs):
    return Vs
  return None

if sys.argv[1] == "wordlist-diphone-list":
  wordlist = load_wordlist (sys.argv[2])
  possible_diphones_list = load_want_diphones ("diphones-german-possible.txt") + load_want_diphones ("diphones-german-hiatus-possible.txt")
  possible_diphones = set(possible_diphones_list)
  printed_diphones = set()

  for w in wordlist:
    phones = w[2]
    for d in phones:
      if not d in possible_diphones and not d in printed_diphones:
        printed_diphones.add (d)
        print ("##############", d)
        print (w)

if sys.argv[1] == "wordlist-diphone-impossible-check":
  wordlist = load_wordlist (sys.argv[2])
  impossible_diphones_list = load_want_diphones ("diphones-german-impossible.txt") + load_want_diphones ("diphones-german-hiatus-impossible.txt")
  impossible_diphones = set (impossible_diphones_list)
  printed_diphones = set()

  for w in wordlist:
    phones = w[2]
    for d in phones:
      if d in impossible_diphones and not d in printed_diphones and not "r" in d:
        printed_diphones.add (d)
        print ("##############", d)
        print (w)
