from .params import *

from functools import partial
from typing import Union, Callable

from amaranth import *


class ShiftIn(Elaboratable):
    def __init__(self):
        self.rx = Signal(1, reset=1)

        self.num_data_bits = Signal(NumDataBits)
        self.parity = Signal(Parity)
        self.divider_tick = Signal(1)

        self.rd_data = Signal(1)
        self.rd_status = Signal(1)
        self.data = Signal(8)
        self.status = Signal(ShiftInStatus)

        self.shift_fsm = ShiftInFSM()

    def elaborate(self, platform):

        ###

        m = Module()
        m.submodules.shift_fsm = EnableInserter(self.divider_tick)(self.shift_fsm)  # noqa: E501

        m.d.comb += [
            self.shift_fsm.rx.eq(self.rx),
            self.shift_fsm.num_data_bits.eq(self.num_data_bits),
            self.shift_fsm.parity.eq(self.parity),
        ]

        with m.If(self.rd_data):
            m.d.sync += self.status.ready.eq(0)

        with m.If(self.rd_status):
            m.d.sync += [
                self.status.overrun.eq(0),
                self.status.parity.eq(0),
                self.status.frame.eq(0),
                self.status.brk.eq(0)
            ]

        # Highest priority b/c it's bad to lose data!
        with m.If(self.shift_fsm.wr_out & self.divider_tick):
            m.d.sync += [
                self.status.eq(self.shift_fsm.status),
                self.status.overrun.eq(self.status.ready & ~self.rd_data)
            ]

            with m.Switch(self.num_data_bits):
                for bits in NumDataBits:
                    with m.Case(bits.value):
                        valid = slice(3 - bits.value, None)
                        m.d.sync += self.data.eq(self.shift_fsm.shreg[valid])

        return m


class ShiftInFSM(Elaboratable):
    """
    This module requires an EnableInserter that asserts once every
    divider cycles to work as intended.
    """
    def __init__(self):
        self.rx = Signal(1)
        self.shreg = Signal(8)

        self.num_data_bits = Signal(NumDataBits)
        self.parity = Signal(Parity)

        self.wr_out = Signal(1)
        self.data = Signal(8)
        self.status = Signal(ShiftInStatus)

    def elaborate(self, platform):
        # Direct FSM Inputs
        rx_tmp = Signal(1)
        rx_parity = Signal(1)
        rx_zero = Signal(1)
        rx_negedge = Signal(1)
        sample_imminent = Signal(1)
        shift_imminent = Signal(1)

        # FSM Outputs
        shift = Signal(1)
        sample = Signal(1)
        schedule_sample_shift = Signal(1)

        # Internal signals.
        parity_error = Signal.like(rx_parity)
        rx_prev = Signal.like(self.rx, reset=1)
        rclk_count = Signal(4)
        rclk_bias = Signal(4)

        ###

        m = Module()

        m.d.comb += [
            rx_negedge.eq(~self.rx & rx_prev),
            # Anticipate that the sample should happen at the end of the
            # _next_ cycle, hence "-1".
            sample_imminent.eq(rclk_count == (rclk_bias + 7 - 1)),
            shift_imminent.eq(rclk_count == (rclk_bias + 15 - 1)),
        ]
        m.d.sync += [
            rx_prev.eq(self.rx),
            rclk_count.eq(rclk_count + 1)
        ]

        with m.If(sample):
            m.d.sync += [
                rx_tmp.eq(self.rx),
                # Although parity is only calculated on the data bits, we
                # can continuously calculate it because START bit won't effect
                # parity, and we calculate whether there's a parity error
                # before the STOP bit.
                rx_parity.eq(rx_parity + self.rx),
                rx_zero.eq(~(rx_zero | self.rx))
            ]

        with m.If(shift):
            m.d.sync += [
                self.shreg[-1].eq(rx_tmp),
                self.shreg[0:-1].eq(self.shreg[1:])
            ]

        with m.If(schedule_sample_shift):
            m.d.sync += [
                rx_tmp.eq(0),
                rx_parity.eq(0),
                rx_zero.eq(1),
                rclk_bias.eq(rclk_count),
                parity_error.eq(0)
            ]

            # If we're trying to schedule an RX due to frame error, go straight
            # to START state. Assume line went low once cycle before it was
            # detected (two cycles before this one).
            # Else: Schedule sample at 8 clock cycles from now.
            with m.If(self.status.frame):
                m.d.sync += rclk_bias.eq(rclk_count - 2)
            with m.Else():
                m.d.sync += rclk_bias.eq(rclk_count)

        with m.FSM():
            def per_bit_state(curr_prefix,
                              next_prefix_or_override: Union[str, Callable[[], None]],  # noqa: E501
                              *,
                              suppress_shift=False):
                with m.State(f"{curr_prefix}_1"):
                    with m.If(sample_imminent):
                        m.next = f"{curr_prefix}_SAMPLE"

                with m.State(f"{curr_prefix}_SAMPLE"):
                    m.d.comb += sample.eq(1)
                    m.next = f"{curr_prefix}_2"

                with m.State(f"{curr_prefix}_2"):
                    with m.If(shift_imminent):
                        m.next = f"{curr_prefix}_SHIFT"

                with m.State(f"{curr_prefix}_SHIFT"):
                    if not suppress_shift:
                        m.d.comb += shift.eq(1)
                    if isinstance(next_prefix_or_override, str):
                        m.next = f"{next_prefix_or_override}_1"
                    else:
                        next_prefix_or_override()

            with m.State("IDLE"):
                with m.If(rx_negedge):
                    m.d.comb += schedule_sample_shift.eq(1)
                    m.next = "START_1"

            # Don't bother doing an xfer if the sampled start bit wasn't 0.
            def check_for_start_glitch():
                with m.If(rx_tmp == 1):
                    m.next = "IDLE"
                with m.Else():
                    m.next = "DATA_BIT_0_1"

            per_bit_state("START", check_for_start_glitch, suppress_shift=True)  # noqa: E501
            per_bit_state("DATA_BIT_0", "DATA_BIT_1")
            per_bit_state("DATA_BIT_1", "DATA_BIT_2")
            per_bit_state("DATA_BIT_2", "DATA_BIT_3")
            per_bit_state("DATA_BIT_3", "DATA_BIT_4")

            def check_if_last_data_bit(next_prefix, num_bits: NumDataBits):
                with m.If(self.num_data_bits == num_bits):
                    check_parity_or_stop()
                with m.Else():
                    m.next = f"{next_prefix}_1"

            def check_parity_or_stop():
                with m.If(self.parity.enabled):
                    m.next = "PARITY_1"
                with m.Else():
                    m.next = "STOP_1"

            per_bit_state("DATA_BIT_4", partial(check_if_last_data_bit, "DATA_BIT_5", NumDataBits.FIVE))  # noqa: E501
            per_bit_state("DATA_BIT_5", partial(check_if_last_data_bit, "DATA_BIT_6", NumDataBits.SIX))  # noqa: E501
            per_bit_state("DATA_BIT_6", partial(check_if_last_data_bit, "DATA_BIT_7", NumDataBits.SEVEN))  # noqa: E501
            per_bit_state("DATA_BIT_7", check_parity_or_stop)

            def check_parity_error():
                with m.Switch(self.parity.kind):
                    with m.Case(ParityType.ODD):
                        m.d.sync += parity_error.eq(rx_parity != 1)
                    with m.Case(ParityType.EVEN):
                        m.d.sync += parity_error.eq(rx_parity != 0)
                    with m.Case(ParityType.ONE):
                        m.d.sync += parity_error.eq(rx_tmp != 1)
                    with m.Case(ParityType.ZERO):
                        m.d.sync += parity_error.eq(rx_tmp != 0)
                m.next = "STOP_1"

            per_bit_state("PARITY", check_parity_error, suppress_shift=True)  # noqa: E501

            # STOP bit is special, handle manually.
            with m.State("STOP_1"):
                with m.If(sample_imminent):
                    m.next = "STOP_SAMPLE"

            with m.State("STOP_SAMPLE"):
                m.d.comb += sample.eq(1)
                m.next = "STOP_2"

            with m.State("STOP_2"):
                # If we found a break, hold until we see the line released.
                with m.If(~rx_zero | (rx_zero & self.rx)):
                    m.d.comb += [
                        self.wr_out.eq(1),
                        self.status.ready.eq(1),
                        # Overrun is determined in parent module, use dummy
                        # value here.
                        self.status.overrun.eq(0),
                        self.status.parity.eq(parity_error),
                        self.status.brk.eq(rx_zero),
                        self.status.frame.eq(~rx_zero & ~rx_tmp)
                    ]

                    # If there was a frame error, or negedge, assume START bit
                    # was reached and try to recover.
                    with m.If(self.status.frame | ~self.rx):
                        m.d.comb += schedule_sample_shift.eq(1)
                        m.next = "START_1"
                    with m.Else():
                        m.next = "IDLE"

        return m
