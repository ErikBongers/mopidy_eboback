#!/bin/bash

groupadd media_grp
usermod -aG media_grp $ORIGINAL_USER
usermod -aG media_grp mopidy


