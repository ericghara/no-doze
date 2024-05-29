import json
from datetime import datetime
from typing import Callable, Any
from typing import Dict

import core.common.message.messages as messages
class MessageEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.timestamp()
        elif isinstance(obj, messages.InhibitMessage):
            return obj.__dict__
        elif isinstance(obj, messages.BindMessage):
            return obj.__dict__
        return super().default(obj)

class MessageDecoder(json.JSONDecoder):

    def __init__(self):
        super().__init__(object_hook=self.object_hook)

    def object_hook(self, d: Dict) -> Any:
        if isinstance(d, dict):
            t = d.get("type", "[UNKNOWN]")
            o = None
            match t:
                case messages.BindMessage.__name__:
                    o = messages.BindMessage(pid=d["pid"], gid=d["gid"], attempt=d["attempt"])
                case messages.InhibitMessage.__name__:
                    o = messages.InhibitMessage(pid=d["pid"], gid=d["gid"],
                                                expiry_timestamp=datetime.fromtimestamp(d["expiry_timestamp"]))
                case _:
                    raise ValueError(f"Could not match {t} to a type.")
            return o
        else:
            raise ValueError(f"Received a non dictionary input")




