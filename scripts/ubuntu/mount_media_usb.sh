#!/bin/bash

if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: Please run this script with sudo"
  exit 1
fi

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

"./$SCRIPT_DIR/create_media_grp.sh"

# list drive names:
lsblk

read -p "👉 Type the partition name to mount (e.g., sda1, sdb1): " DISKNAME

EXTRACTED_UUID=$(blkid "/dev/$DISKNAME" | grep -oP 'UUID="\K[^"]+')
if [ -n "$EXTRACTED_UUID" ]; then
  UUID=$EXTRACTED_UUID
else
  echo "⚠️ Warning: Could not automatically extract the UUID."
  read -p "👉 Please manually type or paste the UUID: " UUID
fi

read -p "👉 Enter a name for your mount folder (e.g., myusb): " MOUNTNAME
MOUNT_PATH="/mnt/$MOUNTNAME"
mkdir -p "$MOUNT_PATH"

#todo: media_grp is hardcoded.
GROUP_ID=$(getent group "media_grp" | cut -d: -f3)
FSTAB_LINE="UUID=$UUID  $MOUNT_PATH  vfat  defaults,nofail,uid=1000,gid=$GROUP_ID,dmask=0002,fmask=0113  0  0"
echo "$FSTAB_LINE" | tee -a /etc/fstab > /dev/null

# STABLINE MASKS:
# These masks DISABLE privs and are NOT AND-ed with the typical chmod 777 privs.
# Where
#  4 = read
#  2 = write
#  1 = execute
# 1st digit = special privs
# 2nd, 3rd and 4th digit are user, group and other
# so 0113 means, 0 = ignore special privs, 1 = no execute for user, 1 = no execute for group and 3 = 1 + 2 = no execute and write for other.