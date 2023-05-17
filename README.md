# NoDoze

Have you ever modified your power settings to manually disable sleep so a
a long-running task could complete?  NoDoze offers a better way.


## Overview

No doze is an extensible service that temporarily inhibits sleep under certain conditions. Those *certain conditions*
can be defined as plug-ins through a straightforward `InhibitingConditions` interface.

#### Examples

These inhibiting conditions have been implemented:

* **Plex Streaming** while a Plex server is actively streaming media to clients, sleep is prevented. After playback
  completes sleep is allowed to resume.
* **qBittorrent Downloading** while download rate remains above a certain threshold sleep is prevented.
* **qBittorrent Seeding** while upload rate remains above a certain threshold sleep is prevented.

## How It works

At its core, NoDoze is an event loop, which schedules checks for inhibiting conditions and prevents sleep while they occur.  

NoDoze periodically checks all the registered `InhibitingConditions`, if at least one is met, sleep is temporarily blocked.
Implementors are directed to `src.trigger.inhibiting_condition` for more details.

## System Requirements

An up-to-date Linux system that uses systemd.

| Required Python packages | Feature             |
|--------------------------|---------------------|
| PyYAML                   | Core                |
| dbus-python              | Core                |
| PlexAPI                  | Plex plug-in        |
| qbittorrent-api          | qBittorrent plug-in |


