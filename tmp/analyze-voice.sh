for i in ${1}_*_split.flac
do
  SEGMENT=${i%.flac}
  echo ../src/mkplan ../template.smplan "$SEGMENT.flac" "$SEGMENT.sm" "$SEGMENT.volume" "50"
done
