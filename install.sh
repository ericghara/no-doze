#!/bin/bash

if (( $EUID != 0 )); then
  echo "Must run as root"
  exit 1
fi

INSTALL_DIR=/opt/no-doze
VENV=$INSTALL_DIR/venv
VENV_BIN=$VENV/bin

mkdir $INSTALL_DIR

virtualenv -q -p /usr/bin/python3 $VENV
$VENV_BIN/pip install -r requirements.txt

# should have a warning about overwriting config.yml

cp no-doze.service /etc/systemd/system/

systemctl daemon-reload

read -p "Would you like to autostart NoDoze on boot (i.e. systemd enable)? (y/n) " -n 1 key <&1
if [[ "$key" =~ ^(y|Y) ]] ; then
  systemctl enable no-doze.service
fi
echo "To start NoDoze run: systemctl start no-doze.service "


