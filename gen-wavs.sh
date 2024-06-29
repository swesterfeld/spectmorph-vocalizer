#!/bin/bash

set -e

mkdir -p testxml pho script wav voice

#---------------- voice downloader ----------------------
VOICE_EXPECT=fc8dec99f2d3d117fe35cdf457fe8e7efdf5973d

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


for xml in $(cd testxml; ls)
do
  pho=$(echo $xml|sed s/.xml$/.pho/g)
  script=$(echo $xml|sed s/.xml$/.script/g)
  wav=$(echo $xml|sed s/.xml$/.wav/g)
  rm -f $pho $script $wav

  ./xml-to-pho.py xml testxml/$xml > pho/$pho || echo "$xml -> $pho" failed
  phomorphdi.py pho/$pho > script/$script || echo "$pho -> $script" failed
  src/smscript voice/sven.smplan script/$script wav/$wav
done
