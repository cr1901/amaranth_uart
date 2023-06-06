import pytest
from amaranth import *
from amaranth.sim import Passive
from itertools import chain, filterfalse, product, repeat

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
        for _ in range((yield shift_in.num_data_bits) + 5 +
                       int((yield shift_in.parity.enabled))):
            bit = dat & 0x01
            yield from shift_bit(bit)

            dat = dat >> 1

        # Stop
        yield from shift_bit(1)

    return task


@pytest.fixture
def take_proc(sim_mod, stop_take):
    """Convenience procedure to empty data when available."""
    _, shift_in = sim_mod

    def task():
        yield Passive()
        while True:
            if (yield shift_in.status.ready) and not (yield stop_take):  # noqa: E501
                yield shift_in.rd_data.eq(1)
            else:
                yield shift_in.rd_data.eq(0)
            yield

    return task


@pytest.fixture
def stop_take():
    """Signal which controls take_proc fixture."""
    stop_take = Signal(1, reset=1)
    return stop_take


@pytest.mark.module(ShiftIn())
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("rx_data,rx_bit_period,tx_bit_period",
                         zip((0xAA, 0x55, 0x00, 0xFF),
                             repeat(375000),
                             repeat(375000)),
                         indirect=["rx_bit_period", "tx_bit_period"])
def test_shift_in(sim_mod, rx_data, take_proc, div_proc,
                  shift_bit, write_data, stop_take):
    sim, shift_in = sim_mod

    def in_proc():
        def init():
            yield shift_in.num_data_bits.eq(NumDataBits.EIGHT)
            yield shift_in.parity.eq(Parity.const({"enabled": 0}))
            yield

        yield from init()

        yield from write_data(rx_data)
        assert (yield shift_in.data == rx_data)

        # Test that data isn't being overwritten now that rx is done.
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


@pytest.mark.module(ShiftIn())
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("data_size,rx_bit_period,tx_bit_period",
                         zip(NumDataBits,
                             repeat(375000),
                             repeat(375000)),
                         indirect=["rx_bit_period", "tx_bit_period"])
def test_data_width(sim_mod, data_size, take_proc, div_proc, write_data,
                    stop_take):
    sim, shift_in = sim_mod

    def in_proc():
        def init():
            yield shift_in.num_data_bits.eq(data_size)
            yield shift_in.parity.eq(Parity.const({"enabled": 0}))
            yield

        yield from init()

        yield from write_data(0xff)
        yield stop_take.eq(0)
        for _ in range(3):
            yield

        if data_size == NumDataBits.FIVE:
            assert (yield shift_in.data == 0b00011111)
        elif data_size == NumDataBits.SIX:
            assert (yield shift_in.data == 0b00111111)
        elif data_size == NumDataBits.SEVEN:
            assert (yield shift_in.data == 0b01111111)
        else:
            assert (yield shift_in.data == 0xff)

    sim.run(sync_processes=[in_proc, div_proc, take_proc])


@pytest.fixture
def data_and_parity_status(request):
    """Given data, calculate parity, and optionally corrupt it.
       Return the raw data to send, as well as whether the parity error
       is expected to be set or not (or None if "no parity")"""
    data, parity_type, corrupt = request.param

    if not parity_type:
        assert not corrupt
        return (data, None, corrupt)

    ones = bin(data).count("1")
    if parity_type == ParityType.EVEN:
        if ones % 2:
            data |= (1 << 7)
        if corrupt:
            data ^= 1
    elif parity_type == ParityType.ODD:
        if not (ones % 2):
            data |= (1 << 7)
        if corrupt:
            data ^= 1
    elif parity_type == ParityType.ONE:
        data |= (1 << 7)
        if corrupt:
            data ^= (1 << 7)
    else:  # ParityType.ZERO
        data &= ~(1 << 7)
        if corrupt:
            data ^= (1 << 7)

    return (data, parity_type, corrupt)


def parity_scenarios():
    def no_parity_and_yes_corrupt(d, p, c):
        return p is None and c

    parity_types = chain((None,), ParityType)
    data_values = (0, 0b0101010, 0b1010101, 127)
    corrupt = (False, True)

    return filterfalse(lambda dpc: no_parity_and_yes_corrupt(*dpc),
                       product(data_values, parity_types, corrupt))


@pytest.mark.module(ShiftIn())
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("data_and_parity_status,rx_bit_period,tx_bit_period",
                         zip(parity_scenarios(),
                             repeat(375000),
                             repeat(375000)),
                         indirect=["data_and_parity_status", "rx_bit_period",
                                   "tx_bit_period"])
def test_parity(sim_mod, data_and_parity_status, take_proc, div_proc,
                write_data, stop_take):
    sim, shift_in = sim_mod
    raw_data, parity_type, expected_parity_error = data_and_parity_status

    expected_data = raw_data & ~(1 << 7)

    def in_proc():
        def init():
            yield shift_in.num_data_bits.eq(NumDataBits.SEVEN)
            if parity_type:
                yield shift_in.parity.eq(Parity.const({"enabled": 1,
                                                       "kind": parity_type.value}))
            else:
                yield shift_in.parity.eq(Parity.const({"enabled": 0}))
            yield

        yield from init()

        yield from write_data(raw_data)
        yield stop_take.eq(0)
        for _ in range(3):
            yield

        if expected_parity_error is not None:
            assert (yield shift_in.status.parity == expected_parity_error)

        if expected_parity_error is False:
            assert (yield shift_in.data == expected_data)

    sim.run(sync_processes=[in_proc, div_proc, take_proc])


@pytest.mark.module(ShiftIn())
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("rx_bit_period,tx_bit_period",
                         ((375000, 375000 * 0.9),
                          (375000, 375000 * 1.10)),
                         indirect=["rx_bit_period", "tx_bit_period"])
def test_frame(sim_mod, take_proc, div_proc, write_data, stop_take):
    sim, shift_in = sim_mod

    def write_proc():
        yield Passive()
        while True:
            yield from write_data(0x55)

    def in_proc():
        def init():
            yield shift_in.num_data_bits.eq(NumDataBits.EIGHT)
            yield shift_in.parity.eq(Parity.const({"enabled": 0}))
            yield

        yield from init()

        yield stop_take.eq(0)
        while (yield shift_in.status.ready == 0):
            yield

        for _ in range(3):
            yield

        assert (yield shift_in.status.ready == 0)
        assert (yield shift_in.status.frame == 1)

        yield shift_in.rd_status.eq(1)
        yield
        yield shift_in.rd_status.eq(0)
        yield

        # Test that another byte is shifted in as we attempt to recover from
        # a frame error.
        for _ in range(500):
            if (yield shift_in.status.ready == 1):
                break
            yield
        else:
            assert False

    sim.run(sync_processes=[in_proc, div_proc, take_proc, write_proc])


@pytest.mark.module(ShiftIn())
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("rx_bit_period,tx_bit_period",
                         ((375000, 375000 * 0.9),),
                         indirect=["rx_bit_period", "tx_bit_period"])
def test_frame_start_glitch(sim_mod, take_proc, div_proc, write_data,
                            stop_take):
    sim, shift_in = sim_mod

    def write_proc():
        yield from write_data(0x55)

    def in_proc():
        def init():
            yield shift_in.num_data_bits.eq(NumDataBits.EIGHT)
            yield shift_in.parity.eq(Parity.const({"enabled": 0}))
            yield

        yield from init()

        yield stop_take.eq(0)
        while (yield shift_in.status.ready == 0):
            yield

        for _ in range(3):
            yield

        assert (yield shift_in.status.ready == 0)
        assert (yield shift_in.status.frame == 1)

        yield shift_in.rd_status.eq(1)
        yield
        yield shift_in.rd_status.eq(0)
        yield

        # Test that the start bit detected during the frame error was a glitch
        # and that no further bytes are received.
        for _ in range(500):
            if (yield shift_in.status.ready == 1):
                assert False
            yield

    sim.run(sync_processes=[in_proc, div_proc, take_proc, write_proc])
