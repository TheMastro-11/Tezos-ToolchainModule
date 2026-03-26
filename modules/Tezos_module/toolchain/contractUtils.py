from pytezos import pytezos
from pathlib import Path
import traceback
from pytezos.michelson.parse import michelson_to_micheline
import time
import subprocess
import sys
import json
import re
from decimal import Decimal

MUTEZ_CONV = 1000000


def _normalize_compiled_name(contract_path: Path) -> str:
    suite = contract_path.parent.parent.name
    family = contract_path.parent.name
    implementation = contract_path.stem
    return f"{suite}_{family}_{implementation}"


def getCompiledRoot() -> Path:
    compiled_root = Path(__file__).resolve().parent / "compiled"
    compiled_root.mkdir(parents=True, exist_ok=True)
    return compiled_root


def getCompiledContractDir(contractPath) -> Path:
    contract_path = Path(contractPath).resolve()
    output_dir = getCompiledRoot() / _normalize_compiled_name(contract_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def getCurrentBlockLevel(client):
    header = client.shell.head.header()
    return int(header["level"])


def waitForBlockDelay(client, startBlockLevel, waitingTime, pollIntervalSeconds=10):
    waiting_blocks = int(waitingTime or 0)

    if waiting_blocks <= 0:
        return startBlockLevel

    target_level = int(startBlockLevel) + waiting_blocks
    print(
        f"Waiting for {waiting_blocks} block(s) before the next step. "
        f"Start level: {startBlockLevel}, target level: {target_level}"
    )

    current_level = getCurrentBlockLevel(client)
    while current_level < target_level:
        remaining_blocks = target_level - current_level
        print(
            f"   -> Current level: {current_level}. "
            f"Waiting for {remaining_blocks} more block(s)..."
        )
        time.sleep(pollIntervalSeconds)
        current_level = getCurrentBlockLevel(client)

    print(f"   -> Target level reached: {current_level}")
    return current_level


def compileContract(contractPath):
    contract_path = Path(contractPath).resolve()
    print(f">>> Compiling '{contract_path}'...")

    if not contract_path.is_file():
        raise FileNotFoundError(f"'{contract_path}' not found.")

    output_dir = getCompiledContractDir(contract_path)

    for artifact in output_dir.rglob("step_*"):
        if artifact.is_file():
            artifact.unlink()
    for extra_dir in sorted(output_dir.iterdir()):
        if extra_dir.is_dir() and extra_dir.name.endswith("Rosetta"):
            for nested in extra_dir.iterdir():
                if nested.is_file():
                    nested.unlink()
            extra_dir.rmdir()

    metadata = {
        "contract_id": f"{contract_path.parent.relative_to(contract_path.parents[2]).as_posix()}:{contract_path.stem}",
        "contract_name": _normalize_compiled_name(contract_path),
        "source": str(contract_path),
        "output_dir": str(output_dir)
    }

    try:
        result = subprocess.run(
            [sys.executable, str(contract_path)],
            cwd=str(output_dir),
            check=True,
            capture_output=True,
            text=True
        )

        # Print subprocess output so redirect_stdout in the dapp captures it.
        subprocess_output = "\n".join(filter(None, [result.stdout, result.stderr])).strip()
        if subprocess_output:
            print(subprocess_output)

        nested_dirs = sorted(
            path for path in output_dir.iterdir()
            if path.is_dir() and path.name.endswith("Rosetta")
        )
        if nested_dirs:
            artifact_dir = nested_dirs[0]
            for artifact in artifact_dir.iterdir():
                target = output_dir / artifact.name
                if target.exists() and target.is_file():
                    target.unlink()
                artifact.replace(target)
            artifact_dir.rmdir()

        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(f">>> '{contract_path}' compiled in '{output_dir}'!")
        return result

    except subprocess.CalledProcessError as e:
        # Always print both streams so the dapp terminal buffer captures them
        # before the exception interrupts the flow.
        subprocess_output = "\n".join(filter(None, [e.stdout, e.stderr])).strip()
        if subprocess_output:
            print(subprocess_output)

        details = subprocess_output or f"Exit code {e.returncode}"
        raise RuntimeError(f"Compilation failed for '{contract_path}':\n{details}") from e


def parseCompilationLog(artifactDir):
    logPath = Path(artifactDir) / "log.txt"
    if not logPath.exists():
        return []

    log = logPath.read_text(encoding="utf-8")
    artifacts = []

    creating_pattern = re.compile(r'Creating contract (KT1\w+)')
    contract_file_pattern = re.compile(
        r'file \S+/(step_(\d+)_cont_(\d+))_contract\.tz contract (\w+)'
    )

    placeholders = creating_pattern.findall(log)
    contract_files = contract_file_pattern.findall(log)

    for i, (step_prefix, step_num, cont_num, contract_name) in enumerate(contract_files):
        placeholder = placeholders[i] if i < len(placeholders) else None
        artifacts.append({
            "step_prefix": step_prefix,
            "step_num": int(step_num),
            "cont_num": int(cont_num),
            "contract_name": contract_name,
            "placeholder": placeholder
        })

    return sorted(artifacts, key=lambda a: (a["step_num"], a["cont_num"]))


def multiOrigination(client, artifactDir, contractId, initialBalance, normalizeContractNameFn, addressUpdateFn, updateDeploymentLevelFn):
    artifactDir = Path(artifactDir)
    artifacts = parseCompilationLog(artifactDir)

    if not artifacts:
        raise FileNotFoundError(f"No artifacts found in '{artifactDir}' (missing or empty log.txt).")

    baseName = normalizeContractNameFn(contractId)
    deployedAddresses = {}
    results = []

    for artifact in artifacts:
        prefix = artifact["step_prefix"]
        contractTzPath = artifactDir / f"{prefix}_contract.tz"
        storageTzPath = artifactDir / f"{prefix}_storage.tz"

        if not contractTzPath.exists() or not storageTzPath.exists():
            raise FileNotFoundError(f"Missing compiled files for {prefix} in '{artifactDir}'.")

        contractTz = contractTzPath.read_text(encoding="utf-8")
        storageTz = storageTzPath.read_text(encoding="utf-8")

        for placeholder, realAddress in deployedAddresses.items():
            storageTz = storageTz.replace(placeholder, realAddress)

        artifactName = re.sub(r"Rosetta$", "", artifact["contract_name"])
        displayName = f"{baseName}_{artifactName}"

        print(f"\n>>> Deploying '{displayName}' ({artifact['contract_name']})...")
        op_result = origination(client, contractTz, storageTz, initialBalance)

        if op_result is None:
            raise RuntimeError(f"Deploy failed for '{displayName}'.")

        contractInfo = contractInfoResult(op_result)

        if artifact["placeholder"]:
            deployedAddresses[artifact["placeholder"]] = contractInfo["address"]

        addressUpdateFn(contract=displayName, newAddress=contractInfo["address"])

        if "ConfirmedLevel" in contractInfo:
            updateDeploymentLevelFn(contract=displayName, confirmedLevel=contractInfo["ConfirmedLevel"])

        print(f">>> '{displayName}' deployed at {contractInfo['address']}")
        results.append({
            "artifact": artifact,
            "info": contractInfo,
            "addressName": displayName
        })

    return results


def runScenario(scenarioPath):
    scenario_path = Path(scenarioPath)

    if not scenario_path.is_file():
        raise FileNotFoundError(f"'{scenarioPath}' not found.")

    try:
        result = subprocess.run(
            [sys.executable, str(scenario_path)],
            cwd=str(scenario_path.parent),
            check=True,
            capture_output=True,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        details = []
        if e.stdout:
            details.append(e.stdout.strip())
        if e.stderr:
            details.append(e.stderr.strip())
        message = "\n\n".join(part for part in details if part)
        if message:
            raise RuntimeError(f"Scenario execution failed for '{scenarioPath}':\n{message}") from e
        raise RuntimeError(f"Scenario execution failed for '{scenarioPath}'.") from e


def origination(client, michelsonCode, initialStorage, initialBalance):
    parsed_code = michelson_to_micheline(michelsonCode)
    parsed_storage = michelson_to_micheline(initialStorage)

    print("Origination")

    try:
        op_group = client.origination(
            script={
                'code': parsed_code,
                'storage': parsed_storage
            },
            balance=initialBalance * MUTEZ_CONV
        ).autofill().sign()

        op_hash = op_group.inject(_async=False)['hash']
        print(f"Operation send! Hash: {op_hash}")

        start_time = time.time()
        timeout = 500
        op_result = None

        while time.time() - start_time < timeout:
            try:
                op_result = client.shell.blocks[-10:].find_operation(op_hash)
                print("Operation Found")
                op_result["confirmed_level"] = getCurrentBlockLevel(client)
                break
            except StopIteration:
                print(f"   -> Not yet completed (time passed: {int(time.time() - start_time)}s)")
                time.sleep(15)

        if not op_result:
            print(f"\n❌ TIMEOUT: The operation has not be included after {timeout} seconds.")
            print("Operation could be failed or not choosen by bakers. (check fees)")
            return None

        return op_result

    except Exception as e:
        print(traceback.format_exc())
        print(f"Error {e}")


def contractInfoResult(op_result):
    deployReport = {}

    try:
        deployReport["hash"] = op_result["hash"]
        content = op_result['contents'][0]
        metadata = content.get('metadata', {})
        op_result_info = metadata.get('operation_result', {})
        originated_contracts = op_result_info.get('originated_contracts')
        contract_address = None
        if originated_contracts:
            contract_address = originated_contracts[0]

        deployReport["address"] = contract_address

        fee_mutez = int(content.get('fee', 0))
        deployReport["BakerFee"] = fee_mutez

        consumed_milligas = int(op_result_info.get('consumed_milligas', 0))
        deployReport["Gas"] = consumed_milligas

        storage_size_diff = int(op_result_info.get('paid_storage_size_diff', 0))
        storage_burn_cost_mutez = storage_size_diff * 250
        deployReport["Storage"] = storage_burn_cost_mutez

        total_cost_mutez = fee_mutez + storage_burn_cost_mutez
        deployReport["TotalCost"] = total_cost_mutez

        if "confirmed_level" in op_result:
            deployReport["ConfirmedLevel"] = op_result["confirmed_level"]

        return deployReport

    except (KeyError, IndexError, TypeError) as e:
        print(f"Errore: {e}")


def entrypointCall(client, contractAddress, entrypointName, parameters, tezAmount):
    if tezAmount is None:
        tezAmount = Decimal("0")
    elif not isinstance(tezAmount, Decimal):
        tezAmount = Decimal(str(tezAmount))
    contract_interface = client.contract(contractAddress)

    print(f"\n Calling {entrypointName} entrypoint...\n")

    try:
        entrypoint = getattr(contract_interface, entrypointName)
        if parameters == [] or parameters is None:
            op = entrypoint().with_amount(tezAmount).send()
        elif isinstance(parameters, dict):
            op = entrypoint(**parameters).with_amount(tezAmount).send()
        elif isinstance(parameters, (list, tuple)):
            op = entrypoint(*parameters).with_amount(tezAmount).send()
        else:
            op = entrypoint(parameters).with_amount(tezAmount).send()

        forged_op = op.forge()

        op_hash = op.hash()
        print(f"Operation Send! Hash: {op_hash}")

        start_time = time.time()
        timeout = 500
        op_result = None

        while time.time() - start_time < timeout:
            try:
                op_result = client.shell.blocks[-10:].find_operation(op_hash)
                print("   -> Operation Found")
                op_result["confirmed_level"] = getCurrentBlockLevel(client)
                break
            except StopIteration:
                print(f"   -> Not yet completed (time passed: {int(time.time() - start_time)}s)")
                time.sleep(15)

        if not op_result:
            print(f"\n❌ TIMEOUT: The operation has not be included after {timeout} seconds.")
            print("Operation could be failed or not choosen by bakers. (check fees)")
            return None

        op_result["weight"] = len(forged_op) // 2
        return op_result
    except Exception as e:
        print(traceback.format_exc())
        raise RuntimeError(f"Entrypoint call '{entrypointName}' failed: {e}") from e


def entrypointAnalyse(client, contractAddress):
    entrypointSchema = {}

    try:
        contract = client.contract(contractAddress)
        if len(contract.entrypoints) > 1:
            del contract.entrypoints["default"]

        for entrypoint_name, entrypoint_object in contract.entrypoints.items():
            if hasattr(entrypoint_object, 'json_type'):
                parameter_schema = entrypoint_object.json_type()

                if parameter_schema.get('title') == 'unit':
                    entrypointSchema[entrypoint_name] = "unit"
                else:
                    lst = []
                    properties = parameter_schema.get('properties', {})
                    for param_name, param_details in properties.items():
                        param_type = param_details.get('title')
                        param_format = f" (details: {param_details.get('format', 'N/D')})"
                        lst.append((param_name, (param_type, param_format)))
                    entrypointSchema[entrypoint_name] = lst
            else:
                param_type = entrypoint_object.prim
                entrypointSchema[entrypoint_name] = param_type

        return entrypointSchema

    except Exception as e:
        print(f"An error occurred: {e}")


def callInfoResult(opResult):
    callReport = {}

    if opResult is None:
        raise ValueError("The operation result is empty because the entrypoint call failed.")

    try:
        callReport["Hash"] = opResult["hash"]
        content = opResult['contents'][0]
        metadata = content.get('metadata', {})
        op_result_info = metadata.get('operation_result', {})

        fee_mutez = int(content.get('fee', 0))
        callReport["BakerFee"] = fee_mutez

        consumed_milligas = int(op_result_info.get('consumed_milligas', 0))
        callReport["Gas"] = consumed_milligas

        if 'paid_storage_size_diff' in op_result_info:
            storage_size_diff = int(op_result_info.get('paid_storage_size_diff', 0))
            storage_burn_cost_mutez = storage_size_diff * 250
            callReport["Storage"] = storage_burn_cost_mutez
        else:
            storage_burn_cost_mutez = 0

        total_cost_mutez = fee_mutez + storage_burn_cost_mutez
        callReport["TotalCost"] = total_cost_mutez

        callReport["Weight"] = opResult["weight"]

        return callReport

    except (KeyError, IndexError, TypeError) as e:
        print(f"Errore: {e}")
