import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pytezos import pytezos

from contractUtils import (
    compileContract,
    origination,
    contractInfoResult,
    entrypointAnalyse,
    entrypointCall,
    callInfoResult,
    runScenario,
    getCompiledRoot,
    waitForBlockDelay,
    getCurrentBlockLevel,
    parseCompilationLog,
    multiOrigination
)
from folderScan import folderScan, contractSuites, scenarioScan
from csvUtils import csvReader, csvWriter
from jsonUtils import getAddress, addressUpdate, jsonWriter, jsonReader, resolveAddress, normalizeTraceTitle, extractContractIdFromTraceTitle, updateDeploymentLevel, getDeploymentLevel, normalizeContractName, outputTraceWriter


def getToolchainRoot() -> Path:
    return Path(__file__).resolve().parent


def getContractsRoot() -> Path:
    candidates = [
        (getToolchainRoot() / "../contracts").resolve(),
        getToolchainRoot() / "contracts"
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return candidates[0]


def getScenariosRoot() -> Path:
    return getContractsRoot() / "Rosetta" / "scenarios"


def getTraceRoot() -> Path:
    toolchain_root = getToolchainRoot()
    candidates = [
        toolchain_root / "rosetta_traces",
        toolchain_root / "execution_traces"
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return candidates[0]


def parseContractId(contractId):
    if ":" in contractId:
        folder, fileBase = contractId.split(":", 1)
        return folder, fileBase
    return contractId, contractId

def findCompiledArtifactDir(compiledBaseDir):
    compiledBaseDir = Path(compiledBaseDir)
    directContract = compiledBaseDir / "step_001_cont_0_contract.tz"
    directStorage = compiledBaseDir / "step_001_cont_0_storage.tz"
    if directContract.exists() and directStorage.exists():
        return compiledBaseDir

    for contractPath in sorted(compiledBaseDir.rglob("step_001_cont_0_contract.tz")):
        candidateDir = contractPath.parent
        if (candidateDir / "step_001_cont_0_storage.tz").exists():
            return candidateDir

    return None


def compiledOutputDir(contractFolder, fileBase):
    parts = Path(contractFolder).parts
    if len(parts) >= 2:
        normalized_name = f"{parts[0]}_{parts[1]}_{fileBase}"
    else:
        normalized_name = f"{parts[0]}_{fileBase}"
    return str((getCompiledRoot() / normalized_name).resolve())


def selectContractSuite():
    contractsRoot = getContractsRoot()
    suites = contractSuites(contractsRoot)

    if not suites:
        raise FileNotFoundError("No contract suites found.")

    print("\nContract suites available:\n")
    for index, suite in enumerate(suites, start=1):
        print(index, " " + suite)

    suiteSel = int(input("Which contract suite do you want to use?\n"))
    return suites[suiteSel - 1]


def interactionSetup(client, contractId):
    addressValid = getAddress()
    contractAddress = resolveAddress(addressValid=addressValid, contractId=contractId)
    entrypoints = entrypointAnalyse(client=client, contractAddress=contractAddress)

    print("\nEntrypoints available:")
    entryList = list(entrypoints.keys())
    for index, entrypoint in enumerate(entryList, start=1):
        print(index, " " + entrypoint)

    entrypointSel = int(input("Which entrypoint do you want to use?\n"))
    entrypointName = entryList[entrypointSel - 1]

    parameters = []
    if entrypoints[entrypointName] != "unit":
        parameters = input("Insert parameters value: ")
        if "," in parameters:
            parameters = parameters.split(",")
        else:
            parameters = [parameters]

    tezAmount = parseAmountToTez(input("Insert tez amount: "))

    opResult = entrypointCall(
        client=client,
        contractAddress=contractAddress,
        entrypointName=entrypointName,
        parameters=parameters,
        tezAmount=tezAmount
    )
    infoResult = callInfoResult(opResult=opResult)
    infoResult["contract"] = contractId
    infoResult["entryPoint"] = entrypointName
    return infoResult


def executionSetupCsv(contractId, rows):
    infoResultDict = {}
    for element in rows:
        row = rows[element]
        entrypointSel = row[0]
        walletSel = row[1]
        tezAmount = parseAmountToTez(row[len(row)-1])
        parameters = row[2:len(row)-1] if row[2:len(row)-1] != [] else []

        addressValid = getAddress()
        contractAddress = resolveAddress(addressValid=addressValid, contractId=contractId)
        contractInterface = pytezos.contract(contractAddress)
        entrypoints = contractInterface.entrypoints
        if entrypointSel not in entrypoints:
            raise Exception("Entrypoint not found: " + entrypointSel)

        with open("wallet.json", 'r', encoding='utf-8') as file:
            wallet = json.load(file)
        key = wallet[walletSel]
        client = pytezos.using(shell="ghostnet", key=key)

        opResult = entrypointCall(
            client=client,
            contractAddress=contractAddress,
            entrypointName=entrypointSel,
            parameters=parameters,
            tezAmount=tezAmount
        )
        infoResult = callInfoResult(opResult=opResult)
        infoResult["contract"] = contractId
        infoResult["entryPoint"] = entrypointSel

        infoResultDict[element] = infoResult

    return infoResultDict


def normalizeWalletLabel(value):
    return str(value).strip().lower()


def readWallets():
    with open("wallet.json", 'r', encoding='utf-8') as file:
        return json.load(file)


def extractWalletLabels(traceData):
    labels = []
    seen = set()

    for actor in traceData.get("trace_actors", []):
        actor_label = normalizeWalletLabel(actor)
        if actor_label and actor_label not in seen:
            labels.append(actor_label)
            seen.add(actor_label)

    sorted_steps = sorted(
        traceData.get("trace_execution", []),
        key=lambda step: sequenceSortKey(step.get("sequence_id", ""))
    )

    for step in sorted_steps:
        for actor in step.get("actors", []):
            actor_label = normalizeWalletLabel(actor)
            if actor_label and actor_label not in seen:
                labels.append(actor_label)
                seen.add(actor_label)

        tezos_data = getTezosStepConfig(step)
        provider_wallet = tezos_data.get("provider_wallet")
        if provider_wallet:
            provider_label = normalizeWalletLabel(provider_wallet)
            if provider_label not in seen:
                labels.append(provider_label)
                seen.add(provider_label)

    return labels


def getTezosStepConfig(step):
    platform_specs = step.get("platform_specs", {})
    tezos_data = platform_specs.get("tezos")

    if isinstance(tezos_data, dict):
        return tezos_data

    legacy_tezos_data = step.get("tezos", {})
    if isinstance(legacy_tezos_data, dict):
        return legacy_tezos_data

    return {}


def sequenceSortKey(sequenceId):
    text = str(sequenceId).strip()

    try:
        return (0, int(text))
    except ValueError:
        return (1, text)

def buildWalletMap(traceData, availableWallets):
    normalized_wallets = {
        normalizeWalletLabel(wallet_id): wallet_id
        for wallet_id in availableWallets.keys()
    }
    wallet_labels = extractWalletLabels(traceData)
    wallet_map = {}

    ordered_wallet_ids = list(availableWallets.keys())
    next_wallet_index = 0

    for label in wallet_labels:
        if label in normalized_wallets:
            wallet_map[label] = normalized_wallets[label]
            continue

        if next_wallet_index >= len(ordered_wallet_ids):
            raise ValueError("Not enough wallets configured in wallet.json for the execution trace.")

        wallet_map[label] = ordered_wallet_ids[next_wallet_index]
        next_wallet_index += 1

    return wallet_map


def parseAmountToTez(amountValue):
    if amountValue is None or amountValue == "":
        return Decimal("0")

    if isinstance(amountValue, Decimal):
        return amountValue

    if isinstance(amountValue, int):
        return Decimal(amountValue)

    if isinstance(amountValue, float):
        return Decimal(str(amountValue))

    text = str(amountValue).strip()

    try:
        if text.startswith("mutez(") and text.endswith(")"):
            mutez_value = Decimal(text[6:-1].strip())
            return mutez_value / Decimal("1000000")

        if text.startswith("tez(") and text.endswith(")"):
            return Decimal(text[4:-1].strip())

        return Decimal(text)
    except InvalidOperation as e:
        raise ValueError(f"Invalid tez amount: {amountValue}") from e


def getContractSourcePath(contractId):
    contractsRoot = getContractsRoot()
    normalizedName = contractId.removesuffix("Rosetta")
    matches = list((contractsRoot / "Rosetta").glob(f"**/{normalizedName}Rosetta.py"))
    if not matches:
        raise FileNotFoundError(f"Unable to resolve the source file for contract '{contractId}'.")
    return matches[0]


def getEntrypointParameterNames(contractId, entrypointName):
    import ast

    sourcePath = getContractSourcePath(contractId)
    module = ast.parse(sourcePath.read_text(encoding="utf-8"))

    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == entrypointName:
            decorators = []
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Attribute):
                    decorators.append(decorator.attr)
                elif isinstance(decorator, ast.Name):
                    decorators.append(decorator.id)

            if "entrypoint" in decorators:
                return [arg.arg for arg in node.args.args if arg.arg != "self"]

    raise ValueError(f"Unable to resolve entrypoint '{entrypointName}' in '{sourcePath}'.")


def getEntrypointParameterTypes(contractId, entrypointName):
    """Return a dict {param_name: annotation_string} for the given entrypoint.
    Only parameters with explicit type annotations are included."""
    import ast

    def annotation_to_str(node):
        if isinstance(node, ast.Attribute):
            return f"{annotation_to_str(node.value)}.{node.attr}"
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Subscript):
            return annotation_to_str(node.value)
        return ""

    sourcePath = getContractSourcePath(contractId)
    module = ast.parse(sourcePath.read_text(encoding="utf-8"))

    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == entrypointName:
            decorators = []
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Attribute):
                    decorators.append(decorator.attr)
                elif isinstance(decorator, ast.Name):
                    decorators.append(decorator.id)

            if "entrypoint" in decorators:
                result = {}
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue
                    if arg.annotation is not None:
                        result[arg.arg] = annotation_to_str(arg.annotation)
                return result

    return {}


# SmartPy address types that must be passed as pytezos Key/Address objects
_SP_ADDRESS_TYPES = {"sp.address", "sp.TAddress"}


def coerceParameterForTezos(value, param_type_str):
    """Convert a resolved parameter value to the format PyTezos expects.
    Specifically, sp.address-annotated parameters must be passed as pytezos
    Address objects, not plain strings, to ensure correct Michelson encoding."""
    if param_type_str in _SP_ADDRESS_TYPES and isinstance(value, str):
        from pytezos.crypto.encoding import is_address
        if is_address(value):
            return value  # PyTezos contract interface accepts plain tz1/KT1 strings
    return value


def resolveAddressOf(value):
    """Recursively resolve {"address_of": "<label>"} objects to the corresponding
    Tezos address read from pubKeyAddr.json.  Any other value is returned as-is."""
    if isinstance(value, dict) and list(value.keys()) == ["address_of"]:
        label = value["address_of"].strip().lower()
        pub_key_path = getToolchainRoot() / "pubKeyAddr.json"
        try:
            with open(pub_key_path, "r", encoding="utf-8") as f:
                pub_keys = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"pubKeyAddr.json not found at '{pub_key_path}'. "
                "Create it with a mapping of label → Tezos address."
            )
        normalized = {k.strip().lower(): v for k, v in pub_keys.items()}
        if label not in normalized:
            raise KeyError(
                f"'address_of' label '{label}' not found in pubKeyAddr.json. "
                f"Available labels: {list(normalized.keys())}"
            )
        return normalized[label]
    if isinstance(value, dict):
        return {k: resolveAddressOf(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolveAddressOf(v) for v in value]
    return value


def buildStepParameters(contractId, entrypointName, stepArgs):
    filteredArgs = {
        key: value
        for key, value in stepArgs.items()
        if not key.startswith("_")
    }

    # Resolve any {"address_of": "<label>"} objects to real Tezos addresses.
    filteredArgs = {k: resolveAddressOf(v) for k, v in filteredArgs.items()}

    if not filteredArgs:
        return []

    parameterNames = getEntrypointParameterNames(contractId, entrypointName)
    parameterTypes = getEntrypointParameterTypes(contractId, entrypointName)

    if len(parameterNames) == 1:
        parameterName = parameterNames[0]
        if parameterName not in filteredArgs:
            raise KeyError(
                f"Parameter '{parameterName}' not found in trace args for '{contractId}.{entrypointName}'."
            )
        value = filteredArgs[parameterName]
        return coerceParameterForTezos(value, parameterTypes.get(parameterName, ""))

    return {
        parameterName: coerceParameterForTezos(
            filteredArgs[parameterName],
            parameterTypes.get(parameterName, "")
        )
        for parameterName in parameterNames
        if parameterName in filteredArgs
    }


def resolveStepWallet(step, walletMap):
    tezos_data = getTezosStepConfig(step)
    provider_wallet = tezos_data.get("provider_wallet")
    if provider_wallet:
        provider_label = normalizeWalletLabel(provider_wallet)
        if provider_label in walletMap:
            return walletMap[provider_label]

    for actor in step.get("actors", []):
        actor_label = normalizeWalletLabel(actor)
        if actor_label in walletMap:
            return walletMap[actor_label]

    trace_actors = walletMap.keys()
    for actor_label in trace_actors:
        return walletMap[actor_label]

    raise ValueError("No wallet could be resolved for the trace step.")

def normalizeJsonTrace(traceData):
    availableWallets = readWallets()
    walletMap = buildWalletMap(traceData, availableWallets)
    normalizedRows = {}
    traceContractId = extractContractIdFromTraceTitle(traceData.get("trace_title", ""))

    if not traceContractId:
        raise ValueError("Unable to resolve the contract name from 'trace_title'.")

    sorted_steps = sorted(
        traceData.get("trace_execution", []),
        key=lambda step: sequenceSortKey(step.get("sequence_id", ""))
    )

    for step in sorted_steps:
        args = step.get("args", {})
        tezos_data = getTezosStepConfig(step)

        provider_wallet = tezos_data.get("provider_wallet")
        if provider_wallet:
            actor_label = normalizeWalletLabel(provider_wallet)
        else:
            actors = step.get("actors", [])
            actor_label = normalizeWalletLabel(actors[0]) if actors else "unknown"

        normalizedRows[step["sequence_id"]] = {
            "entrypoint": step["function_name"],
            "wallet": resolveStepWallet(step, walletMap),
            "actor": actor_label,
            "contractId": traceContractId,
            "parameters": buildStepParameters(traceContractId, step["function_name"], args),
            "tezAmount": parseAmountToTez(step.get("value", tezos_data.get("value", tezos_data.get("_amount", args.get("_amount"))))),
            "waitingTime": int(step.get("waiting_time", 0) or 0),
            "valid": bool(step.get("valid", True))
        }

    return normalizedRows

def executionSetupJson(contractId, traceData):
    normalizedRows = normalizeJsonTrace(traceData)
    infoResultDict = {}
    lastConfirmedBlockLevel = getDeploymentLevel(contractId)

    for element, row in normalizedRows.items():
        currentContractId = row["contractId"]
        entrypointSel = row["entrypoint"]
        walletSel = row["wallet"]
        parameters = row["parameters"]
        tezAmount = row["tezAmount"]
        waitingTime = row["waitingTime"]

        addressValid = getAddress()
        contractAddress = resolveAddress(addressValid=addressValid, contractId=currentContractId)
        contractInterface = pytezos.contract(contractAddress)
        entrypoints = contractInterface.entrypoints
        if entrypointSel not in entrypoints:
            raise Exception("Entrypoint not found: " + entrypointSel)

        with open("wallet.json", 'r', encoding='utf-8') as file:
            wallet = json.load(file)
        key = wallet[walletSel]
        client = pytezos.using(shell="ghostnet", key=key)

        if lastConfirmedBlockLevel is None:
            lastConfirmedBlockLevel = getCurrentBlockLevel(client)

        if waitingTime > 0:
            lastConfirmedBlockLevel = waitForBlockDelay(
                client=client,
                startBlockLevel=lastConfirmedBlockLevel,
                waitingTime=waitingTime
            )

        send_level = lastConfirmedBlockLevel

        opResult = entrypointCall(
            client=client,
            contractAddress=contractAddress,
            entrypointName=entrypointSel,
            parameters=parameters,
            tezAmount=tezAmount
        )
        infoResult = callInfoResult(opResult=opResult)
        infoResult["contract"] = currentContractId
        infoResult["entryPoint"] = entrypointSel
        infoResult["actor"] = row["actor"]

        if "confirmed_level" in opResult:
            lastConfirmedBlockLevel = opResult["confirmed_level"]
        else:
            lastConfirmedBlockLevel = getCurrentBlockLevel(client)

        infoResult["block_delay"] = lastConfirmedBlockLevel - send_level

        infoResultDict[element] = infoResult

    return infoResultDict


def scenarioSetup():
    scenariosRoot = getScenariosRoot()
    if not scenariosRoot.exists():
        raise FileNotFoundError(f"Scenario folder not found: {scenariosRoot}")

    scenarios = scenarioScan(scenariosRoot)
    if not scenarios:
        raise FileNotFoundError("No scenario files found.")

    print("\nScenarios available:\n")
    for index, scenario in enumerate(scenarios, start=1):
        print(index, " " + scenario)

    scenarioSel = int(input("Which scenario do you want to test?\n"))
    scenarioPath = scenariosRoot / f"{scenarios[scenarioSel-1]}.py"
    return runScenario(str(scenarioPath))


def normalizeContractToken(value):
    return normalizeContractName(value).replace("/", "_").replace(":", "_").lower()


def getCompiledContracts():
    compiled_root = getCompiledRoot()
    compiled_contracts = {}

    if not compiled_root.exists():
        return compiled_contracts

    for entry in sorted(compiled_root.iterdir()):
        if not entry.is_dir():
            continue

        artifact_dir = findCompiledArtifactDir(entry)
        if artifact_dir is None:
            continue

        contract_path = artifact_dir / "step_001_cont_0_contract.tz"
        storage_path = artifact_dir / "step_001_cont_0_storage.tz"
        metadata_path = entry / "metadata.json"

        metadata = {}
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except Exception:
                metadata = {}

        display_name = metadata.get("contract_id") or metadata.get("contract_name") or entry.name
        artifacts = parseCompilationLog(artifact_dir)
        compiled_contracts[display_name] = {
            "dir": artifact_dir,
            "contract_path": contract_path,
            "storage_path": storage_path,
            "metadata": metadata,
            "artifacts": artifacts,
        }

    return compiled_contracts


def resolveCompiledContractInfo(contractId):
    compiled_contracts = getCompiledContracts()

    if contractId in compiled_contracts:
        return compiled_contracts[contractId]

    expected_token = normalizeContractToken(contractId)

    for display_name, compiled_info in compiled_contracts.items():
        metadata = compiled_info.get("metadata", {})
        metadata_values = [
            display_name,
            metadata.get("contract_id", ""),
            metadata.get("contract_name", ""),
            Path(metadata.get("source", "")).stem,
        ]

        if any(normalizeContractToken(value) == expected_token for value in metadata_values if value):
            return compiled_info

    raise FileNotFoundError(f"No compiled artifacts found for '{contractId}'.")


def resolveTraceContractCandidates(selectedContract, traceData):
    trace_title_contract_id = extractContractIdFromTraceTitle(traceData.get("trace_title", ""))

    candidate_ids = []
    if trace_title_contract_id:
        candidate_ids.append(trace_title_contract_id)

    if selectedContract and selectedContract != "Ungrouped":
        candidate_ids.append(selectedContract)

    normalized_candidates = [normalizeContractToken(c) for c in candidate_ids if c]
    contractsRoot = getContractsRoot()

    if not contractsRoot.exists():
        raise FileNotFoundError(f"Contracts folder not found: {contractsRoot}")

    available_contracts = folderScan(contractsRoot)
    resolved_candidates = {}

    for contract_id in available_contracts:
        folder, implementation = parseContractId(contract_id)
        suite = folder.split("/", 1)[0]
        searchable_tokens = {
            normalizeContractToken(contract_id),
            normalizeContractToken(folder),
            normalizeContractToken(folder.split("/")[-1]),
            normalizeContractToken(implementation),
        }

        if any(candidate in searchable_tokens for candidate in normalized_candidates):
            resolved_candidates[suite] = contract_id

    if resolved_candidates:
        return resolved_candidates

    raise FileNotFoundError(
        "Unable to match the selected trace to a contract source file. "
        f"Available contracts: {', '.join(available_contracts)}"
    )


def resolveTraceContractId(selectedContract, traceData, preferredSuite=None):
    resolved_candidates = resolveTraceContractCandidates(
        selectedContract=selectedContract, traceData=traceData
    )

    if preferredSuite and preferredSuite in resolved_candidates:
        return resolved_candidates[preferredSuite]

    if "Rosetta" in resolved_candidates:
        return resolved_candidates["Rosetta"]

    return next(iter(resolved_candidates.values()))


def deployContract(client, contractId, initialBalance):
    compiled_info = resolveCompiledContractInfo(contractId)
    artifacts = compiled_info.get("artifacts", [])
    artifact_dir = compiled_info["dir"]

    if len(artifacts) > 1:
        print(f"\n>>> Multi-contract detected ({len(artifacts)} artifacts):")
        for art in artifacts:
            print(f"    - {art['contract_name']} ({art['step_prefix']})")

        return multiOrigination(
            client=client,
            artifactDir=str(artifact_dir),
            contractId=contractId,
            initialBalance=initialBalance,
            normalizeContractNameFn=normalizeContractName,
            addressUpdateFn=addressUpdate,
            updateDeploymentLevelFn=updateDeploymentLevel
        )
    else:
        michelson_code = compiled_info["contract_path"].read_text(encoding="utf-8")
        storage_code = compiled_info["storage_path"].read_text(encoding="utf-8")

        op_result = origination(client, michelson_code, storage_code, initialBalance)
        if not op_result:
            raise RuntimeError(f"Origination failed for '{contractId}'.")

        contractInfo = contractInfoResult(op_result)
        addressUpdate(contract=contractId, newAddress=contractInfo["address"])
        if "ConfirmedLevel" in contractInfo:
            updateDeploymentLevel(contract=contractId, confirmedLevel=contractInfo["ConfirmedLevel"])

        return [{"artifact": None, "info": contractInfo, "addressName": contractId}]


def compileAndDeployForTrace(client, selectedContract, traceData, shouldCompile, initialBalance, preferredSuite=None):
    contractId = resolveTraceContractId(selectedContract, traceData, preferredSuite)

    if shouldCompile:
        folder, implementation = parseContractId(contractId)
        contractPath = getContractsRoot() / folder / f"{implementation}.py"
        if not contractPath.exists():
            raise FileNotFoundError(f"Contract source not found: {contractPath}")
        compileContract(str(contractPath))

    results = deployContract(client, contractId, initialBalance)
    main_result = results[-1]
    return contractId, main_result["info"]


def exportResult(opResult):
    fileName = "transactionsOutput"
    csvWriter(fileName=fileName + ".csv", op_result=opResult)
    print("\nCSV Updated!\n\n")
    jsonWriter(fileName=fileName + ".json", opReport=opResult)
    print("\nJSON Updated!\n\n")


def exportTraceResult(traceData, resultsDict, traceName):
    outputPath = outputTraceWriter(traceData=traceData, resultsDict=resultsDict, traceName=traceName)
    print(f"\nTrace output saved: {outputPath}\n")


def main():
    print("Hi, welcome to the Tezos-Contract toolchain!\n")
    print("Here you can compile, deploy, interact with, or test any contract from the archive.\n")

    contractsRoot = getContractsRoot()
    operationSel = int(input(
        "Now, select an option: \n"
        "1 Compile\n"
        "2 Deploy\n"
        "3 Interact\n"
        "4 Use Execution Trace\n"
        "5 Test Scenario\n"
    ))

    if operationSel not in {4, 5}:
        walletSel = input("Which account do you want to use?\n")
        with open("wallet.json", 'r', encoding='utf-8') as file:
            wallet = json.load(file)

        key = wallet[walletSel]
        client = pytezos.using(shell="ghostnet", key=key)

        selectedSuite = None
        if operationSel == 1:
            selectedSuite = selectContractSuite()

        allContracts = folderScan(contractsRoot, suite=selectedSuite)
        print("\nContracts available (Folder:Implementation): \n")
        for index, contractId in enumerate(allContracts, start=1):
            print(index, " " + contractId)

        contractSel = int(input("Which contract do you want to use?\n"))
        contractId = allContracts[contractSel-1]
        contractFolder, fileBase = parseContractId(contractId)

    match operationSel:
        case 1:
            contractPath = contractsRoot / contractFolder / f"{fileBase}.py"
            try:
                compileContract(contractPath=str(contractPath))
            except Exception as e:
                print(f"\nERROR: {e}\n")
            main()

        case 2:
            initialBalance = int(input("Insert an initial balance: "))
            try:
                results = deployContract(client=client, contractId=contractId, initialBalance=initialBalance)
                for r in results:
                    print(f"  -> {r['addressName']}: {r['info']['address']}")
            except FileNotFoundError:
                print("\n\033[1m Contract must be compiled before \033[0m\n\n")
            except Exception as e:
                print(f"\nERROR during deploy: {e}\n")

            main()

        case 3:
            op_report = interactionSetup(client=client, contractId=contractId)
            sel = input("Do you want to export the result?(y/n):  ")
            if sel == "y":
                exportResult(opResult=op_report)
            main()

        case 4:
            formatSel = input("CSV(1) or JSON(2)?")
            if str(formatSel) == "1":
                contractExecutionTraces = csvReader()
                for contract in contractExecutionTraces:
                    results = executionSetupCsv(contractId=contract, rows=contractExecutionTraces[contract])
                    for result in results:
                        exportResult(results[result])
            else:
                traceExecutionTraces = jsonReader(traceRoot=getTraceRoot())
                for traceName, traceData in traceExecutionTraces.items():
                    results = executionSetupJson(contractId=traceName, traceData=traceData)
                    exportTraceResult(traceData=traceData, resultsDict=results, traceName=traceName)

            main()

        case 5:
            try:
                result = scenarioSetup()
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            except Exception as e:
                print(f"\nERROR: {e}\n")
            main()


if __name__ == "__main__":
    main()