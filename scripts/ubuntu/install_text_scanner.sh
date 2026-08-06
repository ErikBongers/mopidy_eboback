#!/bin/bash

cd /opt/mopidy-dev || exit
git clone https://github.com/ErikBongers/TextScanner.git
sudo apt  install rustup
rustup default stable
pip install maturin
cd text_scanner_py
maturin develop

