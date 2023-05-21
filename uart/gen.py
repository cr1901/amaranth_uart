from .core import *

from amaranth.back import verilog
from fusesoc.capi2.generator import Generator


class UartGenerator(Generator):
    output_file = "uart.v"

    def __init__(self):
        super().__init__()
        self.clk_freq = self.config.get('clk_freq', 12000000)
        self.baud_rate = self.config.get('baud_rate', 19200)

    def run(self):
        files = self.gen_core()
        self.add_files(files)

    # Generate a core to be included in another project.
    def gen_core(self):
        m = Core(self.clk_freq, self.baud_rate)

        ios = [m.tx, m.rx, m.brk, m.tx_tvalid, m.tx_tready, m.tx_tdata,
               m.rx_tvalid, m.rx_tready, m.rx_tdata]

        with open(self.output_file, "w") as fp:
            fp.write(str(verilog.convert(m, name="uart", ports=ios)))

        return [{"uart.v": {"file_type": "verilogSource"}}]
