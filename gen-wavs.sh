#!/bin/bash

set -e

mkdir -p testxml pho script wav voice

#---------------- voice downloader ----------------------
VOICE_EXPECT=292aa38c052c12b4ddff6ba30ed7ba097299a898

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
  wget space.twc.de/~stefan/download2/voice/${VOICE_EXPECT}.flac -O voice/sven.flac
}
check_voice
#--------------------------------------------------------

make -C src
src/mkplan template.smplan voice/sven.flac voice/sven.smplan

XMLS="$@"
if test -z "$XMLS"; then
  XMLS="$(cd testxml; ls)"
fi

for xml in $XMLS
do
  pho=$(echo $xml|sed s/.xml$/.pho/g)
  script=$(echo $xml|sed s/.xml$/.script/g)
  wav=$(echo $xml|sed s/.xml$/.wav/g)
  rm -f $pho $script $wav

  ./xml-to-pho.py xml testxml/$xml > pho/$pho || echo "$xml -> $pho" failed
  if [ "x$1" = "xmbrola" ]; then
    voice=$(grep ';;; VOICE' pho/$pho | cut -d " " -f 3)
    test -f /usr/share/mbrola/$voice/$voice || voice=de2
    mbrola /usr/share/mbrola/$voice/$voice pho/$pho wav/$wav
  else
    phomorphdi.py pho/$pho $(soxi -D voice/sven.flac) > script/$script || echo "$pho -> $script" failed
    src/smscript voice/sven.smplan script/$script wav/$wav
  fi
  ./apply-accent.py pho/$pho wav/$wav wav/$wav
done
