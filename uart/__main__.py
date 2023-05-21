from .core import *
from .gen import *
from .sim import *

import argparse
import sys

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    p_action = parser.add_subparsers(dest="action")

    s_args = p_action.add_parser("sim")
    s_args.add_argument("target", choices=["all", "shift_in", "shift_out"])

    g_args = p_action.add_parser("gen")
    g_args.add_argument("yaml_file")

    args = parser.parse_args()
    if args.action == "sim":
        sim_funcs = {
            "shift_in": sim_shift_in,
            "shift_out": sim_shift_out
        }

        if args.target == "all":
            for sf in sim_funcs.values():
                sf()
        else:
            sim_funcs[args.target]()
    elif args.action == "gen":
        # Pop the "gen" argument of the script because FuseSoC is hardcoded
        # to look at sys.argv[1].
        sys.argv[1] = sys.argv[2]
        ug = UartGenerator()
        ug.run()
        ug.write()
