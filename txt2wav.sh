#!/bin/bash
#
set -e

# handle -s <seed> option
seed_param=""
while getopts "s:" opt
do
  case $opt in
    s) seed_param="-s $OPTARG"
       ;;
    *) echo "Usage: $0 [-s <seed>]"
       exit 1
       ;;
  esac
done
shift $((OPTIND - 1))

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
  txt_noext=$(remove_txt_extension $(basename $txt))
  txt2mxml.py $txt testxml/${txt_noext}.musicxml
  gen-wavs.sh $seed_param testxml/${txt_noext}.musicxml
done
