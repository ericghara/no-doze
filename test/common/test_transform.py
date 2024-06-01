import unittest

import common.message.messages as messages
from common.message.transform import MessageEncoder, MessageDecoder
from datetime import datetime
import json

class TestTransform(unittest.TestCase):

    def test_InhibitMessage_dumps(self):
        pid = 123
        gid = 456
        ts = datetime.now()

        orig = messages.InhibitMessage(pid=pid, gid=gid, expiry_timestamp=ts)
        dump = json.dumps(orig, cls=MessageEncoder)
        copy = json.loads(dump, cls=MessageDecoder)
        self.assertEqual(orig, copy)


    def test_BindMessage(self):
        pid = 123
        gid = 456
        attempt : int = 1

        orig = messages.BindMessage(pid=pid, gid=gid, attempt=attempt)
        dump = json.dumps(orig, cls=MessageEncoder)
        copy = json.loads(dump, cls=MessageDecoder)
        self.assertEqual(orig, copy)