#!/bin/bash

set -e

mkdir -p testxml pho script wav voice

check_voice()
{
  if test -f voice/sven.smplan; then
    echo "checking voice hash..."
    VOICE_EXPECT=a3e33d7ca1d2fd4fea175228ea614abbd75eada2
    VOICE_HASH=$(sha1sum voice/sven.smplan | awk '{print $1;}')
    if [ "x$VOICE_HASH" = "x$VOICE_EXPECT" ]; then
      return 0
    fi
  fi
  return 1
}

check_voice || {
  echo "downloading voice file..."
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
  ./xml-to-pho.py xml testxml/$xml > pho/$pho || echo "$xml -> $pho" failed
  phomorphdi.py pho/$pho > script/$script || echo "$pho -> $script" failed
  src/smscript script voice/sven.smplan script/$script | ascii2wav -r 48000 wav/$wav
done
