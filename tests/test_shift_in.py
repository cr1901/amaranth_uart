import pytest
from amaranth import *
from amaranth.sim import Passive

from uart.core import *


@pytest.mark.module(ShiftIn())
@pytest.mark.clks((1.0 / 12e6,))
def test_shift_in(sim_mod):
    sim, shift_in = sim_mod

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
        assert (yield shift_in.data == 0xAA)

        yield from shift_bit(1)
        assert (yield shift_in.data == 0xAA)

        yield stop_take.eq(0)
        for _ in range(3):
            yield

        assert (yield shift_in.valid == 0)

    sim.run(sync_processes=[in_proc, take_proc])
