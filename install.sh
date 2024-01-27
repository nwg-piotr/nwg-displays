#!/usr/bin/env bash

python3 setup.py install --optimize=1
cp nwg-displays.svg /usr/share/pixmaps/
cp nwg-displays.desktop /usr/share/applications/
install -Dm 644 -t "/usr/share/licenses/nwg-displays" LICENSE
install -Dm 644 -t "/usr/share/doc/nwg-displays" README.md