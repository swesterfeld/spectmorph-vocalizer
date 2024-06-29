#!/bin/bash

set -e

mkdir -p testxml pho script wav voice

VOICE_EXPECT=a3e33d7ca1d2fd4fea175228ea614abbd75eada2

check_voice()
{
  if test -f voice/sven.smplan; then
    echo "checking voice hash..."
    VOICE_HASH=$(sha1sum voice/sven.smplan | awk '{print $1;}')
    if [ "x$VOICE_HASH" = "x$VOICE_EXPECT" ]; then
      return 0
    fi
  fi
  return 1
}

check_voice || {
  echo "downloading voice file..."
  wget space.twc.de/~stefan/download2/voice/${VOICE_EXPECT}.smplan -O voice/sven.smplan
}
check_voice

pushd src
make
popd

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
