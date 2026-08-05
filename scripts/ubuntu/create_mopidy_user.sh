#!/bin/bash

if id "mopidy" &>/dev/null; then
    echo "User 'mopidy' already exists."
    exit 0
fi

useradd -r -s /usr/sbin/nologin mopidy
# Grant the 'mopidy' background user execution access
setfacl -R -m u:mopidy:rwx /opt/mopidy-dev
