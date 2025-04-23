set -e

#---------------- voice downloader ----------------------
VOICE_EXPECT=51d99a003563447f33b27206125cd7b2285ecbf8
VOICE_URL="https://space.twc.de/~stefan/download2/voice/${VOICE_EXPECT}.flac"

check_voice()
{
  if test -f voice/sven.flac; then
    VOICE_HASH=$(sha1sum voice/sven.flac | awk '{print $1;}')
    if [ "x$VOICE_HASH" = "x$VOICE_EXPECT" ]; then
      return 0
    fi
  fi
  return 1
}

check_voice || {
  echo "downloading voice file..."
  wget ${VOICE_URL} -O voice/sven.flac
}
check_voice
echo "Using Voice from $VOICE_URL"
#--------------------------------------------------------
echo "mkplan..."
src/mkplan template.smplan voice/sven.flac voice/sven.sm voice/sven.volume
PSUM=$(sha1sum voice/sven.sm | awk '{print $1}')
VSUM=$(sha1sum voice/sven.volume | awk '{print $1}')
scp voice/sven.smplan stefan@space.twc.de:public_html/download2/voice/${PSUM}.sm
scp voice/sven.volume stefan@space.twc.de:public_html/download2/voice/${VSUM}.volume

echo VOICE_PSUM=$PSUM
echo VOICE_VSUM=$VSUM
