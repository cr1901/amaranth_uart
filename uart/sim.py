from .core import *

from amaranth import *
from amaranth.sim import Simulator, Passive


def sim_shift_in():
    shift_in = ShiftIn()
    sim = Simulator(shift_in)
    sim.add_clock(1.0 / 12e6)

    stop_take = Signal(1)

    def take_proc():
        yield Passive()
        while True:
            if (yield shift_in.valid) and not (yield stop_take) and not (yield shift_in.ready):  # noqa: E501
                yield shift_in.ready.eq(1)
            else:
                yield shift_in.ready.eq(0)
            yield

    def in_proc():
        def shift_bit(bit):
            # Shift
            yield shift_in.shift.eq(1)
            yield shift_in.inp.eq(bit)
            yield

            # Pause- make sure bit shifted in takes effect.
            yield shift_in.shift.eq(0)
            yield

        def write_data(dat):
            # Before Start
            yield shift_in.inp.eq(1)
            yield

            # Start
            yield from shift_bit(0)

            for i in range(8):
                bit = dat & 0x01
                yield from shift_bit(bit)

                dat = dat >> 1

            # Stop
            yield from shift_bit(1)

        yield stop_take.eq(1)
        yield from write_data(0xAA)
        assert (yield shift_in._view.read.payload == 0xAA)

        yield from shift_bit(1)
        assert (yield shift_in._view.read.payload == 0xAA)

        yield stop_take.eq(0)
        for _ in range(3):
            yield

        assert (yield shift_in.valid == 0)

    sim.add_sync_process(in_proc)
    sim.add_sync_process(take_proc)

    with sim.write_vcd("shift_in.vcd", "shift_in.gtkw"):
        sim.run()


def sim_shift_out():
    shift_out = ShiftOut()
    sim = Simulator(shift_out)
    sim.add_clock(1.0 / 12e6)

    # def take_proc():
    #     yield Passive()
    #     while True:
    #         if (yield shift_out.ready) and not (yield stop_take) and not (yield shift_out.ready):  # noqa: E501
    #             yield shift_out.valid.eq(1)
    #         else:
    #             yield shift_out..eq(0)
    #         yield

    def in_proc():
        def shift_bit():
            # Shift
            yield shift_out.shift.eq(1)
            yield

            # Pause- make sure bit shifted out takes effect.
            yield shift_out.shift.eq(0)
            yield

        yield shift_out.data.eq(0xAA)
        yield shift_out.valid.eq(1)
        yield
        yield shift_out.valid.eq(0)
        yield

        assert (yield shift_out.ready == 0)

        for _ in range(11):
            yield from shift_bit()

        assert (yield shift_out.ready == 1)

    sim.add_sync_process(in_proc)

    with sim.write_vcd("shift_out.vcd", "shift_out.gtkw"):
        sim.run()
