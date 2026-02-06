#!/bin/bash
#
set -e

remove_txt_extension() {
  local filename="$1"

  if [[ "$filename" == *.txt ]]; then
    echo "${filename%.txt}"
  else
    echo "Error: File must have .txt extension" >&2
    return 1
  fi
}

for txt in $@
do
  txt_noext=$(remove_txt_extension $txt)
  txt2mxml.py $txt testxml/${txt_noext}.musicxml
  gen-wavs.sh testxml/${txt_noext}.musicxml
done
