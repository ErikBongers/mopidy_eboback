#!/bin/bash

getent group somegroupname || groupadd media_grp
usermod -aG media_grp $SUDO_USER
usermod -aG media_grp mopidy


