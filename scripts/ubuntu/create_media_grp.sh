#!/bin/bash

id -u mopidy &>/dev/null || useradd mopidy
getent group media_grp || groupadd media_grp
usermod -aG media_grp $SUDO_USER
usermod -aG media_grp mopidy
usermod -a -G audio mopidy #add user mopidy to audio group
newgrp audio #apply the new audio group.



