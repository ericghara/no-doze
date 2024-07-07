# NoDoze

Have you ever manually disabled system sleep so a long-running task could complete?  Or worse, periodically came back to
wiggle the mouse?

Is your computer a "media server", where you *permanently* disabled suspend/hibernate, so for a couple of hours each 
evening you can stream without your computer going to sleep?

NoDoze offers a better way.

## Overview

No doze is a plugin based service that decides when it's a good time to inhibit a computer from sleeping.
These plugins check for certain conditions.  Checks can be as simple as if a certain program is running 
(i.e. make) or more complicated, is the average download rate of qBittorrent is over a threshold (in other words downloads
are making progress). 

### Plugins

Plugins define these small checks that NoDoze makes. They are run periodically and used by NoDoze to decide if sleep 
should be prevented.  The plugins allow you to only perform the checks that you want, and ignore those that don't 
really matter to you.

These plugins have been implemented:

* **Process Running**: While processes you chose (i.e. make, apt etc.) are running, sleep is prevented until they
  complete.
* **Plex Streaming**: While a Plex server is actively streaming to clients, sleep is prevented. After playback
  completes, sleep is allowed to resume.
* **qBittorrent Downloading**: While download rate remains above a certain threshold, sleep is prevented.
* **qBittorrent Seeding**: While upload rate remains above a certain threshold, sleep is prevented.
* **SSH Client Connected**: While user(s) are currently logged in by SSH sleep is prevented.

Additionally, the plugin interface was designed to make plugins straightforward to write.  The goal was to allow someone
with a basic familiarity with Python to write a plugin.

## How It works

At its core, NoDoze is an event loop. It schedules checks for inhibiting conditions, preventing sleep while they occur.
Additionally, seconds before the computer is about to go to sleep NoDoze performs one last check to make sure it's 
*really* a good time to sleep.

NoDoze was designed to be agnostic to desktop environments.  It hooks into systemd, which is present on a majority
of linux distros. NoDoze uses dbus messaging to communicate with the systemd login manger (loginctl).

## System Requirements

1. A linux distro that uses systemd (if yours doesn't you'll know, and you will probably have a very grey beard)
2. [virtualenv](https://github.com/pypa/virtualenv)

The install script will create a python virtual environment and pull the required python packages.
If you do not want to use the installation script, NoDoze requires the following packages:

### Required Packages
- PyYAML 
- jeepney
 
### Optional Packages (Plugins)
- PlexAPI (Plex plugin)        
- qbittorrent-api (qBittorrent plugin)

## Installation

```bash
git clone https://github.com/ericghara/no-doze.git
cd no-doze/scripts
sudo ./install
```

The installation prompts will guide you through the installation, but to view things at a high level,
each user has their own NoDoze configuration.  The checks for each user are independent of others
and only apply when that user is logged in.  The only config file you should need to modify is in
`~/.config/no-doze/no-doze-client-config.yml`.  The file is documented for the checks NoDoze will use
to decide when to prevent sleep. If you don't want to use a plugin simply its section from the config, or comment it
out with `#`. 

For distribution package maintainers: there is another config file for the daemon (`no-dozed`) which is a system service
(runs all the time) in `/etc/no-doze/no-dozed.yml`.  Users should not need to touch this, but you may want to.
The purpose for both user and system-wide services is that no-dozed  needs root privileges to prevent sleep, 
but since no-doze is plugin based, running plugins privileged is unsafe.  So NoDoze is split into no-dozed which is
privileged and talks to systemd and no-doze-client which is run per-user unprivileged. no-doze-client checks if sleep should 
be prevented and sends a message to no-dozed.  Users who can send messages to no-dozed should be part of a `no-doze` group 
as no-dozed enforces group membership through file permissions.

### Is it working?

Check if the system-wide daemon is running.

```bash
sudo systemctl status no-dozed.service
```

Check if the per-user service is running (probably more important to focus on)
```bash
systemctl --user status no-doze-client.service
```

## Troubleshooting

Change the logging level from `INFO` to `DEBUG` in `~/.config/no-doze/no-doze-client-config.yml`.

```yaml
logging_level: "DEBUG"
```

Then run:

```bash
systemctl --user restart no-doze-client.service
journalctl --user -u no-doze-client.service --follow
```

The more detailed log should help you isolate the solution.

## Developers

To make a plugin you need to implement a single method: `does_inhibit`, and make
the plugin available for autodiscovery. The documentation in `core.inhibiting_condition` should get you
started.  You can just drop your plugins in `/usr/lib/no-doze/plugin` and it will be auto discovered.  Take a look
at other plugins, like `active_process.py` and `sshd.py` which are pretty simple and should be good templates.

If you want to do more hardcore development on the core of NoDoze you can set up the Poetry virtual environment.

```
poetry install
```

If you do not wish to use poetry, a `requirements.txt` is provided.

*Note:* Root privileges are required by any process which blocks sleep. Keep this in mind while testing.

## FAQ

**Why did you make this?**

The types of computers that you want running 24/7 are larger desktops or workstations which are loud, 
create heat and use a lot of energy.  This is both annoying and wasteful.  There is other software which 
prevents sleep (like Caffeine on Mac), but they do this in pretty simple ways like stopping sleep only when you tell 
it to.  I took a different approach, making something that doesn't require user interaction; in fact, I want something 
that I hope you literally forget about after setup.  This is why NoDoze is a system service and not a program that your 
run on-demand.

**What are the limitations of NoDoze?**

NoDoze can prevent sleep but currently cannot wake your computer up from sleep (harder problem).  So for this
reason I consider NoDoze an 85% solution.  That being said, for me this 85% solution works very well.

**Why did you write it in Python?**

I agree, it's an uncommon choice for a daemon.  The initial goal for NoDoze was to be plugin based and I wanted
it to be easy for people to write plugins.  Writing plugins in C would be inaccessible
for a majority of people.  Writing NoDoze split between Python for plugins and C for the core would just be complicated 
and introduce more dependencies. So I wrote NoDoze in Python and designed it to run very efficiently. `no-dozed` uses 
a few hundred milliseconds of CPU time each day and the `no-doze-client` uses a couple seconds of cpu time each day 
(plugin dependent).

**So there's actually two services running?**

Yes.  I started out with one, but decided I hated it from a security standpoint.  On almost all Linux systems you need 
root privileges to prevent sleep-- but NoDoze is plugin based.  A plugin based service that runs as root is pretty 
unsafe. Therefore, NoDoze is separated into `no-dozed` that runs privileged, as a system service, 
and  `no-doze-client` a per-user service which is unprivileged and runs plugins only while a user is logged in.  Only users
who are members of the `no-doze` linux group can actually use `no-dozed` to inhibit sleep.  You shouldn't need to touch 
`no-dozed`other than make sure it's running. The `no-doze-client` and its config is where most of the magic happens.  
