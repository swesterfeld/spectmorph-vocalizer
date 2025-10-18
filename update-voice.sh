set -e

if [ $# -ne 2 ]; then
  echo "Usage: $0 <voice> <flac>"
  exit 1
fi

. "voice/$1/voice.sh"

if ! [[ "$VOICE_MIDI_NOTE" =~ ^[1-9][0-9]*$ ]]; then
  echo "Error: VOICE_MIDI_NOTE must be an integer greater than 0" >&2
  exit 1
fi

FLAC_HASH=$(sha1sum "$2" | awk '{print $1;}')
if [ "x$VOICE_FLAC_HASH" != "x$FLAC_HASH" ]; then
  echo flac hash is different
  rsync -avc "$2" stefan@space.twc.de:public_html/download2/voice/${FLAC_HASH}.flac
fi

FLAC_LOCAL_HASH=$(sha1sum "voice/$1/voice.flac" | awk '{print $1;}')
if [ "x$FLAC_LOCAL_HASH" != "x$FLAC_HASH" ]; then
  echo voice flac hash not equal
  rsync -avc "stefan@space.twc.de:public_html/download2/voice/${FLAC_HASH}.flac" voice/$1/voice.flac
fi

make -Csrc

echo "mkplan..."
src/mkplan template.smplan "voice/$1/voice.flac" "voice/$1/voice.sm" "voice/$1/voice.volume" "$VOICE_MIDI_NOTE"

ASUM=$(sha1sum "voice/$1/voice.sm" | awk '{print $1}')
VSUM=$(sha1sum "voice/$1/voice.volume" | awk '{print $1}')
rsync -avc "voice/$1/voice.sm" stefan@space.twc.de:public_html/download2/voice/${ASUM}.sm
rsync -avc "voice/$1/voice.volume" stefan@space.twc.de:public_html/download2/voice/${VSUM}.volume
(
  cat "voice/$1/voice.sh" | egrep -v '(VOICE_FLAC_HASH|VOICE_SM_HASH|VOICE_VOLUME_HASH)'
  echo VOICE_FLAC_HASH=$FLAC_HASH
  echo VOICE_SM_HASH=$ASUM
  echo VOICE_VOLUME_HASH=$VSUM
) >voice/$1/voice.sh.tmp
mv voice/$1/voice.sh.tmp voice/$1/voice.sh
