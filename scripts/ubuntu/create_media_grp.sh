#!/bin/bash

id -u mopidy &>/dev/null || useradd mopidy
getent group somegroupname || groupadd media_grp
usermod -aG media_grp $SUDO_USER
usermod -aG media_grp mopidy


