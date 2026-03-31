# Extendable Toolchain for Smart Contract Traces

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Node.js](https://img.shields.io/badge/Node.js-18+-green?logo=node.js)
![Rust](https://img.shields.io/badge/Rust-stable-orange?logo=rust)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red?logo=streamlit)
![Flask](https://img.shields.io/badge/Backend-Flask-lightgrey?logo=flask)

A unified platform to **compile, deploy, and interact** with smart contracts across multiple blockchains through a single web interface. Originally developed as part of academic research on transaction fee and size estimation, it has grown into a comprehensive modular multi-chain environment.

---

## Supported Blockchains

| Blockchain | Status | Contract Language | Test Network |
|---|---|---|---|
| **Tezos** | ✅ Full support | SmartPy → Michelson | Ghostnet |
| **Ethereum / EVM** | ✅ Full support | Solidity 0.8.18 | Ganache (local) / Sepolia |
| **Solana** | ✅ Full support | Rust (Anchor) | Devnet |
| **Cardano** | 🚧 In development | — | — |

---

## Key Features

- **Unified trace format** — a single JSON file describes transaction sequences executable simultaneously across multiple chains
- **Parallel multi-chain execution** — the same trace runs on Solana, Ethereum, and Tezos in a single operation
- **Automatic and interactive modes** — run from JSON files or build instructions manually step by step
- **Integrated compilation** — SmartPy for Tezos, Solc/Hardhat for Ethereum, Anchor/Cargo for Solana
- **Wallet management** — view balances, keys, and perform operations on each chain
- **Execution reports** — detailed output with gas, transaction hashes, status, and errors for every step
- **Fee and size estimation** — compute transaction cost and size for Solana

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Streamlit UI (port 8501)            │
│   pages/: Rosetta.py | Solana.py | Ethereum.py  │
│            Tezos.py | Cardano.py                 │
└────────────────────┬────────────────────────────┘
                     │ HTTP REST
┌────────────────────▼────────────────────────────┐
│           Flask Backend (port 5000)              │
│              flask_backend.py                    │
│         22 multi-chain REST endpoints            │
└──────┬──────────────┬──────────────┬────────────┘
       │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────────┐
│ Tezos Module│ │ ETH Module │ │ Solana Module │
│  SmartPy    │ │  web3.py   │ │  anchorpy     │
│  pytezos    │ │  py-solc-x │ │  Anchor CLI   │
└──────┬──────┘ └─────┬──────┘ └────┬──────────┘
       │              │              │
   Ghostnet       Ganache/       Devnet/
  (testnet)       Sepolia       Testnet
```

---

## Project Structure

```
Tezos-ToolchainModule/
├── Rosetta_SC.py                    # Streamlit entry point (page router)
├── Rosetta_utils.py                 # Shared UI utilities (trace rendering, upload)
├── flask_backend.py                 # Flask REST backend (22 endpoints)
├── requirements.txt                 # Python dependencies
├── start.sh                         # Startup script (Flask + Streamlit)
├── .env                             # Environment variables (API keys)
│
├── pages/                           # Streamlit multi-chain pages
│   ├── Rosetta.py                   # Main dashboard (trace selection)
│   ├── Solana.py                    # Solana interface
│   ├── Ethereum.py                  # Ethereum/EVM interface
│   ├── Tezos.py                     # Tezos interface
│   └── Cardano.py                   # Cardano interface (WIP)
│
├── modules/
│   ├── Tezos_module/
│   │   ├── contracts/               # SmartPy contracts (.py)
│   │   ├── toolchain/               # Tezos execution engine
│   │   │   ├── main.py              # Main orchestrator
│   │   │   ├── contractUtils.py     # Compilation, origination, calls
│   │   │   ├── trace_utils.py       # Trace management and reports
│   │   │   ├── compiled/            # Michelson compilation output
│   │   │   └── output_traces/       # JSON execution reports
│   │
│   ├── Ethereum_module/
│   │   ├── hardhat_module/
│   │   │   ├── contracts/*.sol      # Solidity contracts
│   │   │   ├── artifacts/           # Compilation artifacts
│   │   │   ├── deployments/         # Deployment records with ABI
│   │   │   ├── execution_traces/    # JSON traces for EVM
│   │   │   └── package.json         # Node.js / Hardhat config
│   │   ├── ethereum_wallets/        # EVM wallets (JSON)
│   │   └── ethereum_utils.py        # Wallet and balance utilities
│   │
│   ├── Solana_module/
│   │   └── solana_module/
│   │       ├── anchor_module/
│   │       │   ├── anchor_programs/ # Rust programs (Anchor)
│   │       │   └── execution_traces/# JSON traces for Solana
│   │       ├── solana_wallets/      # JSON keypairs
│   │       └── requirements.txt     # Solana Python dependencies
│   │
│   └── Cardano_module/              # Stub (WIP)
│
└── rosetta_traces/                  # Pre-loaded sample traces
    └── README.md                    # Unified trace format specification
```

---

## Prerequisites

### General

- Python **3.12** with an active virtual environment
- macOS, Linux, or WSL Ubuntu 22.04+

### Tezos

- `pytezos` and `smartpy-tezos` (installed via `requirements.txt`)
- **libsodium** (native dependency required by pytezos):
  ```bash
  # macOS
  brew install libsodium
  # Ubuntu/WSL
  sudo apt-get install libsodium-dev
  ```
- SmartPy CLI installed globally

### Ethereum / EVM

- **Node.js 18+** and npm
- **Ganache CLI** for the local node:
  ```bash
  npm install -g ganache
  ```
- Python dependencies (`web3`, `py-solc-x`, `eth-account`) are in `requirements.txt`

### Solana

- **Rust toolchain** (`rustup` + `cargo`)
- **Solana CLI** (configured for Devnet/Testnet/Mainnet)
- **Anchor CLI** (`avm` recommended)
- **Node.js 18+** and npm

---

## Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd Tezos-ToolchainModule

# 2. Create and activate the Python virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Node.js dependencies for Ethereum (Hardhat)
cd modules/Ethereum_module/hardhat_module
npm install
cd ../../..

# 5. Configure environment variables
cp .env.example .env   # if it exists, otherwise create the file manually
# Edit .env and add your API keys (see Environment Variables section)
```

---

## Running the Application

### Quick start

```bash
./start.sh
```

The script automatically starts Flask (port 5000) and Streamlit (port 8501).

### Manual start (two terminals)

```bash
# Terminal 1 — Flask backend
source .venv/bin/activate
python flask_backend.py

# Terminal 2 — Streamlit UI
source .venv/bin/activate
streamlit run Rosetta_SC.py
```

### For Ethereum: start Ganache before using the EVM module

```bash
ganache --host 127.0.0.1 --port 8545 --accounts 10 --deterministic
```

> The default deterministic account is:
> Address: `0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1`
> Private Key: `0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d`
> Balance: 100 ETH

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Required to use external Ethereum networks (Sepolia, Mainnet, etc.)
INFURA_PROJECT_ID=your_infura_project_id

# Alternative API for Ethereum nodes
BLOCKPI_API_KEY=your_blockpi_api_key
```

Without these variables, the Ethereum module works only on local Ganache.

---

## Using the Toolchains

### Rosetta Page (Dashboard)

The main page allows you to:
- **Upload a JSON trace file** for multi-chain execution
- **Select a trace** from the pre-loaded files in `rosetta_traces/`
- Start parallel execution on all chains configured in the trace

---

### Tezos

Add contracts to `modules/Tezos_module/contracts/<ContractName>/<ContractName>.py`
The wallet is at `modules/Tezos_module/tezos_module/tezos_wallets/wallet.json`

From the **Tezos** menu:

| Action | Description |
|---|---|
| **Compile** | Compile the SmartPy contract to Michelson |
| **Deploy** | Originate the contract on Ghostnet |
| **Interact** | Call an entrypoint with parameters |
| **Execute Trace** | Run a full operation sequence from CSV |

---

### Ethereum / EVM

Add contracts to `modules/Ethereum_module/hardhat_module/contracts/*.sol`
Wallets are in `modules/Ethereum_module/ethereum_wallets/*.json`

From the **Ethereum** menu:

| Action | Description |
|---|---|
| **Manage Wallets** | View addresses and balances |
| **Upload Contract** | Upload a `.sol` file |
| **Compile & Deploy** | Compile with py-solc-x and deploy to Ganache/Sepolia/Mainnet |
| **Interactive** | Call contract functions (view or transaction) |
| **Execution Traces** | Run automatic JSON traces |

---

### Solana

Add wallets to `modules/Solana_module/solana_module/solana_wallets/*.json`
Add programs to `modules/Solana_module/solana_module/anchor_module/anchor_programs/`
Add traces to `modules/Solana_module/solana_module/anchor_module/execution_traces/*.json`

From the **Solana** menu:

| Action | Description |
|---|---|
| **Upload** | Upload a `.rs` file |
| **Compile & Deploy** | Compile and deploy to Devnet/Testnet/Mainnet |
| **Interactive Data Insertion** | Build and send instructions manually |
| **Execution Traces** | Run automatic sequences from JSON |

---

## Unified Trace Format

A **trace** is a JSON file that describes a sequence of operations executable on one or more blockchains simultaneously.

### Schema

```json
{
  "trace_title": "trace_name",
  "trace_actors": ["player1", "player2"],
  "configuration": {
    "solana": {},
    "evm":    {},
    "tezos":  {},
    "cardano":{}
  },
  "trace_execution": [
    {
      "sequence_id": "1",
      "function_name": "deposit",
      "waiting_time": 0,
      "actors": ["player1"],
      "args": { "amount": 1000 },
      "solana": {},
      "evm": {},
      "tezos": {},
      "cardano": {}
    }
  ]
}
```

### Main Fields

| Field | Type | Description |
|---|---|---|
| `trace_title` | string | Identifying name of the trace |
| `trace_actors` | string[] | Labels for the involved actors (e.g. "sender", "user") |
| `trace_execution` | Step[] | Ordered list of steps to execute |
| `sequence_id` | string/number | Step order within the sequence |
| `function_name` | string | Logical name of the function/entrypoint |
| `waiting_time` | number | Slots/blocks to wait before executing this step |
| `actors` | string[] | Subset of `trace_actors` involved in this step |
| `args` | object | Parameters shared across chains |

#### Solana PDA Options (`opt`)

| Value | Behavior |
|---|---|
| `"s"` | Generates the PDA from seeds specified in `"param"` |
| `"r"` | Generates a random-like address |
| `"p"` | Uses a manually provided base58 address in `"param"` |

Place trace files in:
`rosetta_traces/`

See `rosetta_traces/README.md` for the full format specification.

---

## Backend API (Flask)

The backend exposes 22 REST endpoints grouped by blockchain.

### Solana

| Method | Endpoint | Description |
|---|---|---|
| POST | `/wallet_balance` | Get wallet balance |
| POST | `/compile_deploy` | Compile and deploy program |
| POST | `/automatic_data_insertion` | Run JSON trace |
| POST | `/interactive_transaction` | Send manual instruction |
| GET | `/get_programs` | List available programs |
| POST | `/get_instructions` | Get program instructions |
| POST | `/get_program_context` | Context for an instruction |
| POST | `/close_program` | Program cleanup |

### Ethereum / EVM

| Method | Endpoint | Description |
|---|---|---|
| POST | `/eth_wallet_balance` | Get wallet balance |
| POST | `/eth_deployment_session` | Contract deployment session |
| GET | `/eth_get_contracts` | List contracts |
| POST | `/eth_get_functions` | Get contract functions |
| POST | `/eth_get_contract_context` | Context for a function |
| POST | `/eth_interact_contract` | Call contract function |

### Tezos

| Method | Endpoint | Description |
|---|---|---|
| POST | `/tezos_compile_deploy` | Compile and originate contract |
| GET | `/tezos_get_contracts` | List contracts |
| POST | `/tezos_get_entrypoints` | Get contract entrypoints |
| POST | `/tezos_get_contract_context` | Context for an entrypoint |
| POST | `/tezos_interact_contract` | Call entrypoint |
| GET | `/tezos_get_json_traces` | List available traces |
| POST | `/tezos_automatic_execution` | Run automatic trace |

### General

| Method | Endpoint | Description |
|---|---|---|
| GET | `/get_info` | Server info |

---

## Module-Specific READMEs

Each module has its own detailed documentation:

- [`modules/Tezos_module/README.md`](modules/Tezos_module/README.md)
- [`modules/Ethereum_module/README.md`](modules/Ethereum_module/README.md) — includes wallet security notes and network setup
- [`modules/Solana_module/README.md`](modules/Solana_module/README.md) — includes architecture diagrams
- [`rosetta_traces/README.md`](rosetta_traces/README.md) — full unified trace format specification
