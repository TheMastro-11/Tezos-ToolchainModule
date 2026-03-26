import json
import re
from pathlib import Path
from folderScan import folderScan


def getAddressListPath():
    return Path(__file__).resolve().parent.parent / "contracts" / "addressList.json"


def getDeploymentLevelPath():
    return Path(__file__).resolve().parent.parent / "contracts" / "deploymentLevels.json"


def normalizeContractName(contractId):
    normalizedName = Path(str(contractId)).stem

    if ":" in normalizedName:
        normalizedName = Path(normalizedName.split(":", 1)[0]).name
    else:
        normalizedName = Path(normalizedName).name

    normalizedName = re.sub(r"Rosetta$", "", normalizedName)
    normalizedName = re.sub(r"Trace$", "", normalizedName)

    return normalizedName


def normalizeTraceTitle(traceTitle):
    normalizedTitle = Path(str(traceTitle)).stem
    normalizedTitle = re.sub(r"Rosetta", "", normalizedTitle)
    normalizedTitle = re.sub(r"Trace", "", normalizedTitle)
    return normalizedTitle.strip("_-")


def extractContractIdFromTraceTitle(traceTitle):
    normalizedTitle = normalizeTraceTitle(traceTitle)
    contractToken = normalizedTitle.split("__", 1)[0]
    return normalizeContractName(contractToken)


def addressUpdate(contract, newAddress):
    addressList = getAddressListPath()
    with open(addressList, 'r', encoding='utf-8') as file:
        addressValid = json.load(file)

    normalizedContract = normalizeContractName(contract)
    addressValid[normalizedContract] = newAddress

    with open(addressList, 'w', encoding='utf-8') as file:
        json.dump(addressValid, file, indent=4)

    return addressValid


def getAddress():
    addressList = getAddressListPath()
    with open(addressList, 'r', encoding='utf-8') as file:
        addressValid = json.load(file)

    return addressValid


def resolveAddress(addressValid, contractId):
    resolutionCandidates = [
        contractId,
        normalizeContractName(contractId)
    ]

    if ':' in contractId:
        folder = contractId.split(':', 1)[0]
        resolutionCandidates.extend([
            folder,
            Path(folder).name,
            normalizeContractName(folder)
        ])

    normalized = normalizeContractName(contractId)
    resolutionCandidates.append(f"{normalized}_{normalized}")

    for candidate in resolutionCandidates:
        if candidate in addressValid:
            return addressValid[candidate]

    raise KeyError(f"Address not found for '{contractId}'")


def jsonWriter(fileName, opReport):
    transactionsValid = {}

    try:
        with open(fileName, 'r', encoding='utf-8') as file:
            data = json.load(file)

        if isinstance(data, dict):
            transactionsValid = data
    except(FileNotFoundError, json.JSONDecodeError):
        pass

    item = {
        "Entrypoint": opReport["entryPoint"],
        "TotalCost": opReport["TotalCost"],
        "Weight": opReport["Weight"],
        "Hash": opReport["Hash"]
    }
    transactionsValid[opReport["contract"]] = item

    with open(fileName, 'w', encoding='utf-8') as file:
        json.dump(transactionsValid, file, indent=4)


def getTraceRoot():
    toolchain_root = Path(__file__).resolve().parent
    candidates = [
        toolchain_root / "rosetta_traces",
        toolchain_root / "execution_traces",
        Path("rosetta_traces"),
        Path("execution_traces")
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    return candidates[0]


def jsonReader(traceRoot=None):
    trace_root = Path(traceRoot) if traceRoot else getTraceRoot()
    executionTracesDict = {}

    try:
        executionTraces = sorted(
            entry
            for entry in trace_root.rglob("*.json")
            if entry.is_file() and not entry.name.startswith('.')
        )

        for tracePath in executionTraces:
            with open(tracePath, 'r', encoding='utf-8') as file:
                traceData = json.load(file)

            traceTitle = traceData.get("trace_title", tracePath.stem)
            executionTracesDict[normalizeTraceTitle(traceTitle)] = traceData

        return executionTracesDict

    except FileNotFoundError:
        print(f"Error: Folder '{trace_root}' not found.")
    except Exception as e:
        print(f"Error: {e}")



def jsonReaderByContract(traceRoot=None):
    trace_root = Path(traceRoot) if traceRoot else getTraceRoot()
    executionTracesByContract = {}
    excluded_contracts = {"traces_guide"}

    try:
        traceFiles = sorted(
            entry
            for entry in trace_root.rglob("*.json")
            if entry.is_file() and not entry.name.startswith('.')
        )

        for tracePath in traceFiles:
            relativePath = tracePath.relative_to(trace_root)
            contractName = relativePath.parts[0] if len(relativePath.parts) > 1 else "Ungrouped"

            if contractName in excluded_contracts:
                continue

            with open(tracePath, 'r', encoding='utf-8') as file:
                traceData = json.load(file)

            traceTitle = traceData.get("trace_title", tracePath.stem)
            normalizedTraceName = normalizeTraceTitle(traceTitle)

            if contractName not in executionTracesByContract:
                executionTracesByContract[contractName] = {}

            executionTracesByContract[contractName][normalizedTraceName] = traceData

        return {
            contractName: dict(sorted(contractTraces.items()))
            for contractName, contractTraces in sorted(executionTracesByContract.items())
        }

    except FileNotFoundError:
        print(f"Error: Folder '{trace_root}' not found.")
    except Exception as e:
        print(f"Error: {e}")


def updateDeploymentLevel(contract, confirmedLevel):
    deploymentLevelPath = getDeploymentLevelPath()
    deploymentLevels = {}

    try:
        with open(deploymentLevelPath, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if isinstance(data, dict):
            deploymentLevels = data
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    normalizedContract = normalizeContractName(contract)
    deploymentLevels[normalizedContract] = int(confirmedLevel)

    deploymentLevelPath.parent.mkdir(parents=True, exist_ok=True)
    with open(deploymentLevelPath, 'w', encoding='utf-8') as file:
        json.dump(deploymentLevels, file, indent=4)

    return deploymentLevels


def getDeploymentLevel(contractId):
    deploymentLevelPath = getDeploymentLevelPath()

    try:
        with open(deploymentLevelPath, 'r', encoding='utf-8') as file:
            deploymentLevels = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    resolutionCandidates = [
        contractId,
        normalizeContractName(contractId)
    ]

    if ':' in contractId:
        folder = contractId.split(':', 1)[0]
        resolutionCandidates.extend([
            folder,
            Path(folder).name,
            normalizeContractName(folder)
        ])

    for candidate in resolutionCandidates:
        if candidate in deploymentLevels:
            return int(deploymentLevels[candidate])

    return None
