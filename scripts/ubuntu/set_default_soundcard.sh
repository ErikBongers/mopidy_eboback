#!/bin/bash

CARD_NUM=$1

# If no parameter was provided, prompt the user interactively
if [ -z "$CARD_NUM" ]; then
    # shellcheck disable=SC2162
    echo ""
    read -p "Enter the ALSA card number you want to set as default: " CARD_NUM  < /dev/tty
fi

# Ensure the final value is actually a valid integer
if ! [[ "$CARD_NUM" =~ ^[0-9]+$ ]]; then
    echo "Error: '$CARD_NUM' is not a valid card number. Please use an integer."
    exit 1
fi

cat << 'EOF' > /etc/asound.conf
pcm.!default {
    type hw
    card $CARD_NUM
}

ctl.!default {
    type hw
    card $CARD_NUM
}
EOF
