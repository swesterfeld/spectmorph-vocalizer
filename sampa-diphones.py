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

line = 1
with open (sys.argv[1], newline="", encoding="utf-8") as f:
  reader = csv.reader (f, delimiter=";")
  for row in reader:
    if line >= 3: # skip header
      for diphone in row[1:]:
        diphone = diphone.strip("[]")
        if diphone != "":
          print (convert (diphone[0]) + convert (diphone[1]))
    line += 1
