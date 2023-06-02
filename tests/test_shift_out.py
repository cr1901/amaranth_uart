import pytest
from amaranth import *

from uart.core import *


@pytest.mark.module(ShiftOut())
@pytest.mark.clks((1.0 / 12e6,))
def test_shift_out(sim_mod):
    sim, shift_out = sim_mod

    def out_proc():
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

    sim.run(sync_processes=[out_proc])
