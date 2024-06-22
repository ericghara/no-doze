#!/bin/bash

TAG=ericgha/no-doze:2.0

cp ../../resources/requirements.txt ./
docker build . --tag=$TAG