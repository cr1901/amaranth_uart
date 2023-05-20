from .core import *
from .sim import *

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    p_action = parser.add_subparsers(dest="action")

    s_args = p_action.add_parser("sim")
    s_args.add_argument("target", choices=["all", "shift_in", "shift_out"])

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
