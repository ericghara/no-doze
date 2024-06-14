# NoDoze

Have you ever manually disabled system sleep so a long-running task could complete? NoDoze offers a better way.

## Overview

No doze is an extensible service that temporarily inhibits sleep under certain conditions. Those *certain conditions*
can be defined as plugins through a straightforward `InhibitingConditions` interface.

### Examples

These plugins have been implemented:

* **Process Running**: While specified processes (i.e. make, apt etc.) are running, sleep is prevented until they
  complete.
* **Plex Streaming**: While a Plex server is actively streaming media to clients, sleep is prevented. After playback
  completes, sleep is allowed to resume.
* **qBittorrent Downloading**: While download rate remains above a certain threshold, sleep is prevented.
* **qBittorrent Seeding**: While upload rate remains above a certain threshold, sleep is prevented.
* **SSH Client Connected**: While user(s) are currently logged in by SSH sleep is prevented.

## How It works

At its core, NoDoze is an event loop. It schedules checks for inhibiting conditions, preventing sleep while they occur.

The actual prevention of sleep is accomplished through dbus messaging. NoDoze sends a message to systemd (login1) to
request
a lock. While the lock is held, NoDoze prevents sleep. Upon releasing the lock, sleep returns to normal.

## System Requirements

1. A Linux system that uses systemd or elogind
2. [virtualenv](https://github.com/pypa/virtualenv)
3. D-Bus Libraries:
    * Arch: glib
    * Fedora/RHEL: dbus-devel
    * Gentoo: glib
    * Ubuntu/Debian: libdbus-glib-1-dev, libgirepository1.0-dev

The install script will create a python virtual environment and pull the required python packages.
If you do not want to use the installation script, NoDoze requires the following packages:

| Required Python packages | Feature            |
|--------------------------|--------------------|
| PyYAML                   | Core               |
| dbus-python              | Core               |
| PlexAPI                  | Plex plugin        |
| qbittorrent-api          | qBittorrent plugin |

## Installation

```bash
git clone https://github.com/ericghara/no-doze.git
cd no-doze/scripts
sudo ./install
```

The installation directory is `/opt/no-doze`. Before staring NoDoze take a look at the configuration in
`/opt/no-doze/resources/config.yml`. Leave it as is or make changes according to your needs. When everything is
configured run:

```bash
systemctl start no-dozed.service
```

To make sure everything is running as expected:

```bash
journalctl -u no-dozed.service --follow
```

If you configured NoDoze to start on boot, you are all set; on future boots systemctl will start NoDoze. Otherwise,
NoDoze
can be started and stopped on demand like any other systemd service.

## Troubleshooting

Change the logging level from `INFO` to `DEBUG` in the `config.yml`.

```yaml
logging_level: "DEBUG"
```

Then run:

```bash
systemctl restart no-dozed.service
journalctl -u no-dozed.service --follow
```

Hopefully the more detailed log provides insight towards a solution.

## Developers

To make a plugin you need to implement a single method: `does_inhibit`, and make
the plugin available for autodiscovery. The documentation in `core.inhibiting_condition` should get you
started.

To set up the Poetry virtual environment.

```
poetry install
```

If you do not wish to use poetry, a `requirements.txt` is provided.

*Note:* Root privileges are required by any process which blocks sleep. Keep this in mind while testing.
