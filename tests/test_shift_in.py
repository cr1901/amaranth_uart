import pytest
from amaranth import *
from amaranth.sim import Passive

from uart.params import *
from uart.rx import *


@pytest.mark.module(ShiftIn())
@pytest.mark.clks((1.0 / 12e6,))
def test_shift_in(sim_mod):
    sim, shift_in = sim_mod

    stop_take = Signal(1, reset=1)

    def take_proc():
        yield Passive()
        while True:
            if (yield shift_in.status.ready) and not (yield stop_take):  # noqa: E501
                yield shift_in.rd_data.eq(1)
            else:
                yield shift_in.rd_data.eq(0)
            yield

    def in_proc():
        def init():
            yield shift_in.num_data_bits.eq(NumDataBits.EIGHT)
            yield shift_in.parity.eq(Parity.const({"enabled": 0}))

        def shift_bit(bit):
            # Prepare sample
            yield shift_in.rx.eq(bit)
            yield shift_in.divider_tick.eq(1)
            yield

            # Do sample
            yield shift_in.divider_tick.eq(0)
            yield

            # Prepare shift
            yield shift_in.divider_tick.eq(1)
            yield

            # Do shift
            yield shift_in.divider_tick.eq(0)
            yield

        def write_data(dat):
            # Before Start
            yield shift_in.rx.eq(1)
            yield

            # Start
            yield from shift_bit(0)

            for i in range(8):
                bit = dat & 0x01
                yield from shift_bit(bit)

                dat = dat >> 1

            # Stop
            yield from shift_bit(1)

        yield from init()

        yield from write_data(0xAA)
        assert (yield shift_in.data == 0xAA)

        yield from shift_bit(1)
        assert (yield shift_in.data == 0xAA)

        yield stop_take.eq(0)
        for _ in range(3):
            yield

        assert (yield shift_in.status.ready == 0)

    sim.run(sync_processes=[in_proc, take_proc])
