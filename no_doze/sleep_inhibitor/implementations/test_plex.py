import time
import unittest
from datetime import timedelta

import yaml

from plex import PlexInhibitor
from unittest.mock import patch, Mock


class PlexTest(unittest.TestCase):

    def setUp(self):
        yml_str = """
                plex:
                    token: "A1AAAAAAAAAAA_AAAAA1"
                    base_url: "http://localhost:12345"
                    pause_timeout_min: 999
                """
        patch.dict("plex.config_yml", yaml.load(yml_str, Loader=yaml.CLoader) ).start()

        # This is the plex server constructed by PlexServer() constructor
        self.templateMock = Mock()
        # This patches the PlexServer import
        self.plexPatch = patch("plex.PlexServer", return_value=self.templateMock )
        self.plexServerMock = self.plexPatch.start()

        self.inhibitor = PlexInhibitor()

    def tearDown(self) -> None:
        for patch in self.plexPatch,:
            patch.stop()

    def test_template_has_expected_configuration(self):
            self.plexServerMock.assert_called_with(token="A1AAAAAAAAAAA_AAAAA1", baseurl="http://localhost:12345")

    def test_pause_timeout_configuration(self):
        self.assertEqual(timedelta(minutes=999), self.inhibitor._get_pause_timeout() )

    def test_does_inhibit_returns_true_when_media_buffering(self):
        sessionMock = Mock()
        sessionMock.player.state = "buffering"
        self.templateMock.sessions = lambda: [sessionMock]
        self.assertTrue( self.inhibitor.does_inhibit() )
    def test_does_inhibit_returns_true_when_media_playing(self):
        sessionMock = Mock()
        sessionMock.player.state = "playing"
        self.templateMock.sessions = lambda: [sessionMock]
        self.assertTrue( self.inhibitor.does_inhibit() )

    def test_does_inhibit_when_only_playback_stream_recently_paused(self):
        sessionMock = Mock()
        sessionMock.player.state = "paused"
        sessionMock.player.machineIdentifier = "abc123"
        sessionMock.title = "test video"

        self.templateMock.sessions = lambda: [sessionMock]
        self.assertTrue(self.inhibitor.does_inhibit())

    def test_does_not_inhibit_when_only_playback_paused_shorter_than_timeout(self):
        sessionMock = Mock()
        sessionMock.player.state = "paused"
        sessionMock.player.machineIdentifier = "abc123"
        sessionMock.title = "test video"
        self.templateMock.sessions = lambda: [sessionMock]

        self.inhibitor.pause_timeout = timedelta(milliseconds=30)
        self.inhibitor.does_inhibit() # should record a paused session
        self.assertTrue(self.inhibitor.does_inhibit())

    def test_does_not_inhibit_when_only_black_stream_paused_longer_than_timeout(self):
        sessionMock = Mock()
        sessionMock.player.state = "paused"
        sessionMock.player.machineIdentifier = "abc123"
        sessionMock.title = "test video"
        self.templateMock.sessions = lambda: [sessionMock]

        self.inhibitor.pause_timeout = timedelta(milliseconds=30)
        self.inhibitor.does_inhibit()
        time.sleep(.030)
        self.assertFalse(self.inhibitor.does_inhibit() )

    def test_does_inhibit_when_two_paused_playback_one_shorter_than_timeout(self):
        self.inhibitor.pause_timeout = timedelta(milliseconds=30)
        # session 1
        sessionMock1 = Mock()
        sessionMock1.player.state = "paused"
        sessionMock1.player.machineIdentifier = "abc123"
        sessionMock1.title = "test video1"
        # session 2
        sessionMock2 = Mock()
        sessionMock1.player.state = "paused"
        sessionMock1.player.machineIdentifier = "abc123"
        sessionMock1.title = "test video2"

        self.templateMock.sessions = lambda: [sessionMock1] # only sessionMock1
        self.inhibitor.does_inhibit()
        time.sleep(0.015)
        self.templateMock.sessions = lambda: [sessionMock1, sessionMock2] # both mocks
        self.inhibitor.does_inhibit()
        time.sleep(0.016)  # session1 should be > 30ms old, session2 ~16 ms
        self.assertTrue(self.inhibitor.does_inhibit()) # session2 inhibits

    def test_playback_forgets_paused_state_after_play(self):
        self.inhibitor.pause_timeout = timedelta(milliseconds=30)
        # session is paused
        sessionMock1 = Mock()
        sessionMock1.player.state = "paused"
        sessionMock1.player.machineIdentifier = "abc123"
        sessionMock1.title = "test video1"
        self.templateMock.sessions = lambda: [sessionMock1]
        self.inhibitor.does_inhibit()
        time.sleep(0.015)
        sessionMock1.player.state = "playing"
        self.inhibitor.does_inhibit()  # should clear previous pause
        time.sleep(0.16)
        sessionMock1.player.state = "paused" # first pause > 30 ms ago should be cleared
        self.assertTrue(self.inhibitor.does_inhibit() ) # the new pause can inhibit

    def test_playback_paused_beyond_timeout_inhibits_when_played_again(self):
        self.inhibitor.pause_timeout = timedelta(milliseconds=30)
        # session is paused
        sessionMock1 = Mock()
        sessionMock1.player.state = "paused"
        sessionMock1.player.machineIdentifier = "abc123"
        sessionMock1.title = "test video1"
        self.templateMock.sessions = lambda: [sessionMock1]
        self.inhibitor.does_inhibit()
        time.sleep(0.31) # paused beyond timeout
        self.assertFalse(self.inhibitor.does_inhibit() ) # no longer inhibits
        sessionMock1.player.state = "playing"
        self.assertTrue(self.inhibitor.does_inhibit() ) # does inhibit



if __name__ == '__main__':
    unittest.main()
