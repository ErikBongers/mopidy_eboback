#!/bin/bash

id -u mopidy &>/dev/null || useradd -r -s /usr/sbin/nologin mopidy
# Grant the 'mopidy' background user execution access
setfacl -R -m u:mopidy:rwx /opt/mopidy-dev
