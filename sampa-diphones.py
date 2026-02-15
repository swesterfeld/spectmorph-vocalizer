#!/usr/bin/env python3

import csv
import sys

ipa_to_sampa = {
  "p": "p",
  "b": "b",
  "t": "t",
  "d": "d",
  "k": "k",
  "g": "g",
  "ɡ": "g",
  "ʔ": "?",
  "m": "m",
  "n": "n",
  "ŋ": "N",
  "f": "f",
  "v": "v",
  "s": "s",
  "z": "z",
  "ʃ": "S",
  "ʒ": "Z",
  "ç": "C",
  "j": "j",
  "x": "x",
  "χ": "x",
  "ʁ": "r", # not correct
  "h": "h",
  "r": "r",
  "ʀ": "R",
  "R": "R",
  "l": "l",
  "i": "i",
  "ɪ": "I",
  "y": "y",
  "ʏ": "Y",
  "e": "e",
  "ɛ": "E",
  "ø": "2",
  "œ": "9",
  "a": "a",
  "u": "u",
  "ʊ": "U",
  "o": "o",
  "ɔ": "O",
  "ə": "@",
  "ɐ": "6",
  "_": "_" # not really sampa
  # Add more as needed
}

def convert (char):
  conv = ipa_to_sampa.get (char)
  return conv

def is_v (v):
  return v in [ 'a', 'i', 'I', 'e', 'o', 'O', 'u', 'U', 'y', 'Y', '6', '2', '9', '@', 'E' ]

if sys.argv[1] == "diphones":
  line = 1
  with open (sys.argv[2], newline="", encoding="utf-8") as f:
    reader = csv.reader (f, delimiter=";")
    for row in reader:
      if line >= 3: # skip header
        for diphone in row[1:]:
          diphone = diphone.strip("[]")
          if diphone != "":
            a = convert (diphone[0])
            b = convert (diphone[1])
            if is_v (a) and is_v (b): # diphthong
              print (a + "_" + b)
            else:
              print (a + " " + b)
      line += 1

# sampa-diphones.py hiatus diphones-german-hiatus.csv > diphones-german-hiatus-possible.txt
# sampa-diphones.py no-hiatus diphones-german-hiatus.csv > diphones-german-hiatus-impossible.txt
if sys.argv[1] in [ "hiatus", "no-hiatus" ]:
  line = 1
  with open (sys.argv[2], newline="", encoding="utf-8") as f:
    reader = csv.reader (f, delimiter=";")
    for row in reader:
      if line == 1:
        header = row
      else:
        for x in range (1, len (row)):
          diphone = header[x] + row[0]
          diphone = diphone.strip("[]")
          a = convert (diphone[0])
          b = convert (diphone[1])
          assert (is_v (a) and is_v (b))
          if sys.argv[1] == "hiatus":
            if (row[x] != ""):
              print (a + " " + b) # list possible hiatus entries
          else:
            if (row[x] == ""):
              print (a + " " + b) # list impossible hiatus entries
      line += 1
