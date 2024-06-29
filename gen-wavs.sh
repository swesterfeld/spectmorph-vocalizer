#!/bin/bash

set -e

mkdir -p testxml pho script wav

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
  src/smscript script ~/smtest/diphone-sven-test.smplan script/$script | ascii2wav -r 48000 wav/$wav
done
