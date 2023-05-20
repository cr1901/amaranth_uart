from amaranth import *
from amaranth.lib import data


class ShiftIn(Elaboratable):
    class BackingStore(data.Union):
        read: data.StructLayout({
            "start": unsigned(1),
            "payload": unsigned(8),
            "stop": unsigned(1)
        })
        write: data.FlexibleLayout(
            fields={
                "msb": data.Field(unsigned(1), offset=9),
                "lsbs": data.Field(unsigned(9), offset=0),
                "msbs": data.Field(unsigned(9), offset=1),
            },
            size=10
        )

    def __init__(self):
        self._view = Signal(ShiftIn.BackingStore)
        self.inp = Signal(1)
        self.shift = Signal(1)

        # AXI stream interface- source
        self.valid = Signal(1)
        self.ready = Signal(1)
        self.data = Signal.like(self._view.read.payload)

    def elaborate(self, platform):
        shreg_len = len(Value.cast(self._view))
        count = Signal(range(shreg_len))

        ###

        m = Module()

        m.d.comb += self.data.eq(self._view.read.payload)

        with m.If(count == shreg_len):
            m.d.comb += self.valid.eq(1)
        with m.Elif(self.shift):
            m.d.sync += [
                self._view.write.msb.eq(self.inp),
                self._view.write.lsbs.eq(self._view.write.msbs),
                count.eq(count + 1)
            ]

        with m.If(self.valid & self.ready):
            m.d.sync += count.eq(0)

        return m


class ShiftOut(Elaboratable):
    class BackingStore(data.Union):
        write: data.StructLayout({
            "start": unsigned(1),
            "payload": unsigned(8),
            "stop": unsigned(1)
        })
        read: data.FlexibleLayout(
            fields={
                "lsb": data.Field(unsigned(1), offset=0),
                "lsbs": data.Field(unsigned(9), offset=0),
                "msbs": data.Field(unsigned(9), offset=1),
            },
            size=10
        )

    def __init__(self):
        self._view = Signal(ShiftOut.BackingStore, reset={"read": {"lsb": 1}})
        self.out = Signal(1)
        self.shift = Signal(1)

        # AXI stream interface
        self.valid = Signal(1)
        self.ready = Signal(1)
        self.data = Signal.like(self._view.write.payload)

    def elaborate(self, platform):
        shreg_len = len(Value.cast(self._view))
        count = Signal(range(shreg_len))

        ###

        m = Module()

        m.d.comb += self.out.eq(self._view.read.lsb)

        with m.If(count == 0):
            m.d.comb += self.ready.eq(1)
        with m.Elif(self.shift):
            m.d.sync += [
                self._view.read.lsbs.eq(self._view.read.msbs),
                count.eq(count - 1)
            ]

        with m.If(self.valid & self.ready):
            m.d.sync += [
                self._view.write.start.eq(0),
                self._view.write.payload.eq(self.data),
                self._view.write.stop.eq(1),
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
