#!/bin/bash

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

#if [ "x$1" != x ]; then
F="$@"
#else
  #F="ba ga da pa ta ka tak dap"
#fi

for i in $F
do
  echo -n "$i ..."
  xtata.py $i > xtata.txt
  txt2mxml.py xtata.txt testxml/xtata.musicxml
  gen-wavs.sh $seed_param testxml/xtata.musicxml
  if [ "x$PLAY" != "x" ]; then
    gst123 wav/xtata.wav
  fi
  echo " OK"
done
