from .params import *

from typing import Optional

from amaranth import *


class ShiftOut(Elaboratable):
    def __init__(self):
        self._view = Signal(BackingStore, reset={"start": 1})
        self.out = Signal(1)
        self.shift = Signal(1)

        # AXI stream interface
        self.valid = Signal(1)
        self.ready = Signal(1)
        self.data = Signal.like(self._view.payload)

    def elaborate(self, platform):
        shreg_len = len(Value.cast(self._view))
        count = Signal(range(shreg_len))

        ###

        m = Module()

        m.d.comb += self.out.eq(self._view.as_value()[0])

        with m.If(count == 0):
            m.d.comb += self.ready.eq(1)
        with m.Elif(self.shift):
            m.d.sync += [
                self._view.as_value()[0:-1].eq(self._view.as_value()[1:]),
                count.eq(count - 1)
            ]

        with m.If(self.valid & self.ready):
            m.d.sync += [
                self._view.start.eq(0),
                self._view.payload.eq(self.data),
                self._view.stop.eq(1),
                count.eq(shreg_len)
            ]

        return m


# Core we want to share with the world. Must be visible in __init__.py due
# to importlib limitations.
class Core(Elaboratable):
    def __init__(self, divisor: Optional[int] = None):
        self.out = Signal(1)

        self.tx = Signal(1)
        self.rx = Signal(1)
        self.brk = Signal(1)

        self.tx_tvalid = Signal(1)
        self.tx_tready = Signal(1)
        self.tx_tdata = Signal(8)

        self.rx_tvalid = Signal(1)
        self.rx_tready = Signal(1)
        self.rx_tdata = Signal(8)

        if divisor:
            self.divisor = C(divisor, 16)
        else:
            self.divisor = Signal(16)
        self.counter = Signal(range(12000000))

    def elaborate(self, platform):

        ###

        m = Module()

        m.d.sync += [self.counter.eq(self.counter + 1)]

        with m.If(self.counter == 12000000):
            m.d.sync += [self.out.eq(~self.out)]

        return m
