FROM jrei/systemd-debian:12
MAINTAINER Eric G
ENV container docker

# container has systemd
# any CMD passed to it it will run with the default entrypoint
# implemented as running via a systemd runner service
# probably not useful was trying to automate testing of install but didn't pan out

ENV PIP_BREAK_SYSTEM_PACKAGES=1
COPY requirements.txt /root/requirements.txt

ARG UNIT_FILE_NAME=runner.service
ARG UNIT_FILE='[Unit]\n\
Description=Run From args\n\
[Service]\n\
WorkingDirectory=/tmp\n\
ExecStart=bash /tmp/run.sh\n\
Restart=no\n\
\
[Install]\n\
WantedBy=multi-user.target\n\
'

ARG ENTRY_SCRIPT='#/bin/bash\n\
echo "$@" > /tmp/run.sh\n\
chmod +x /tmp/run.sh\n\
exec /sbin/init\n\
'

RUN \
    apt-get update;  \
    apt-get -y install libdbus-glib-1-dev libgirepository1.0-dev python3 pip virtualenv sudo procps; \
    pip install -r /root/requirements.txt; \
    rm /root/requirements.txt; \
    (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == systemd-tmpfiles-setup.service ] || rm -f $i; done); \
    rm -f /lib/systemd/system/multi-user.target.wants/*;\
    rm -f /etc/systemd/system/*.wants/*;\
    rm -f /lib/systemd/system/local-fs.target.wants/*; \
    rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
    rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
    rm -f /lib/systemd/system/basic.target.wants/*;\
    rm -f /lib/systemd/system/anaconda.target.wants/*; \
    echo "$UNIT_FILE" > /etc/systemd/system/$UNIT_FILE_NAME; \
    systemctl enable $UNIT_FILE_NAME; \
    echo "$ENTRY_SCRIPT" > /entrypoint.sh; \
    chmod +x /entrypoint.sh; \
    useradd -m test0; \
    sudo -u test0 mkdir ~test0/.config; \
    useradd -m test1; \
    sudo -u test1 mkdir ~test1/.config;

VOLUME [ "/sys/fs/cgroup", "/tmp", "/run", "/run/lock" ]

ENTRYPOINT [ "/bin/bash", "/entrypoint.sh" ]
CMD ["echo", "test"]