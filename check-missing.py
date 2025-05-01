#!/usr/bin/env python3

import sys
import re

want_diphones = []
with open (sys.argv[1], "r") as file:
  for line in file:
    line = line.strip()
    assert (len (line) == 2)
    want_diphones.append (line)

have_diphones = []
with open (sys.argv[2], "r") as file:
  for line in file:
    re_match = re.match (r'([\w ]+):[ \t]+([\w@?_ ]+)$', line, re.UNICODE)
    if not re_match:
        raise RuntimeError ("line %s doesn't match" % line)
    print ("%-30s%s" % (re_match.groups()[0] + ":", re_match.groups()[1]))
    letters = re_match.groups()[1]
    letters = letters.split()
    pairs = [letters[i] + letters[i+1] for i in range (len (letters) - 1)]
    new_diphones = []
    for pair in pairs:
      if not pair in have_diphones:
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
