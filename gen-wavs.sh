#!/bin/bash

set -e

mkdir -p testxml pho script wav voice

#---------------- voice downloader ----------------------
VOICE_EXPECT=51d99a003563447f33b27206125cd7b2285ecbf8
VOICE_URL="https://space.twc.de/~stefan/download2/voice/${VOICE_EXPECT}.flac"

check_voice()
{
  if test -f voice/sven.flac; then
    VOICE_HASH=$(sha1sum voice/sven.flac | awk '{print $1;}')
    if [ "x$VOICE_HASH" = "x$VOICE_EXPECT" ]; then
      return 0
    fi
  fi
  return 1
}

check_voice || {
  echo "downloading voice file..."
  wget ${VOICE_URL} -O voice/sven.flac
}
check_voice
echo "Using Voice from $VOICE_URL"
#--------------------------------------------------------

make -C src

#--------- update sven.smplan if necessary --------------
PLAN_INPUT_HASH=$(cat template.smplan voice/sven.flac | sha1sum - | awk '{print $1;}')
if test -f voice/sven.hash; then
  PLAN_INPUT_HASH_OLD=$(cat voice/sven.hash)
fi
if [ "x$PLAN_INPUT_HASH" != "x$PLAN_INPUT_HASH_OLD" ]; then
  echo "mkplan... (input_hash $PLAN_INPUT_HASH, old input_hash $PLAN_INPUT_HASH_OLD)"
  src/mkplan template.smplan voice/sven.flac voice/sven.smplan voice/sven.volume && ( echo $PLAN_INPUT_HASH > voice/sven.hash )
fi
#--------------------------------------------------------

XMLS="$@"
if test -z "$XMLS"; then
  XMLS="$(cd testxml; ls)"
fi

for xml in $XMLS
do
  xml=$(basename "$xml")
  pho=$(echo $xml|sed s/.xml$/.pho/g)
  script=$(echo $xml|sed s/.xml$/.script/g)
  wav=$(echo $xml|sed s/.xml$/.wav/g)
  rm -f $pho $script $wav

  echo "$xml..."
  ./xml-to-pho.py xml testxml/$xml > pho/$pho || echo "$xml -> $pho" failed
  if [ "x$1" = "xmbrola" ]; then
    voice=$(grep ';;; VOICE' pho/$pho | cut -d " " -f 3)
    test -f /usr/share/mbrola/$voice/$voice || voice=de2
    mbrola /usr/share/mbrola/$voice/$voice pho/$pho wav/$wav
  else
    phomorphdi.py pho/$pho $(soxi -D voice/sven.flac) > script/$script || echo "$pho -> $script" failed
    src/smscript voice/sven.smplan script/$script wav/$wav
  fi
#  ./apply-accent.py pho/$pho wav/$wav wav/$wav
done
