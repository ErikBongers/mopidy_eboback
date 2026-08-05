#!/bin/bash

MOPIDY_AUDIO_OUTPUT=$1

# If no parameter was provided, prompt the user interactively
if [ -z "$MOPIDY_AUDIO_OUTPUT" ]; then
    # shellcheck disable=SC2162
    read -p "Enter the mopidy [audio.output] value: " MOPIDY_AUDIO_OUTPUT
fi

#todo: erik is hardcoded!!!
tee /home/erik/.config/mopidy/mopidy.conf << EOF
[audio]
output=$MOPIDY_AUDIO_OUTPUT
EOF
