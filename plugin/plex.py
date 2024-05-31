import logging
import sys
from datetime import datetime, timedelta
from math import inf
from typing import List, Dict, Optional

from plexapi.base import PlexSession
from plexapi.server import PlexServer

from common import config_provider
from client.inhibiting_condition import InhibitingCondition

logging_level_key = "logging_level"
config_root_key = "plex"
token_key = "token"
base_url_key = "base_url"
period_key = "period_min"
pause_periods_key = "max_periods_paused"



class PlexInhibitor(InhibitingCondition):

    """
    A sleep inhibitor that checks the status of active playback streams using the Plex API.  Any active streams have
    the ability to inhibit sleep.  Paused streams are a special case, they can be configured to inhibit sleep for only
    a few periods.  This is to handle cases where someone paused playback for a very long time.

    if no `period_min` key is found service is disabled, with the period being set to a very large value.
    """

    def __init__(self):
        self.log = logging.getLogger(type(self).__name__)
        period = config_provider.get_period_min(key_path=[config_root_key, period_key], default=timedelta.max)
        super().__init__(name="Plex Playback", period=period)
        if period == sys.maxsize:
            self.log.info("Plex Inhibitor was disabled by config.")
        # delay instantiation, PlexServer attempts to create a connection immediately
        self.template: Optional[PlexServer] = None

        self.pause_timeout: timedelta = self._generate_pause_timeout()
        self.paused: Dict[str, datetime] = dict()

        if config_provider.get_value([logging_level_key], "INFO") == "INFO":
            logging.getLogger('urllib3').setLevel(logging.CRITICAL) # very chatty when unable to connect

    def does_inhibit(self) -> bool:
        currently_paused: List[PlexSession] = list()
        inhibited = False
        # check all sessions for activity
        for session in self._fetch_sessions():
            if session.player.state.lower() != "paused":
                inhibited = True
            else:
                currently_paused.append(session)
        inhibited |= self._update_paused(currently_paused)
        return inhibited

    def _create_server_template(self) -> PlexServer:
        token = config_provider.get_value([config_root_key, token_key], "")
        base_url = config_provider.get_value([config_root_key, base_url_key], "")
        if not token or not base_url:
            raise ValueError("Problem parsing server info from config file.")
        return PlexServer(baseurl=base_url, token=token)

    def _generate_pause_timeout(self) -> timedelta:
        pause_periods = round(float(config_provider.get_value([config_root_key, pause_periods_key])), 0)
        if pause_periods == inf:
            return timedelta.max
        return pause_periods * self.period()


    def _fetch_sessions(self) -> List[PlexSession]:
        try:
            if not self.template:
                self.template = self._create_server_template()
            return self.template.sessions()
        except Exception as e:
            self.log.debug(f"Failed to fetch sessions from server.", e)
            return list()

    def _update_paused(self, currently_paused: List[PlexSession]) -> bool:
        """
        Add newly paused sessions and *only* carry over those that remain paused.  Returns
        True if any paused items inhibit sleep (`time duration paused < pause_timeout`) else
        False.
        :param currently_paused:
        :return: if any paused items inhibit sleep
        """
        next_paused: Dict[str, datetime] = dict()
        inhibited = False
        for session in currently_paused:
            machine_id = session.player.machineIdentifier
            title = session.title
            identifier = f"{machine_id}:{title}"
            paused_at = self.paused.get(identifier, datetime.now())
            next_paused[identifier] = paused_at
            if datetime.now() - paused_at < self.pause_timeout:
                inhibited = True
        self.paused = next_paused
        return inhibited


def register(registrar: 'InhibtingConditionRegistrar'):
    if config_provider.key_exists(["plex"]):
        registrar.accept(PlexInhibitor())
    else:
        logging.debug("Skipping registration of Plex. Configuration is absent from config.yml.")