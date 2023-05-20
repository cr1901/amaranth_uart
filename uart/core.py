from amaranth import *
from amaranth.lib import data


class BackingStore(data.Struct):
    start: unsigned(1)
    payload: unsigned(8)
    stop: unsigned(1)


class ShiftIn(Elaboratable):
    def __init__(self):
        self._view = Signal(BackingStore)
        self.inp = Signal(1)
        self.shift = Signal(1)

        # AXI stream interface- source
        self.valid = Signal(1)
        self.ready = Signal(1)
        self.data = Signal.like(self._view.payload)

    def elaborate(self, platform):
        shreg_len = len(Value.cast(self._view))
        count = Signal(range(shreg_len))

        ###

        m = Module()

        m.d.comb += self.data.eq(self._view.payload)

        with m.If(count == shreg_len):
            m.d.comb += self.valid.eq(1)
        with m.Elif(self.shift):
            m.d.sync += [
                self._view.as_value()[-1].eq(self.inp),
                self._view.as_value()[0:-1].eq(self._view.as_value()[1:]),
                count.eq(count + 1)
            ]

        with m.If(self.valid & self.ready):
            m.d.sync += count.eq(0)

        return m


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
    def __init__(self):
        self.out = Signal(1)
        self.counter = Signal(range(12000000))

    def elaborate(self, platform):

        ###

        m = Module()

        m.d.sync += [self.counter.eq(self.counter + 1)]

        with m.If(self.counter == 12000000):
            m.d.sync += [self.out.eq(~self.out)]

        return m
