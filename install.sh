#!/usr/bin/env bash

# Before running this script, make sure you have python-build, python-installer,
# python-wheel and python-setuptools installed.

PROGRAM_NAME="nwg-displays"
MODULE_NAME="nwg_displays"
SITE_PACKAGES="$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")"
PATTERN="$SITE_PACKAGES/$MODULE_NAME*"

# Remove from site_packages
for path in $PATTERN; do
    if [ -e "$path" ]; then
        echo "Removing $path"
        rm -r "$path"
    fi
done

[ -d "./dist" ] && rm -rf ./dist

# Remove launcher scripts
filenames=("/usr/bin/nwg-displays" "/usr/bin/nwg-displays-apply")

for filename in "${filenames[@]}"; do
  if [ -f "$filename" ]; then
      rm -f "$filename"
      echo "Removing -f $filename"
  fi
done

python -m build --wheel --no-isolation

python -m installer dist/*.whl

install -Dm 644 -t "/usr/share/applications" "$PROGRAM_NAME.desktop"
install -Dm 644 -t "/usr/share/pixmaps" "$PROGRAM_NAME.svg"

install -Dm 644 -t "/usr/share/licenses/$PROGRAM_NAME" LICENSE
install -Dm 644 -t "/usr/share/doc/$PROGRAM_NAME" README.md