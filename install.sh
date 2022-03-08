#!/usr/bin/env bash

python3 setup.py install --optimize=1
cp nwg-displays.svg /usr/share/pixmaps/
cp nwg-displays.desktop /usr/share/applications/
