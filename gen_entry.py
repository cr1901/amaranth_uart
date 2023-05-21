import subprocess
import os
import sys

# Workaround for FuseSoC hardcoding generator arguments to an interpreter,
# a script, and a single YAML file.
if __name__ == "__main__":
    try:
        os.environ["PYTHONPATH"] += os.path.dirname(__file__)
    except KeyError:
        os.environ["PYTHONPATH"] = os.path.dirname(__file__)
    subprocess.run(["python3", "-m", "uart", "gen", sys.argv[1]])
