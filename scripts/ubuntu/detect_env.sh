#!/bin/bash

# Detect and print only the platform identifier string
if grep -qi "microsoft" /proc/version; then
    echo "WSL2"
elif [ -f /proc/device-tree/model ] && grep -qi "Raspberry Pi 4" /proc/device-tree/model; then
    echo "RP4"
else
    echo "UNKNOWN"
fi