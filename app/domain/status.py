from enum import Enum


class AppStatus(str, Enum):
    STARTING = "starting"
    READY = "ready"
    RECORDING = "recording"
    WORKING = "working"
    BUSY = "busy"
    ERROR = "error"
    DISCONNECTED = "disconnected"
