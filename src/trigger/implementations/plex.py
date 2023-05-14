import logging
from typing import List, Dict
from datetime import datetime, timedelta

from plexapi.base import PlexSession
from plexapi.server import PlexServer

from src.trigger.inhibiting_process import InhibitingProcess
from src import config_provider

config_root_key = "plex"
token_key = "token"
base_url_key = "base_url"
pause_timeout_key = "pause_timeout_min"  # optional, defaults to 0


class PlexInhibitor(InhibitingProcess):

    def __init__(self):
        super().__init__("Plex Playback")
        self.log = logging.getLogger(type(self).__name__)
        self.template: PlexServer = self._create_server_template()
        self.pause_timeout: timedelta = self._get_pause_timeout()
        self.paused: Dict[str, datetime] = dict()

    def _create_server_template(self) -> PlexServer:
        token = config_provider.get_value([config_root_key, token_key], "")
        base_url = config_provider.get_value([config_root_key, base_url_key], "")
        if not token or not base_url:
            raise ValueError("Problem parsing server info from config file.")
        return PlexServer(baseurl=base_url, token=token)

    def _get_pause_timeout(self) -> timedelta:
        raw_min = config_provider.get_value([config_root_key, pause_timeout_key], "0")
        return timedelta(minutes=float(raw_min) )

    def _fetch_sessions(self) -> List[PlexSession]:
        try:
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
