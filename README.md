# NoDoze

Have you ever manually disabled system sleep so a long-running task could complete?  NoDoze offers a better way.

## Overview

No doze is an extensible service that temporarily inhibits sleep under certain conditions. Those *certain conditions*
can be defined as plug-ins through a straightforward `InhibitingConditions` interface.

### Examples

These have been implemented:

* **Plex Streaming**: while a Plex server is actively streaming media to clients, sleep is prevented. After playback
  completes sleep is allowed to resume.
* **qBittorrent Downloading** while download rate remains above a certain threshold, sleep is prevented.
* **qBittorrent Seeding** while upload rate remains above a certain threshold, sleep is prevented.

## How It works

At its core, NoDoze is an event loop, which schedules checks for inhibiting conditions, preventing sleep while they occur.  

NoDoze periodically checks all the registered `InhibitingConditions`, if at least one is met sleep is temporarily blocked.
Implementors are directed to `src.condition.inhibiting_condition` for more details.

## System Requirements

An up-to-date Linux system that uses systemd and [virtualenv](https://github.com/pypa/virtualenv).  The install script
will create a python virtual environment and pull the required python packages.

If you do not want to use the installation script, no doze requires the following packages: 

| Required Python packages | Feature             |
|--------------------------|---------------------|
| PyYAML                   | Core                |
| dbus-python              | Core                |
| PlexAPI                  | Plex plug-in        |
| qbittorrent-api          | qBittorrent plug-in |

## Installation

```bash
git clone https://github.com/ericghara/no-doze.git
cd  no-doze
sudo ./install
```

The installation script will install NoDoze in `/opt/no-doze`.  Before staring NoDoze take a look at the configuration in 
`/opt/no-doze/src/resources/config.yml`.  The file is heavily documented, leave it as is or make changes according to your
needs.  When everything is configured run:
```bash
systemctl start no-doze.service
```

To make sure everything is running as expected:

```bash
journalctl -u no-doze.service --follow
```

## Troubleshooting
change the logging level from `INFO` to `DEBUG` in the `config.yml`.
```yaml
logging_level: "DEBUG"
```
Then run:
```bash
systemctl restart no-doze.service
journalctl -u no-doze.service --follow
```

## Developers

Setup the poetry virtual environment.
```
poetry install
```
If you do not wish to use poetry, a `requirements.txt` is provided.


