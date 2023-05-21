import importlib
import sys

from amaranth import *
from amaranth.build import *
from amaranth_boards import icebreaker

from fusesoc.config import Config
from fusesoc.coremanager import CoreManager
from fusesoc.vlnv import Vlnv


class Top(Elaboratable):
    def __init__(self, uart):
        self.uart = uart

    def elaborate(self, platform):
        led = platform.request("led")

        ###

        m = Module()
        m.submodules += self.uart
        m.d.comb += [led.eq(self.uart.out)]

        return m


class FuseSocImporter:
    def __init__(self):
        self.cfg = Config()
        self.cm = CoreManager(self.cfg)

        for library in self.cfg.libraries:
            self.cm.add_library(library, [])

    def import_(self, name):
        vlnv = Vlnv(name)
        core = self.cm.get_core(vlnv)

        # To be reworked. Need a consistent way to refer to fusesoc python
        # modules inside the core config?
        module = core.get_files({})[0]["name"]
        # Can files_root be repurposed for "path to the module"?
        sys.path.append(core.files_root)

        # Return namespace exposed by __init__.py
        return importlib.import_module(module)


if __name__ == "__main__":
    importer = FuseSocImporter()
    uart = importer.import_("cr1901:amaranth:uart").Core()
    top = Top(uart)

    p = icebreaker.ICEBreakerPlatform()
    p.add_resources(p.break_off_pmod)
    plan = p.build(top, do_build=False, debug_verilog=True)
    products = plan.execute_local(run_script=True)
    p.toolchain_program(products, "top")
