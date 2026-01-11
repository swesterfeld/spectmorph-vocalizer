#!/bin/bash

set -e

mkdir -p testxml pho script wav voice

make -C src

remove_music_extension() {
  local filename="$1"

  if [[ "$filename" == *.musicxml ]]; then
    echo "${filename%.musicxml}"
  elif [[ "$filename" == *.xml ]]; then
    echo "${filename%.xml}"
  else
    echo "Error: File must have .xml or .musicxml extension" >&2
    return 1
  fi
}

# handle -s <seed> option
seed_param=""
# handle -v <voice> option
VOICE=sven
export VOICE
while getopts "s:v:" opt
do
  case $opt in
    s) seed_param="-s $OPTARG"
       ;;
    v) VOICE="$OPTARG"
       ;;
    *) echo "Usage: $0 [-s <seed>]"
       exit 1
       ;;
  esac
done
shift $((OPTIND - 1))

echo "VOICE: $VOICE"
. voice/$VOICE/voice.sh

check_voice()
{
  if test -f voice/$VOICE/$1; then
    LOCAL_HASH=$(sha1sum voice/$VOICE/$1 | awk '{print $1;}')
    if [ "x$LOCAL_HASH" = "x$2" ]; then
      return 0
    fi
  fi
  return 1
}

download()
{
  local EXT=$1
  local HASH=$2
  local URL="https://space.twc.de/~stefan/download2/voice/${HASH}.$EXT"

  check_voice voice.$EXT $HASH || {
    wget ${URL} -O voice/$VOICE/voice.$EXT
  }
  check_voice voice.$EXT $HASH
}

download sm $VOICE_SM_HASH
download volume $VOICE_VOLUME_HASH

XMLS="$@"
if test -z "$XMLS"; then
  XMLS="$(cd testxml; ls)"
fi

for xml in $XMLS
do
  xml=$(basename "$xml")
  filename_noext=$(remove_music_extension $xml)
  pho="${filename_noext}.pho"
  script="${filename_noext}.script"
  wav="${filename_noext}.wav"
  rm -f $pho $script $wav

  echo "$xml..."
  ./xml-to-pho.py xml testxml/$xml > pho/$pho || echo "$xml -> $pho" failed
  if [ "x$1" = "xmbrola" ]; then
    voice=$(grep ';;; VOICE' pho/$pho | cut -d " " -f 3)
    test -f /usr/share/mbrola/$voice/$voice || voice=de2
    mbrola /usr/share/mbrola/$voice/$voice pho/$pho wav/$wav
  else
    phomorphdi.py pho/$pho $seed_param > script/$script || echo "$pho -> $script" failed
    src/smscript script/$script wav/$wav
  fi
  ./volume-normalize.py wav/$wav
done
