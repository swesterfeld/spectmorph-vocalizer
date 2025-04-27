#!/bin/bash

set -e

mkdir -p testxml pho script wav voice

make -C src

VOICE_ASUM=e93ba1fab6c7e16cd9eaa4efd0c262966a62fd0b
VOICE_VSUM=052ba5d2e3dc0ba1bab01a6fb69c739e4663b31b

VOICE_AURL=https://space.twc.de/~stefan/download2/voice/${VOICE_ASUM}.sm
VOICE_VURL=https://space.twc.de/~stefan/download2/voice/${VOICE_VSUM}.volume

check_voice()
{
  if test -f voice/$1; then
    VOICE_HASH=$(sha1sum voice/$1 | awk '{print $1;}')
    if [ "x$VOICE_HASH" = "x$2" ]; then
      return 0
    fi
  fi
  return 1
}

check_voice sven.sm $VOICE_ASUM || {
  wget ${VOICE_AURL} -O voice/sven.sm
}
check_voice sven.sm $VOICE_ASUM

check_voice sven.volume $VOICE_VSUM || {
  wget ${VOICE_VURL} -O voice/sven.volume
}
check_voice sven.volume $VOICE_VSUM

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
    phomorphdi.py pho/$pho $(soxi -D voice/sven.flac) > script/$script || echo "$pho -> $script" failed
    src/smscript template.smplan voice/sven.sm script/$script wav/$wav
  fi
#  ./apply-accent.py pho/$pho wav/$wav wav/$wav
done
