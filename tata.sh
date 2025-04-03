for i in ba ga da pa ta ka tak dap
do
  echo -n "$i ..."
  tata.py $(soxi -D voice/sven.flac) 1 $i > tata.script
  src/smscript voice/sven.smplan tata.script ${i}${i}.wav
  echo " OK"
done
