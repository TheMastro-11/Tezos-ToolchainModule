"""
tezos_interface.py
==================
Integration layer between Rosetta SC (flask_backend.py) and the
Tezos toolchain (tezos-contract-2.0).

Expected location in the repo:
    Tezos_module/tezos_module/tezos_interface.py

The toolchain source files (contractUtils.py, main.py, jsonUtils.py,
folderScan.py, csvUtils.py) must live in:
    Tezos_module/toolchain/

Contracts live in:
    Tezos_module/contracts/

The wallet file is expected at:
    Tezos_module/tezos_module/tezos_wallets/wallet.json

Public functions consumed by flask_backend.py:
    - is_tezos_available()
    - compile_and_deploy_tezos_contracts(contract_name, deploy, initial_balance)
    - fetch_tezos_contracts()
    - fetch_tezos_entrypoints(contract_name)
    - fetch_tezos_contract_context(contract_name, entrypoint_name)
    - interact_with_tezos_contract(contract_name, entrypoint_name, parameters, tez_amount)
    - run_tezos_trace(trace_file)           ← replaces the CSV placeholder in flask_backend
"""

import sys
import json
import traceback
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup – inject toolchain folder so its modules are importable
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent          # Tezos_module/tezos_module/
_MODULE_ROOT = _THIS_DIR.parent                       # Tezos_module/
_TOOLCHAIN_DIR = _MODULE_ROOT / "toolchain"
_CONTRACTS_DIR = _MODULE_ROOT / "contracts"
_WALLET_FILE = _THIS_DIR / "tezos_wallets" / "wallet.json"
_ADDRESS_LIST = _CONTRACTS_DIR / "addressList.json"
_TRACE_ROOT = _TOOLCHAIN_DIR / "rosetta_traces"

if str(_TOOLCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLCHAIN_DIR))

# ---------------------------------------------------------------------------
# Lazy imports from the toolchain (graceful failure if pytezos not installed)
# ---------------------------------------------------------------------------

def is_tezos_available() -> bool:
    """Return True if pytezos and the toolchain modules can be imported."""
    try:
        import pytezos  # noqa: F401
        import contractUtils  # noqa: F401
        return True
    except ImportError:
        return False


def _require_tezos():
    if not is_tezos_available():
        raise ImportError(
            "pytezos or the Tezos toolchain modules are not installed. "
            "Run: pip install pytezos"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_wallets() -> dict:
    """Load the wallet.json file that maps label → private key."""
    if not _WALLET_FILE.exists():
        raise FileNotFoundError(f"Wallet file not found: {_WALLET_FILE}")
    with open(_WALLET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_client(wallet_label: str = "player1"):
    """Return a pytezos client configured for Ghostnet with the given wallet."""
    from pytezos import pytezos as _pytezos
    wallets = _load_wallets()
    key = wallets.get(wallet_label)
    if not key:
        raise KeyError(
            f"Wallet label '{wallet_label}' not found in wallet.json. "
            f"Available labels: {list(wallets.keys())}"
        )
    return _pytezos.using(shell="ghostnet", key=key)


def _get_address(contract_name: str) -> str:
    """Resolve a contract name to its on-chain KT1 address."""
    from jsonUtils import getAddress, resolveAddress  # noqa
    address_map = getAddress()
    return resolveAddress(addressValid=address_map, contractId=contract_name)


def _find_contract_source(contract_name: str) -> Path:
    """
    Locate a Rosetta contract .py file by name.
    Searches contracts/Rosetta/<contract_name>/<contract_name>Rosetta.py
    and falls back to a plain name scan.
    """
    rosetta_dir = _CONTRACTS_DIR / "Rosetta"
    # Primary: exact folder + file naming convention
    candidate = rosetta_dir / contract_name / f"{contract_name}Rosetta.py"
    if candidate.exists():
        return candidate
    # Fallback: glob search
    matches = list(rosetta_dir.rglob(f"{contract_name}*.py"))
    matches = [m for m in matches if "__pycache__" not in str(m)]
    if not matches:
        raise FileNotFoundError(
            f"No SmartPy source file found for contract '{contract_name}' "
            f"under {rosetta_dir}"
        )
    return matches[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_and_deploy_tezos_contracts(
    contract_name: str,
    deploy: bool = True,
    initial_balance: float = 0,
) -> dict:
    """
    Compile a SmartPy contract (and optionally originate it on Ghostnet).

    Parameters
    ----------
    contract_name : str
        Name of the contract folder under contracts/Rosetta/ (e.g. "Auction").
    deploy : bool
        If True, originate the compiled contract on Ghostnet.
    initial_balance : float
        Initial XTZ balance to send to the originated contract.

    Returns
    -------
    dict  with keys: success, message, address (if deployed), compile_log
    """
    _require_tezos()
    from contractUtils import (  # noqa
        compileContract, origination, contractInfoResult,
        parseCompilationLog,
    )
    from jsonUtils import addressUpdate, updateDeploymentLevel  # noqa
    from main import findCompiledArtifactDir  # noqa

    result = {"success": False, "message": "", "compile_log": "", "address": None}

    try:
        source_path = _find_contract_source(contract_name)
        compile_output = compileContract(str(source_path))
        result["compile_log"] = compile_output.get("log", "") if isinstance(compile_output, dict) else ""
        result["message"] = f"Contract '{contract_name}' compiled successfully."

        if not deploy:
            result["success"] = True
            return result

        # Locate compiled artefacts
        from contractUtils import getCompiledContractDir  # noqa
        compiled_dir = getCompiledContractDir(str(source_path))
        artifact_dir = findCompiledArtifactDir(str(compiled_dir))
        if not artifact_dir:
            raise FileNotFoundError(
                f"Compiled .tz artefacts not found in {compiled_dir}"
            )

        contract_tz = Path(artifact_dir) / "step_001_cont_0_contract.tz"
        storage_tz = Path(artifact_dir) / "step_001_cont_0_storage.tz"

        michelson_code = contract_tz.read_text(encoding="utf-8")
        initial_storage = storage_tz.read_text(encoding="utf-8")

        wallets = _load_wallets()
        default_wallet = next(iter(wallets))
        client = _get_client(default_wallet)

        op_result = origination(
            client=client,
            michelsonCode=michelson_code,
            initialStorage=initial_storage,
            initialBalance=initial_balance,
        )

        if op_result is None:
            result["message"] = "Origination timed out or failed."
            return result

        deploy_info = contractInfoResult(op_result)
        contract_address = deploy_info.get("address")

        # Persist address and deployment level
        addressUpdate(contract=contract_name, newAddress=contract_address)
        if "ConfirmedLevel" in deploy_info:
            updateDeploymentLevel(
                contract=contract_name,
                confirmedLevel=deploy_info["ConfirmedLevel"],
            )

        result.update({
            "success": True,
            "address": contract_address,
            "message": f"Contract '{contract_name}' originated at {contract_address}.",
            "deploy_info": deploy_info,
        })

    except Exception as e:
        result["message"] = str(e)
        result["traceback"] = traceback.format_exc()

    return result


def fetch_tezos_contracts() -> list:
    """
    Return a list of contract names that have a known KT1 address
    (i.e. have been deployed via this toolchain).
    """
    _require_tezos()
    try:
        from jsonUtils import getAddress  # noqa
        address_map = getAddress()
        return [name for name, addr in address_map.items() if addr]
    except Exception:
        return []


def fetch_tezos_entrypoints(contract_name: str) -> list:
    """
    Return the list of entrypoint names for a deployed contract.
    """
    _require_tezos()
    from contractUtils import entrypointAnalyse  # noqa
    try:
        client = _get_client(next(iter(_load_wallets())))
        address = _get_address(contract_name)
        schema = entrypointAnalyse(client=client, contractAddress=address)
        return list(schema.keys())
    except Exception as e:
        raise RuntimeError(f"Could not fetch entrypoints for '{contract_name}': {e}") from e


def fetch_tezos_contract_context(contract_name: str, entrypoint_name: str) -> dict:
    """
    Return parameter metadata for a specific entrypoint.

    Returns
    -------
    dict with keys:
        entrypoint   – entrypoint name
        params       – list of (param_name, type_info) tuples, or "unit"
    """
    _require_tezos()
    from contractUtils import entrypointAnalyse  # noqa
    try:
        client = _get_client(next(iter(_load_wallets())))
        address = _get_address(contract_name)
        schema = entrypointAnalyse(client=client, contractAddress=address)
        params = schema.get(entrypoint_name, [])
        return {
            "entrypoint": entrypoint_name,
            "params": params,
        }
    except Exception as e:
        raise RuntimeError(
            f"Could not fetch context for '{contract_name}.{entrypoint_name}': {e}"
        ) from e


def interact_with_tezos_contract(
    contract_name: str,
    entrypoint_name: str,
    parameters,
    tez_amount: float = 0,
    wallet_label: str = "player1",
) -> dict:
    """
    Call an entrypoint on a deployed Tezos contract.

    Parameters
    ----------
    contract_name    : str
        Name of the contract (must be in addressList.json).
    entrypoint_name  : str
        Name of the entrypoint to call.
    parameters       : str | list | dict | None
        Raw parameter value(s). Pass None or [] for unit entrypoints.
    tez_amount       : float
        Amount of XTZ to attach to the call.
    wallet_label     : str
        Key in wallet.json to use as the caller.

    Returns
    -------
    dict with keys: success, result (on success), error (on failure)
    """
    _require_tezos()
    from contractUtils import entrypointCall, callInfoResult  # noqa

    try:
        client = _get_client(wallet_label)
        address = _get_address(contract_name)

        # Normalise parameters
        if parameters == "" or parameters is None:
            params = None
        elif isinstance(parameters, str):
            # Try JSON parse first; otherwise treat as plain string
            try:
                params = json.loads(parameters)
            except (json.JSONDecodeError, ValueError):
                params = parameters
        else:
            params = parameters

        op_result = entrypointCall(
            client=client,
            contractAddress=address,
            entrypointName=entrypoint_name,
            parameters=params,
            tezAmount=Decimal(str(tez_amount)),
        )
        call_info = callInfoResult(opResult=op_result)
        call_info["contract"] = contract_name
        call_info["entryPoint"] = entrypoint_name

        return {"success": True, "result": call_info}

    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


def run_tezos_trace(trace_file: str) -> dict:
    """
    Execute a Rosetta JSON execution trace for the Tezos chain.

    Parameters
    ----------
    trace_file : str
        Filename (relative to rosetta_traces/) e.g. "Auction.json"
        or a subdirectory path like "Bet/BetPlayer1Win.json".

    Returns
    -------
    dict  with keys: success, results (list of per-step info), error
    """
    _require_tezos()
    from main import executionSetupJson  # noqa
    from jsonUtils import normalizeTraceTitle  # noqa

    trace_path = _TRACE_ROOT / trace_file
    if not trace_path.exists():
        return {"success": False, "error": f"Trace file not found: {trace_path}"}

    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            trace_data = json.load(f)

        # executionSetupJson uses the tezos section of the trace
        contract_id = trace_data.get("trace_title", trace_path.stem)
        result_dict = executionSetupJson(contractId=contract_id, traceData=trace_data)
        return {"success": True, "results": result_dict}

    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
