#!/bin/bash

IMAGE_TAG=ericgha/no-doze:2.0
SOURCE_DIR=$(dirname $(dirname `pwd`))
echo $SOURCE_DIR

container=$(docker run -d --rm -v /sys/fs/cgroup:/sys/fs/cgroup -v $SOURCE_DIR:/tmp/no-doze --privileged --cgroupns=host $IMAGE_TAG)
docker exec -it $container /bin/bash
echo "Stopping container"
docker container stop -s 9 $container