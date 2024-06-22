from datetime import datetime
from typing import *

API_VERSION = 2

class InhibitMessage:
    def __init__(self, pid:int, uid: int, expiry_timestamp: datetime):
        self.pid : int = pid
        self.uid : int = uid
        self.expiry_timestamp : datetime = expiry_timestamp
        self.type: str = type(self).__name__
        self.version: int = API_VERSION

    def __eq__(self, other: Any) -> bool:
        if type(other) is type(self):
            return other.__dict__ == self.__dict__
        return NotImplemented

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self) -> str:
        vals = ", ".join([f"{k}={v}" for k,v in self.__dict__.items()])
        return f"{type(self).__name__}({vals})"


class BindMessage:

    def __init__(self, pid: int, uid:int, attempt: int):
        self.pid : int = pid
        self.uid : int = uid
        self.attempt : int = attempt
        self.type : str = type(self).__name__
        self.version : int = API_VERSION

    def __eq__(self, other: Any) -> bool:
        if type(other) is type(self):
            return other.__dict__ == self.__dict__
        return NotImplemented

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self) -> str:
        vals = ", ".join([f"{k}={v}" for k, v in self.__dict__.items()])
        return f"{type(self).__name__}({vals})"

