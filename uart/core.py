from amaranth import *

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
