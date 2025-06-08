#!/usr/bin/env python3
import json
import sys
import re

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
  "ʀ": "r", # not correct
  "l": "l",
  "p͡f": "pf",
  "t͡s": "ts",
  "tʃ": "tS",
  "t͡ʃ": "tS",
  "dʒ": "dZ",
  "d͡ʒ": "dZ",
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
  "aʊ̯": "a_U",
  "ɔɪ̯": "O_I",
  "ɔʏ̯": "O_Y",
  "aɪ̯": "a_I",
  "iɐ̯" : "i_6",
  "yɐ̯" : "y_6",
  "ʏɐ̯" : "Y_6",
  "ɪɐ̯" : "I_6",
  "i̯o" : "i_o",
  "ɪ̯o" : "I_o",
  "i̯e" : "i_e",
  "eɐ̯" : "e_6",
  "øɐ̯" : "2_6",
  "ɛɐ̯" : "E_6",
  "œɐ̯" : "9_6",
  "aɐ̯": "a_6",
  "uɐ̯" : "u_6",
  "ʊɐ̯" : "U_6",
  "oɐ̯" : "o_6",
  "ɔɐ̯" : "O_6",

  # Add more as needed
}

ALL = 0
FAIL = 0
def convert (char):
  conv = ipa_to_sampa.get (char)
  return conv

state = 0
word_string = ""
# Load JSON file
with open('x.json', 'r') as file:
  for line in file:
    line = line.rstrip ("\n")
    if line == '{':
      state = 1
    if state == 1:
      word_string += line
    if line == '}':
      data = json.loads (word_string)
      try:
        if data["pos"] == "noun":
          for i in data["sounds"]:
            try:
              xipa = i["ipa"]
              match = re.fullmatch (r"/([^/]+)/", xipa)
              if match:
                ALL += 1
                print ("ALL = %d FAIL = %d COV %f" % (ALL, FAIL, (ALL - FAIL) / ALL * 100))
                print (":::::::", data["word"])
                ipa = match.group (1)
                print (ipa)
                ipa = ipa.replace ("(ː)", "")
                ipa = ipa.replace ("(ˌ)", "")
                ipa = ipa.replace ("(p)", "p")
                ipa = ipa.replace ("(t)", "t")
                ipa = ipa.replace ("tʰ", "t")
                ipa = ipa.replace ("(d)", "d")
                ipa = ipa.replace ("(k)", "k")
                ipa = ipa.replace ("kʰ", "k")
                ipa = ipa.replace ("(e)", "e")
                ipa = ipa.replace ("(ə)", "ə")
                ipa = ipa.replace ("(ɐ̯)", "ɐ̯")
                ipa = ipa.replace ("ː", "")
                ipa = ipa.replace (".", "")
                ipa = ipa.replace ("m̩", "m")
                ipa = ipa.replace ("n̩", "n")
                ipa = ipa.replace ("ŋ̩", "ŋ")
                ipa = ipa.replace ("l̩", "l")
                print (ipa)
                X = ""
                while len (ipa):
                  s = ipa[0:3]
                  if s in ipa_to_sampa:
                    print (ipa_to_sampa[s])
                    X += ipa_to_sampa[s] + " "
                    ipa = ipa[3:]
                  else:
                    char = ipa[0]
                    conv = convert (char)
                    if conv:
                      print (conv)
                      X += conv + " "
                      ipa = ipa[1:]
                    elif char in [ "ˈ", "ˌ", "ː", " " ]:
                      ipa = ipa[1:]
                    else:
                      FAIL += 1
                      print ("fail: %s" % ipa)
                      raise RuntimeError ("bad convert")
                print ("X %s" % X)
                print ("############################")
                break
                '''
                print (ipa)
                multi_char_symbols = [ "aʊ̯" ]
                for sym in multi_char_symbols:
                  if sym in ipa:
                    ipa = ipa.replace (sym, ipa_to_sampa.get (sym, sym))

                for char in ipa:
                  if char in [ "ˈ", "ˌ", "ː", " " ]:
                    pass
                  else:
                    conv = convert (char)
                    if conv:
                      print (conv)
                    else:
                      print ("fail: %s" % char)
                      '''
            except:
              pass
      except:
        pass
      #print (word_string)
      word_string = ""
      state = 0
