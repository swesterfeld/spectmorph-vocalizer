set -e

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
  gen-wavs.sh testxml/xtata.musicxml
  if [ "x$PLAY" != "x" ]; then
    gst123 wav/xtata.wav
  fi
  echo " OK"
done
