import pytest
from amaranth import *
from amaranth.sim import Passive
from itertools import repeat

from uart.params import *
from uart.rx import *


@pytest.fixture
def rx_bit_period(request):
    """Calculate how many clock cycles should elapse before asserting
       divider_tick for ShiftIn."""
    clk_period = request.node.get_closest_marker("clks").args[0][0]
    baud = request.param
    return int(1 / (16 * clk_period * baud))


@pytest.fixture
def tx_bit_period(request):
    """Calculate how many clock cycles should elapse before transmitting
       the next bit."""
    clk_period = request.node.get_closest_marker("clks").args[0][0]
    baud = request.param
    return int(1 / (clk_period * baud))


@pytest.fixture
def div_proc(sim_mod, rx_bit_period):
    """Simulate divider_tick for ShiftIn. Simulates a timing generator supplied
       with a baud rate divisor register."""
    _, shift_in = sim_mod

    def task():
        yield Passive()
        while True:
            yield shift_in.divider_tick.eq(0)
            # A divide-by-n counter requires n - 1 ticks per period.
            for _ in range(rx_bit_period - 1):
                yield

            yield shift_in.divider_tick.eq(1)
            yield

    return task


@pytest.fixture
def shift_bit(sim_mod, tx_bit_period):
    """Simulate transmitting a bit to the receiver."""
    _, shift_in = sim_mod

    def task(bit):
        # Prepare sample
        yield shift_in.rx.eq(bit)

        # No clock dividers here, so no need for -1.
        for _ in range(tx_bit_period):
            yield

    return task


@pytest.fixture
def write_data(sim_mod, shift_bit):
    """Simulate transmitting a word to the receiver."""
    _, shift_in = sim_mod

    def task(dat):
        # Start
        yield from shift_bit(0)

        # num_data_bits is 0-3; we need 5-8.
        for _ in range((yield shift_in.num_data_bits) + 5):
            bit = dat & 0x01
            yield from shift_bit(bit)

            dat = dat >> 1

        # Stop
        yield from shift_bit(1)

    return task


@pytest.mark.module(ShiftIn())
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("rx_data,rx_bit_period,tx_bit_period",
                         zip((0xAA, 0x55, 0x00, 0xFF),
                             repeat(375000),
                             repeat(375000)),
                         indirect=["rx_bit_period", "tx_bit_period"])
def test_shift_in(sim_mod, rx_data, div_proc, shift_bit, write_data):
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
            yield

        yield from init()

        yield from write_data(rx_data)
        assert (yield shift_in.data == rx_data)

        yield from shift_bit(1)
        assert (yield shift_in.data == rx_data)

        yield stop_take.eq(0)
        for _ in range(3):
            yield

        assert (yield shift_in.status.ready == 0)
        assert (yield shift_in.status.overrun == 0)
        assert (yield shift_in.status.brk == 0)
        assert (yield shift_in.status.frame == 0)

    sim.run(sync_processes=[in_proc, div_proc, take_proc])
