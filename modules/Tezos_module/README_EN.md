# Tezos Module

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![SmartPy](https://img.shields.io/badge/SmartPy-latest-teal)
![PyTezos](https://img.shields.io/badge/PyTezos-latest-purple)
![Network](https://img.shields.io/badge/Network-Ghostnet-lightblue)

A complete module for **managing the full lifecycle of Tezos smart contracts**: SmartPy → Michelson compilation, deployment on Ghostnet, entrypoint interaction, automated trace execution, and transaction cost analysis.

---

## Table of Contents

- [Module Structure](#module-structure)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Available Contracts](#available-contracts)
- [Toolchain Architecture](#toolchain-architecture)
- [Core Components](#core-components)
- [Operational Workflows](#operational-workflows)
- [Trace Format](#trace-format)
- [Output and Reports](#output-and-reports)
- [Tezos Fee Model](#tezos-fee-model)
- [Flask Backend Integration](#flask-backend-integration)

---

## Module Structure

```
Tezos_module/
├── contracts/
│   ├── addressList.json             # KT1... addresses of deployed contracts
│   ├── deploymentLevels.json        # Block levels of deployments
│   ├── Library/
│   │   └── fa2Lib.py                # FA2 standard library (tokens)
│   ├── Legacy/                      # Original implementations (old syntax)
│   │   ├── Auction/
│   │   ├── CrowdFunding/
│   │   ├── Escrow/
│   │   ├── HTLC/
│   │   ├── SimpleTransfer/
│   │   ├── Storage/
│   │   ├── Vault/
│   │   ├── Vesting/
│   │   └── ... (9 more contracts)
│   └── Rosetta/                     # Standardized implementations (current syntax)
│       ├── AnonymousData/
│       ├── Auction/
│       ├── Bet/
│       ├── ConstantProductAmm/
│       ├── Crowdfund/
│       ├── Escrow/
│       ├── Factory/
│       ├── HTLC/
│       ├── Lottery/
│       ├── PaymentSplitter/
│       ├── PriceBet/
│       ├── SimpleTransfer/
│       ├── SimpleWallet/
│       ├── Storage/
│       ├── TicketGenerator/
│       ├── UpgradableProxy/
│       ├── Vault/
│       ├── Vesting/
│       └── scenarios/               # SmartPy test scenarios for each contract
│
└── toolchain/
    ├── main.py                      # CLI orchestrator (847 lines)
    ├── contractUtils.py             # Blockchain operations via PyTezos (442 lines)
    ├── trace_utils.py               # Streamlit utilities and trace logic (520 lines)
    ├── jsonUtils.py                 # JSON persistence for addresses and traces (308 lines)
    ├── folderScan.py                # Contract directory scanner (72 lines)
    ├── dapp.py                      # Streamlit web interface (387 lines)
    ├── wallet.json                  # Wallet private keys (edsk...)
    ├── pubKeyAddr.json              # Label → tz1... address mapping
    ├── compiled/                    # Compiled Michelson artifacts
    │   └── <Suite>_<Contract>_<Impl>/
    │       ├── step_001_cont_0_contract.tz
    │       ├── step_001_cont_0_storage.tz
    │       ├── step_001_cont_0_contract.json
    │       ├── step_001_cont_0_storage.json
    │       ├── step_001_cont_0_types.py
    │       └── log.txt
    ├── output_traces/               # JSON reports from executed traces
    │   ├── Auction.json
    │   ├── SimpleWallet.json
    │   └── template.json
    └── transactionsOutput.json      # JSON summary of latest transactions
```

---

## Prerequisites

### Python Dependencies

Installed via `requirements.txt` in the project root:

```
pytezos
smartpy-tezos
```

### Native Dependency: libsodium

PyTezos requires the native `libsodium` library:

```bash
# macOS
brew install libsodium

# Ubuntu / WSL
sudo apt-get install libsodium-dev
```

### SmartPy CLI

Required for compilation. Official installation:

```bash
pip install smartpy-tezos
```

Verify:

```bash
python -c "import smartpy; print(smartpy.__version__)"
```

---

## Configuration

### wallet.json

Contains the private keys for the wallets used by the toolchain. Must be placed at `toolchain/wallet.json`:

```json
{
    "admin":   "edsk...",
    "oracle":  "edsk...",
    "player1": "edsk...",
    "player2": "edsk...",
    "player3": "edsk..."
}
```

> `edsk...` keys are Tezos private keys in base58 format. Use Ghostnet accounts with no real funds.

### pubKeyAddr.json

Optional mapping from label to public address `tz1...`. Used by `resolveAddressOf` to replace labels like `{"address_of": "player1"}` with the actual address in trace parameters:

```json
{
    "admin":   "tz1SL2xBdmLSD2W3Hs84SfH912xDpYtAjsaa",
    "oracle":  "tz1ZNfCeehri4t8oFNB187DDEAqtdu3Ayc1z",
    "player1": "tz1SL2xBdmLSD2W3Hs84SfH912xDpYtAjsaa",
    "player2": "tz1aLPm3WynyHRXFvjjdHZDKEjHZVvQMGxqU",
    "player3": "tz1ZNfCeehri4t8oFNB187DDEAqtdu3Ayc1z"
}
```

### Network

The module operates on **Ghostnet** (Tezos public testnet). The connection is managed by PyTezos:

```python
client = pytezos.using(shell="ghostnet", key=private_key)
```

---

## Available Contracts

### Rosetta Suite (current implementations)

| Contract | Description | Main Entrypoints |
|---|---|---|
| **Auction** | On-chain English auction | `start`, `bid`, `withdraw`, `end` |
| **Bet** | Two-party betting contract | `create`, `join`, `resolve` |
| **Crowdfund** | Goal-based crowdfunding | `contribute`, `withdraw`, `claim` |
| **Escrow** | Controlled escrow service | `deposit`, `release`, `refund` |
| **Factory** | Contract factory pattern | `create`, `get` |
| **HTLC** | Hash Time Locked Contract (atomic swap) | `lock`, `redeem`, `refund` |
| **Lottery** | Lottery with drawing mechanism | `buy`, `draw`, `claim` |
| **PaymentSplitter** | Revenue sharing among beneficiaries | `addPayee`, `release` |
| **PriceBet** | Oracle-based price prediction bet | `bet`, `resolve` |
| **SimpleTransfer** | Basic XTZ transfer | `transfer` |
| **SimpleWallet** | Multi-sig wallet | `deposit`, `withdraw`, `approve` |
| **Storage** | Generic data storage | `store`, `retrieve` |
| **UpgradableProxy** | Upgradeable proxy pattern | `upgrade`, `call` |
| **Vault** | Token vault / staking | `deposit`, `withdraw` |
| **Vesting** | Token vesting schedule | `release`, `revoke` |
| **AnonymousData** | Privacy-preserving data storage | `submit`, `retrieve` |
| **ConstantProductAmm** | Constant-product AMM | `addLiquidity`, `swap`, `removeLiquidity` |
| **TicketGenerator** | Tezos ticket minter | `mint`, `transfer`, `burn` |

### Legacy Suite

Earlier versions of the same contracts, written with the pre-unified SmartPy syntax. Kept for compatibility and comparison purposes.

### Test Scenarios

Each Rosetta contract has a `scenarios/` folder with runnable SmartPy scenarios to verify its logic locally:

```
contracts/Rosetta/Auction/scenarios/
└── AuctionScenario.py   # Full SmartPy test scenario
```

---

## Toolchain Architecture

```
                ┌─────────────────────┐
                │    User Interfaces  │
                ├──────────┬──────────┤
                │  dapp.py │ main.py  │
                │(Streamlit)│  (CLI)   │
                └────┬─────┴────┬─────┘
                     │          │
          ┌──────────▼──────────▼──────────┐
          │          main.py               │
          │     (operations orchestrator)  │
          └──┬───────────┬────────────┬───┘
             │           │            │
   ┌─────────▼──┐  ┌─────▼──────┐  ┌─▼──────────┐
   │contractUtils│  │ jsonUtils  │  │ trace_utils │
   │(blockchain) │  │(data       │  │(UI helpers) │
   └─────────┬──┘  │persistence)│  └─────────────┘
             │     └─────┬──────┘
   ┌─────────▼──┐        │
   │  PyTezos   │  ┌─────▼──────┐
   │  (RPC)     │  │folderScan  │
   └─────────┬──┘  └────────────┘
   ┌─────────▼──────────────────┐
   │       Tezos Ghostnet       │
   │    (public RPC node)       │
   └────────────────────────────┘
```

### Separation of Concerns

| Module | Responsibility |
|---|---|
| `main.py` | Orchestration, CLI menus, parameter parsing, address resolution, trace execution |
| `contractUtils.py` | All blockchain operations (compile, originate, call, inspect) |
| `jsonUtils.py` | Read/write `addressList.json`, `deploymentLevels.json`, JSON traces, output reports |
| `trace_utils.py` | Streamlit UI components, output capture, report rendering, session state |
| `folderScan.py` | Contract and scenario directory scanning |
| `dapp.py` | Streamlit view routing, complete web interface |

---

## Core Components

### `contractUtils.py` — Blockchain Operations

#### Compilation

```python
compileContract(contractPath: str) -> subprocess.CompletedProcess
```

Runs the SmartPy contract `.py` file as a subprocess. SmartPy automatically generates the Michelson files in the output directory:
- `step_001_cont_0_contract.tz` — Michelson contract code
- `step_001_cont_0_storage.tz` — initial storage
- `log.txt` — metadata and placeholders

---

#### Deployment (Origination)

```python
origination(
    client: PyTezos,
    michelsonCode: str,
    initialStorage: str,
    initialBalance: int
) -> dict | None
```

Originates the contract on the blockchain. Converts Michelson to Micheline format, forges and signs the operation, waits for confirmation (timeout: 500s, polling every 15s).

For multi-contract artifacts:

```python
multiOrigination(
    client, artifactDir, contractId, initialBalance,
    normalizeContractNameFn, addressUpdateFn, updateDeploymentLevelFn
) -> list[dict]
```

---

#### Entrypoint Call

```python
entrypointCall(
    client: PyTezos,
    contractAddress: str,        # KT1...
    entrypointName: str,
    parameters: list | dict,
    tezAmount: Decimal           # in tez (not mutez)
) -> dict | None
```

---

#### Entrypoint Inspection

```python
entrypointAnalyse(client: PyTezos, contractAddress: str) -> dict
```

Returns the entrypoint schema of a deployed contract, useful for interactive mode.

---

#### Operation Result — Data Structures

**Deploy report** (from `contractInfoResult`):

```python
{
    "hash":           str,   # operation hash
    "address":        str,   # KT1... address of the deployed contract
    "BakerFee":       int,   # baker fee in mutez
    "Gas":            int,   # consumed gas in milligas
    "Storage":        int,   # storage cost in mutez (size × 250)
    "TotalCost":      int,   # BakerFee + Storage
    "ConfirmedLevel": int    # block level of confirmation
}
```

**Call report** (from `callInfoResult`):

```python
{
    "Hash":       str,   # operation hash
    "BakerFee":   int,   # baker fee in mutez
    "Gas":        int,   # consumed gas in milligas
    "Storage":    int,   # storage increase cost in mutez
    "TotalCost":  int,   # BakerFee + Storage
    "Weight":     int    # operation weight in bytes
}
```

---

### `main.py` — Orchestrator

#### Key Resolution Functions

```python
# AST analysis of SmartPy source to extract parameters
getEntrypointParameterNames(contractId, entrypointName) -> list[str]
getEntrypointParameterTypes(contractId, entrypointName) -> dict[str, str]

# Address resolution from label ({"address_of": "player1"} → "tz1...")
resolveAddressOf(value) -> any

# Parameter coercion to PyTezos-compatible format
coerceParameterForTezos(value, param_type_str) -> any

# Amount parsing (supports "0.5")
parseAmountToTez(amountValue) -> Decimal
```

#### Wallet Label Normalization

All labels are normalized to lowercase and stripped:

```
"Player1" → "player1"
"ADMIN"   → "admin"
" Oracle" → "oracle"
```

#### Contract Address Resolution Chain

When looking up a contract address in `addressList.json`, the system tries in order:
1. Exact contract ID
2. Normalized contract name
3. Folder name (if it contains ":")
4. Folder basename
5. Normalized folder name
6. Double-normalized format (e.g. `"SimpleTransfer_SimpleTransfer"`)

---

### `jsonUtils.py` — Data Persistence

#### Address Management

```python
addressUpdate(contract: str, newAddress: str) -> dict
# Updates addressList.json with the new KT1... address

getAddress() -> dict
# Reads and returns the full addressList.json

resolveAddress(addressValid: dict, contractId: str) -> str
# Looks up address with multiple fallbacks
```

#### Trace Management

```python
jsonReader(traceRoot: Path) -> dict
# Reads all .json trace files from a directory
# Returns: {trace_name: trace_data}

jsonReaderByContract(traceRoot: Path) -> dict
# Reads traces organized by contract folder
# Returns: {contract: {trace_name: trace_data}}
```

#### Deployment Levels

```python
updateDeploymentLevel(contract: str, confirmedLevel: int) -> dict
# Updates deploymentLevels.json with the block level

getDeploymentLevel(contractId: str) -> int | None
# Retrieves deployment level (used for block delay calculation)
```

---

### `trace_utils.py` — Streamlit Utilities

#### Terminal Output Capture

```python
class StreamlitTerminalWriter(io.TextIOBase):
    # Text stream for capturing stdout/stderr inside Streamlit
    def write(self, text: str) -> int
    def getvalue(self) -> str

run_with_terminal_output(action, session_key, render_live, output_placeholder)
# Executes action() capturing all output inside Streamlit
```

#### Session State Management

```python
get_trace_report_state() -> dict | None
save_trace_report(report_data: dict) -> None
save_trace_setup_config(config_data: dict) -> None
get_last_trace_setup() -> dict | None
```

#### Report Rendering

```python
render_trace_report() -> None
# Renders the full trace report with metrics, phases, and details

render_live_trace_progress(title, total_traces, show_terminal_output)
# Creates UI elements for real-time progress tracking

render_execution_phase_payload(payload: dict) -> None
# Displays detailed execution statistics
```

#### Trace Execution with Report

```python
run_trace_with_report(
    trace_name, trace_data, contract_name,
    should_compile, initial_balance, preferred_suite,
    render_live, output_placeholder
) -> dict
```

Runs the full pipeline (compilation → deployment → execution) and returns a structured report with three phases:

```python
{
    "compile":  {"status": "success"|"error"|"skipped", "output": str, "payload": dict},
    "deploy":   {"status": "success"|"error"|"skipped", "output": str, "payload": dict},
    "execute":  {"status": "success"|"error",           "output": str, "payload": dict}
}
```

---

## Operational Workflows

### Workflow A — Compilation

```
1. Select suite (Legacy / Rosetta)
2. Select contract from directory
3. compileContract(contractPath)
   └── Subprocess: python <contract>.py
       └── SmartPy generates:
           ├── step_001_cont_0_contract.tz   (Michelson code)
           ├── step_001_cont_0_storage.tz    (initial storage)
           ├── step_001_cont_0_contract.json
           └── log.txt
4. Save to compiled/<Suite>_<Contract>_<Impl>/
```

---

### Workflow B — Deployment (Origination)

```
1. Select compiled contract
2. Set initial balance (in tez)
3. Read Michelson files from compiled/
4. Convert Michelson → Micheline (PyTezos)
5. client.origination(script={code, storage}, balance=initialBalance)
6. Wait for confirmation (timeout 500s, polling every 15s)
7. Extract KT1... address from operation result
8. Update addressList.json
9. Update deploymentLevels.json (block level)
```

---

### Workflow C — Interactive Interaction

```
1. Select contract from addressList.json
2. entrypointAnalyse(client, KT1...) → entrypoint schema
3. Select entrypoint
4. Input parameters (with automatic type-coercion)
5. Input tez amount
6. entrypointCall(client, KT1..., entrypoint, params, amount)
7. Wait for confirmation
8. callInfoResult(opResult) → {BakerFee, Gas, Storage, Weight, Hash}
9. Optional export to JSON
```

---

### Workflow D — Automated JSON Trace Execution

```
1. Read traces from rosetta_traces/ or execution_traces/
2. normalizeJsonTrace(traceData):
   ├── Extract wallet labels (trace_actors + provider_wallet)
   ├── Build wallet map (label → wallet_id)
   └── For each step:
       ├── resolveStepWallet() → wallet to use
       ├── buildStepParameters() → params with address resolution
       └── parseAmountToTez() → amount in tez
3. executionSetupJson():
   ├── getAddress() → contract address from addressList.json
   └── For each step in order:
       ├── waitForBlockDelay() if waiting_time > 0
       ├── entrypointCall(client, KT1..., ...)
       └── callInfoResult() → step costs
4. exportTraceResult():
   ├── Aggregate costs per actor
   ├── Compute total statistics
   └── Write output_traces/<TraceName>.json
```

---

### Workflow E — SmartPy Scenario Testing

```
1. scenarioScan() → list available scenarios
2. Select scenario
3. runScenario(scenarioPath) → subprocess python scenario.py
4. HTML / log output from SmartPy
```

---

## Trace Format

### JSON Trace (Rosetta unified format)

```json
{
  "trace_title": "Auction",
  "trace_actors": ["player1", "player2"],
  "configuration": {
    "tezos": { "use": "True" },
    "solana": {}, "evm": {}, "cardano": {}
  },
  "trace_execution": [
    {
      "sequence_id": "1",
      "function_name": "start",
      "waiting_time": 0,
      "actors": ["player1"],
      "args": {
        "reserve_amount": "100000000"
      },
      "tezos": {
        "entrypoint": "start",
        "provider_wallet": "player1",
        "mutez": 0,
        "send_transaction": true
      },
      "solana": {}, "evm": {}, "cardano": {}
    },
    {
      "sequence_id": "2",
      "function_name": "bid",
      "waiting_time": 1,
      "actors": ["player2"],
      "args": {
        "amount": "150000000"
      },
      "tezos": {
        "entrypoint": "bid",
        "provider_wallet": "player2",
        "mutez": 150000000,
        "send_transaction": true
      },
      "solana": {}, "evm": {}, "cardano": {}
    }
  ]
}
```

#### Tezos-specific fields in the `tezos` block

| Field | Type | Description |
|---|---|---|
| `entrypoint` | string | Name of the entrypoint to call |
| `provider_wallet` | string | Label of the wallet signing the transaction |
| `mutez` | number | Amount in mutez to send (0 if none) |
| `tezAmount` | number/string | Alternative to `mutez`, expressed in tez |
| `address` | string | Contract address (overrides `addressList.json`) |
| `send_transaction` | boolean | If `false`, the step is skipped |
| `parameters` | object/string | Parameter override (replaces `args`) |

#### Address resolution in `args`

In parameters, you can use the `{"address_of": "label"}` syntax to refer to an actor's address:

```json
{
  "args": {
    "recipient": { "address_of": "player2" }
  }
}
```

The system automatically resolves `"player2"` → `"tz1..."` from `pubKeyAddr.json`.

#### Amount parsing (`mutez` / `args`)

The module accepts amounts in various formats:

| Format | Result |
|---|---|
| `"0.5"` | 0.5 tez |

---

## Output and Reports

### `output_traces/<TraceName>.json`

Full structured report with cost analysis for each executed trace:

```json
{
  "trace_title": "Auction",
  "trace_actors_costs": {
    "player1": {
      "total_cost": 2479,
      "miner_fee": 979,
      "chain_fee": 1500
    },
    "player2": {
      "total_cost": 694,
      "miner_fee": 694,
      "chain_fee": 0
    }
  },
  "total_sequence_execution_costs": {
    "total_cost": 3173,
    "miner_fee": 1673,
    "chain_fee": 1500,
    "weight": 402,
    "average_block_delay": 7.5
  },
  "trace_execution_costs": {
    "1": {
      "function_name": "start",
      "actor": "player1",
      "total_cost": 1949,
      "miner_fee": 449,
      "chain_fee": 1500,
      "weight": 100,
      "hash": "ooE2JcM2B8151j1MyUiVM5NjuKziKMkiGFcKPmrCsYAT31epyyM",
      "block_delay": 7
    },
    "2": {
      "function_name": "bid",
      "actor": "player2",
      "total_cost": 346,
      "miner_fee": 346,
      "chain_fee": 0,
      "weight": 101,
      "hash": "oo1Z4rABoCtS44xi8iRYs6dPT2zWTj7hDw9e5R2y2p8UZydpUX3",
      "block_delay": 7
    }
  }
}
```

#### Report Fields

| Field | Description |
|---|---|
| `total_cost` | Total cost in mutez (miner_fee + chain_fee) |
| `miner_fee` | Fee paid to the baker in mutez |
| `chain_fee` | On-chain storage cost in mutez (size × 250) |
| `weight` | Operation weight in bytes |
| `block_delay` | Blocks elapsed between one operation and the next |
| `hash` | Tezos operation hash |

### `compiled/<Suite>_<Contract>_<Impl>/`

Compilation artifacts for each contract:

| File | Contents |
|---|---|
| `step_001_cont_0_contract.tz` | Contract code in text Michelson |
| `step_001_cont_0_contract.json` | Contract code in Micheline JSON |
| `step_001_cont_0_storage.tz` | Initial storage in text Michelson |
| `step_001_cont_0_storage.json` | Initial storage in Micheline JSON |
| `step_001_cont_0_types.py` | Python type definitions |
| `log.txt` | Compilation log with placeholders and metadata |

---

## Tezos Fee Model

The module extracts and calculates the following cost metrics for each operation:

| Metric | Formula | Unit |
|---|---|---|
| **Baker Fee** | Extracted from `content.fee` | mutez |
| **Consumed Gas** | Extracted from `consumed_milligas` | milligas |
| **Storage Cost** | `paid_storage_size_diff × 250` | mutez |
| **Total Cost** | `baker_fee + storage_cost` | mutez |
| **Operation Weight** | Extracted from `paid_storage_size_diff` | bytes |

### Reference Parameters (post-Delphi)

| Parameter | Value |
|---|---|
| Minimum base fee | 100 µꜩ |
| Cost per byte | 250 µꜩ/B |
| Gas limit per operation | 1,040,000 gu |
| Storage burn | 250 µꜩ/B (0.25 ꜩ/kB) |

---

## Flask Backend Integration

The Tezos module exposes its functionality through 7 endpoints in the Flask backend (`flask_backend.py`):

| Method | Endpoint | Internal Function | Description |
|---|---|---|---|
| `POST` | `/tezos_compile_deploy` | `compileAndDeployForTrace()` | Compile and/or originate a contract |
| `GET` | `/tezos_get_contracts` | `getCompiledContracts()` | List available compiled contracts |
| `POST` | `/tezos_get_entrypoints` | `entrypointAnalyse()` | Entrypoint schema for a contract |
| `POST` | `/tezos_get_contract_context` | `getEntrypointParameterTypes()` | Parameter types for an entrypoint |
| `POST` | `/tezos_interact_contract` | `entrypointCall()` | Call an entrypoint |
| `GET` | `/tezos_get_json_traces` | `jsonReaderByContract()` | List available JSON traces |
| `POST` | `/tezos_automatic_execution` | `execution_setup_auto()` | Run an automatic trace |

These endpoints are consumed by the Streamlit interface in `pages/Tezos.py`.
