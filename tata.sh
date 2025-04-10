set -e

if [ "x$1" != x ]; then
  F="$@"
else
  F="ba ga da pa ta ka tak dap"
fi

for i in $F
do
  echo -n "$i ..."
  tata.py $(soxi -D voice/sven.flac) 1 $i > tata.script
  src/smscript voice/sven.smplan tata.script ${i}${i}.wav
  echo " OK"
done
