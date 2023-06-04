import enum

from amaranth import *
from amaranth.lib import data


class BackingStore(data.Struct):
    start: unsigned(1)
    payload: unsigned(8)
    stop: unsigned(1)


class NumDataBits(enum.Enum):
    FIVE = 0
    SIX = 1
    SEVEN = 2
    EIGHT = 3


class NumStopBits(enum.Enum):
    ONE = 0
    TWO = 1


class ParityType(enum.Enum):
    ODD = 0
    EVEN = 1
    ONE = 2
    ZERO = 3


class Parity(data.Struct):
    enabled: unsigned(1)
    kind: ParityType


class ShiftInStatus(data.Struct):
    ready: unsigned(1)
    overrun: unsigned(1)
    parity: unsigned(1)
    frame: unsigned(1)
    brk: unsigned(1)
