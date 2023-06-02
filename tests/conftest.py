import pytest

from amaranth.sim import Simulator


class SimulatorFixture:
    def __init__(self, mod, clks, req):
        self.name = req.function.__name__
        self.sim = Simulator(mod.args[0])

        for clk in clks.args[0]:
            self.sim.add_clock(clk)

    def run(self, sync_processes, processes=[]):
        for s in sync_processes:
            self.sim.add_sync_process(s)

        for p in processes:
            self.sim.add_process(p)

        with self.sim.write_vcd(self.name + ".vcd", self.name + ".gtkw"):
            self.sim.run()


@pytest.fixture
def sim_mod(request):
    mod = request.node.get_closest_marker("module")
    clks = request.node.get_closest_marker("clks")
    return (SimulatorFixture(mod, clks, request), mod.args[0])
