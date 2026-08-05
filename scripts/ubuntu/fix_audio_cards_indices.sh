#!/bin/bash

cat <<- 'EOF' > nano /etc/modprobe.d/alsa-order.conf
options snd_bcm2835 index=0
options vc4 index=1,2
options snd_usb_audio index=3
EOF
