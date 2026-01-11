set -e

if [ $# -ne 3 ]; then
  echo "Usage: $0 <voice> <segment> <flac>"
  exit 1
fi

VOICE=$1
SEGMENT=$2
FLAC=$3

. "voice/$VOICE/$SEGMENT.sh"

if ! [[ "$VOICE_MIDI_NOTE" =~ ^[1-9][0-9]*$ ]]; then
  echo "Error: VOICE_MIDI_NOTE must be an integer greater than 0" >&2
  exit 1
fi

FLAC_HASH=$(sha1sum "$FLAC" | awk '{print $1;}')
if [ "x$VOICE_FLAC_HASH" != "x$FLAC_HASH" ]; then
  echo flac hash is different
  rsync -avc "$FLAC" stefan@space.twc.de:public_html/download2/voice/${FLAC_HASH}.flac
fi

FLAC_LOCAL_HASH=$(sha1sum "voice/$VOICE/$SEGMENT.flac" | awk '{print $1;}')
if [ "x$FLAC_LOCAL_HASH" != "x$FLAC_HASH" ]; then
  echo voice flac hash not equal
  rsync -avc "stefan@space.twc.de:public_html/download2/voice/${FLAC_HASH}.flac" voice/$VOICE/$SEGMENT.flac
fi

make -Csrc

echo "mkplan..."
src/mkplan template.smplan "voice/$VOICE/$SEGMENT.flac" "voice/$VOICE/$SEGMENT.sm" "voice/$VOICE/$SEGMENT.volume" "$VOICE_MIDI_NOTE"

ASUM=$(sha1sum "voice/$VOICE/$SEGMENT.sm" | awk '{print $1}')
VSUM=$(sha1sum "voice/$VOICE/$SEGMENT.volume" | awk '{print $1}')
rsync -avc "voice/$VOICE/$SEGMENT.sm" stefan@space.twc.de:public_html/download2/voice/${ASUM}.sm
rsync -avc "voice/$VOICE/$SEGMENT.volume" stefan@space.twc.de:public_html/download2/voice/${VSUM}.volume
(
  cat "voice/$VOICE/$SEGMENT.sh" | egrep -v '(VOICE_FLAC_HASH|VOICE_SM_HASH|VOICE_VOLUME_HASH)'
  echo VOICE_FLAC_HASH=$FLAC_HASH
  echo VOICE_SM_HASH=$ASUM
  echo VOICE_VOLUME_HASH=$VSUM
) >voice/$VOICE/$SEGMENT.sh.tmp
mv voice/$VOICE/$SEGMENT.sh.tmp voice/$VOICE/$SEGMENT.sh
