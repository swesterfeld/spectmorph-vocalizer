set -e

if [ "x$1" != x ]; then
  F="$@"
else
  F="ba ga da pa ta ka tak dap"
fi

for i in $F
do
  echo -n "$i ..."
  VOICE=sven tata.py 1 $i > tata.script
  src/smscript tata.script ${i}${i}.wav
  if [ "x$PLAY" != "x" ]; then
    gst123 ${i}${i}.wav
  fi
  echo " OK"
done
