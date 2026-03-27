import sys
import os
from pathlib import Path

_toolchain_dir = str(Path(__file__).resolve().parent.parent / "modules" / "Tezos_module" / "toolchain")
if _toolchain_dir not in sys.path:
    sys.path.insert(0, _toolchain_dir)

_dapp_path = os.path.join(_toolchain_dir, "dapp.py")
exec(open(_dapp_path).read(), {**globals(), "__file__": _dapp_path})
