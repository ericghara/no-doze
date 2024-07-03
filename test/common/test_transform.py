import json
import unittest
from datetime import datetime

import common.message.messages as messages
from common.message.transform import MessageEncoder, MessageDecoder


class TestTransform(unittest.TestCase):

    def test_InhibitMessage_dumps(self):
        pid = 123
        uid = 456
        ts = datetime.now()

        orig = messages.InhibitMessage(pid=pid, uid=uid, expiry_timestamp=ts)
        dump = json.dumps(orig, cls=MessageEncoder)
        copy = json.loads(dump, cls=MessageDecoder)
        self.assertEqual(orig, copy)


    def test_BindMessage(self):
        pid = 123
        uid = 456

        orig = messages.BindMessage(pid=pid, uid=uid)
        dump = json.dumps(orig, cls=MessageEncoder)
        copy = json.loads(dump, cls=MessageDecoder)
        self.assertEqual(orig, copy)
