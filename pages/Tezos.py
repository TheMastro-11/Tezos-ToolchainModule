import sys
import os
from pathlib import Path

_toolchain_dir = str(Path(__file__).resolve().parent.parent / "modules" / "Tezos_module" / "toolchain")
if _toolchain_dir not in sys.path:
    sys.path.insert(0, _toolchain_dir)

_original_cwd = os.getcwd()
os.chdir(_toolchain_dir)
try:
    exec(open(os.path.join(_toolchain_dir, "dapp.py")).read())
finally:
    os.chdir(_original_cwd)
