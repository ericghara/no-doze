#!/bin/bash

LOGIND_BUS_NAME='org.freedesktop.login1'
LOGIND_OBJECT_PATH='/org/freedesktop/login1'

python3 -m jeepney.bindgen --name $LOGIND_BUS_NAME \
        --path $LOGIND_OBJECT_PATH --bus SYSTEM