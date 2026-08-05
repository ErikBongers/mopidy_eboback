#!/bin/bash

CARD_NUM=$1

# If no parameter was provided, prompt the user interactively
if [ -z "$CARD_NUM" ]; then
    # shellcheck disable=SC2162
    read -p "Enter the ALSA card number you want to set as default: " CARD_NUM
fi

# Ensure the final value is actually a valid integer
if ! [[ "$CARD_NUM" =~ ^[0-9]+$ ]]; then
    echo "Error: '$CARD_NUM' is not a valid card number. Please use an integer."
    exit 1
fi

tee /etc/asound.conf << EOF
pcm.!default {
    type hw
    card $CARD_NUM
}

ctl.!default {
    type hw
    card $CARD_NUM
}
EOF
