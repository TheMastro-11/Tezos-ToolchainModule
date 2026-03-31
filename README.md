# Extendable Toolchain for Smart Contract Traces

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Node.js](https://img.shields.io/badge/Node.js-18+-green?logo=node.js)
![Rust](https://img.shields.io/badge/Rust-stable-orange?logo=rust)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red?logo=streamlit)
![Flask](https://img.shields.io/badge/Backend-Flask-lightgrey?logo=flask)

Una piattaforma unificata per **compilare, deployare e interagire** con smart contract su più blockchain tramite un'unica interfaccia web. Sviluppata nell'ambito di una ricerca accademica sulla stima di fee e dimensioni delle transazioni, è cresciuta in un ambiente modulare multi-chain completo.

---

## Blockchain supportate

| Blockchain | Stato | Linguaggio contratti | Rete di test |
|---|---|---|---|
| **Tezos** | ✅ Completo | SmartPy → Michelson | Ghostnet |
| **Ethereum / EVM** | ✅ Completo | Solidity 0.8.18 | Ganache (locale) / Sepolia |
| **Solana** | ✅ Completo | Rust (Anchor) | Devnet |
| **Cardano** | 🚧 In sviluppo | — | — |

---

## Funzionalità principali

- **Formato trace unificato** — un singolo file JSON descrive sequenze di transazioni eseguibili contemporaneamente su più chain
- **Esecuzione multi-chain parallela** — la stessa trace viene eseguita su Solana, Ethereum e Tezos in un'unica operazione
- **Modalità automatica e interattiva** — esecuzione da file JSON oppure costruzione manuale passo-passo delle istruzioni
- **Compilazione integrata** — SmartPy per Tezos, Solc/Hardhat per Ethereum, Anchor/Cargo per Solana
- **Gestione wallet** — visualizzazione saldi, chiavi e operazioni per ogni chain
- **Report di esecuzione** — output dettagliato con gas, hash transazione, stato e errori per ogni step
- **Stima fee e dimensioni** — calcolo del costo e della dimensione delle transazioni Solana

---

## Architettura

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
│         22 endpoint REST multi-chain            │
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

## Struttura del progetto

```
Tezos-ToolchainModule/
├── Rosetta_SC.py                    # Entry point Streamlit (router pagine)
├── Rosetta_utils.py                 # Utility condivise UI (rendering trace, upload)
├── flask_backend.py                 # Backend REST Flask (22 endpoint)
├── requirements.txt                 # Dipendenze Python
├── start.sh                         # Script avvio (Flask + Streamlit)
├── .env                             # Variabili d'ambiente (API keys)
│
├── pages/                           # Pagine Streamlit multi-chain
│   ├── Rosetta.py                   # Dashboard principale (selezione trace)
│   ├── Solana.py                    # Interfaccia Solana
│   ├── Ethereum.py                  # Interfaccia Ethereum/EVM
│   ├── Tezos.py                     # Interfaccia Tezos
│   └── Cardano.py                   # Interfaccia Cardano (WIP)
│
├── modules/
│   ├── Tezos_module/
│   │   ├── contracts/               # Contratti SmartPy (.py)
│   │   ├── toolchain/               # Motore di esecuzione Tezos
│   │   │   ├── main.py              # Orchestratore principale
│   │   │   ├── contractUtils.py     # Compilazione, origination, chiamate
│   │   │   ├── trace_utils.py       # Gestione e report trace
│   │   │   ├── compiled/            # Output compilazione Michelson
│   │   │   └── output_traces/       # Report esecuzione JSON
│   │
│   ├── Ethereum_module/
│   │   ├── hardhat_module/
│   │   │   ├── contracts/*.sol      # Contratti Solidity
│   │   │   ├── artifacts/           # Artefatti compilazione
│   │   │   ├── deployments/         # Record deployment con ABI
│   │   │   ├── execution_traces/    # Trace JSON per EVM
│   │   │   └── package.json         # Config Node.js / Hardhat
│   │   ├── ethereum_wallets/        # Wallet EVM (JSON)
│   │   └── ethereum_utils.py        # Utility wallet e saldi
│   │
│   ├── Solana_module/
│   │   └── solana_module/
│   │       ├── anchor_module/
│   │       │   ├── anchor_programs/ # Programmi Rust (Anchor)
│   │       │   └── execution_traces/# Trace JSON per Solana
│   │       ├── solana_wallets/      # Keypair JSON
│   │       └── requirements.txt     # Dipendenze Python Solana
│   │
│   └── Cardano_module/              # Stub (WIP)
│
└── rosetta_traces/                  # Trace di esempio pre-caricati
    └── README.md                    # Specifica formato trace JSON
```

---

## Prerequisiti

### Generali

- Python **3.12** con virtual environment attivo
- macOS, Linux, o WSL Ubuntu 22.04+

### Tezos

- `pytezos` e `smartpy-tezos` (installati via `requirements.txt`)
- **libsodium** (dipendenza nativa richiesta da pytezos):
  ```bash
  # macOS
  brew install libsodium
  # Ubuntu/WSL
  sudo apt-get install libsodium-dev
  ```
- SmartPy CLI installata globalmente

### Ethereum / EVM

- **Node.js 18+** e npm
- **Ganache CLI** per il nodo locale:
  ```bash
  npm install -g ganache
  ```
- Le dipendenze Python (`web3`, `py-solc-x`, `eth-account`) sono in `requirements.txt`

### Solana

- **Rust toolchain** (`rustup` + `cargo`)
- **Solana CLI** (configurata per Devnet/Testnet/Mainnet)
- **Anchor CLI** (`avm` raccomandato)
- **Node.js 18+** e npm

---

## Installazione

```bash
# 1. Clona il repository
git clone <repository-url>
cd Tezos-ToolchainModule

# 2. Crea e attiva il virtual environment Python
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Installa le dipendenze Python
pip install -r requirements.txt

# 4. Installa le dipendenze Node.js per Ethereum (Hardhat)
cd modules/Ethereum_module/hardhat_module
npm install
cd ../../..

# 5. Configura le variabili d'ambiente
cp .env.example .env   # se esiste, altrimenti crea il file manualmente
# Edita .env e inserisci le tue API key (vedi sezione Variabili d'ambiente)
```

---

## Avvio

### Metodo rapido

```bash
./start.sh
```

Lo script avvia automaticamente Flask (porta 5000) e Streamlit (porta 8501).

### Avvio manuale (due terminali)

```bash
# Terminale 1 — Backend Flask
source .venv/bin/activate
python flask_backend.py

# Terminale 2 — UI Streamlit
source .venv/bin/activate
streamlit run Rosetta_SC.py
```

### Per Ethereum: avvia Ganache prima di usare il modulo EVM

```bash
ganache --host 127.0.0.1 --port 8545 --accounts 10 --deterministic
```

> L'account deterministic di default è:
> Address: `0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1`
> Private Key: `0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d`
> Balance: 100 ETH

---

## Variabili d'ambiente

Crea un file `.env` nella root del progetto:

```env
# Necessario per usare reti Ethereum esterne (Sepolia, Mainnet, ecc.)
INFURA_PROJECT_ID=your_infura_project_id

# API alternativa per nodi Ethereum
BLOCKPI_API_KEY=your_blockpi_api_key
```

Senza queste variabili, il modulo Ethereum funziona solo su Ganache locale.

---

## Uso dei toolchain

### Pagina Rosetta (Dashboard)

La pagina principale permette di:
- **Caricare un file trace JSON** per esecuzione multi-chain
- **Selezionare una trace** dai file precaricati in `rosetta_traces/`
- Avviare l'esecuzione parallela su tutte le chain configurate nella trace

---

### Tezos

Aggiungi i contratti in `modules/Tezos_module/contracts/<NomeContratto>/<NomeContratto>.py`
Il wallet è in `modules/Tezos_module/tezos_module/tezos_wallets/wallet.json`

Dal menu **Tezos**:

| Azione | Descrizione |
|---|---|
| **Compile** | Compila il contratto SmartPy in Michelson |
| **Deploy** | Origina il contratto su Ghostnet |
| **Interact** | Chiama un entrypoint con parametri |
| **Execute Trace** | Esegue una sequenza di operazioni da CSV |

---

### Ethereum / EVM

Aggiungi contratti in `modules/Ethereum_module/hardhat_module/contracts/*.sol`
I wallet sono in `modules/Ethereum_module/ethereum_wallets/*.json`

Dal menu **Ethereum**:

| Azione | Descrizione |
|---|---|
| **Manage Wallets** | Visualizza indirizzi e saldi |
| **Upload Contract** | Carica un file `.sol` |
| **Compile & Deploy** | Compila con py-solc-x e deploya su Ganache/Sepolia/Mainnet |
| **Interactive** | Chiama funzioni del contratto (view o transazione) |
| **Execution Traces** | Esegui trace JSON automatiche |

---

### Solana

Aggiungi wallet in `modules/Solana_module/solana_module/solana_wallets/*.json`
Aggiungi programmi in `modules/Solana_module/solana_module/anchor_module/anchor_programs/`
Aggiungi trace in `modules/Solana_module/solana_module/anchor_module/execution_traces/*.json`

Dal menu **Solana**:

| Azione | Descrizione |
|---|---|
| **Upload** | Carica un file `.rs` |
| **Compile & Deploy** | Compila e deploya su Devnet/Testnet/Mainnet |
| **Interactive Data Insertion** | Costruisci e invia istruzioni manualmente |
| **Execution Traces** | Esegui sequenze automatiche da JSON |

---

## Formato Trace Unificato

Una **trace** è un file JSON che descrive una sequenza di operazioni eseguibili su una o più blockchain contemporaneamente.

### Schema

```json
{
  "trace_title": "nome_della_trace",
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

### Campi principali

| Campo | Tipo | Descrizione |
|---|---|---|
| `trace_title` | string | Nome identificativo della trace |
| `trace_actors` | string[] | Label degli attori coinvolti (es. "sender", "user") |
| `trace_execution` | Step[] | Lista ordinata di passi da eseguire |
| `sequence_id` | string/number | Ordine del passo nella sequenza |
| `function_name` | string | Nome logico della funzione/entrypoint |
| `waiting_time` | number | Slot/blocchi da attendere prima dell'esecuzione |
| `actors` | string[] | Subset di `trace_actors` coinvolti in questo step |
| `args` | object | Parametri condivisi tra le chain |

#### Opzioni PDA Solana (`opt`)

| Valore | Comportamento |
|---|---|
| `"s"` | Genera il PDA dai seed specificati in `"param"` |
| `"r"` | Genera un indirizzo casuale |
| `"p"` | Usa un indirizzo base58 fornito manualmente in `"param"` |

Posiziona i file trace in:
 `rosetta_traces/`

Consulta `rosetta_traces/README.md` per la specifica completa del formato.

---

## API Backend (Flask)

Il backend espone 22 endpoint REST raggruppati per blockchain.

### Solana

| Method | Endpoint | Descrizione |
|---|---|---|
| POST | `/wallet_balance` | Saldo wallet |
| POST | `/compile_deploy` | Compila e deploya programma |
| POST | `/automatic_data_insertion` | Esegui trace JSON |
| POST | `/interactive_transaction` | Invia istruzione manuale |
| GET | `/get_programs` | Lista programmi disponibili |
| POST | `/get_instructions` | Istruzioni del programma |
| POST | `/get_program_context` | Contesto per un'istruzione |
| POST | `/close_program` | Cleanup programma |

### Ethereum / EVM

| Method | Endpoint | Descrizione |
|---|---|---|
| POST | `/eth_wallet_balance` | Saldo wallet |
| POST | `/eth_deployment_session` | Sessione deployment contratto |
| GET | `/eth_get_contracts` | Lista contratti |
| POST | `/eth_get_functions` | Funzioni del contratto |
| POST | `/eth_get_contract_context` | Contesto per una funzione |
| POST | `/eth_interact_contract` | Chiama funzione contratto |

### Tezos

| Method | Endpoint | Descrizione |
|---|---|---|
| POST | `/tezos_compile_deploy` | Compila e origina contratto |
| GET | `/tezos_get_contracts` | Lista contratti |
| POST | `/tezos_get_entrypoints` | Entrypoint del contratto |
| POST | `/tezos_get_contract_context` | Contesto per un entrypoint |
| POST | `/tezos_interact_contract` | Chiama entrypoint |
| GET | `/tezos_get_json_traces` | Lista trace disponibili |
| POST | `/tezos_automatic_execution` | Esegui trace automatica |

### Generale

| Method | Endpoint | Descrizione |
|---|---|---|
| GET | `/get_info` | Info server |

---

## Moduli — README specifici

Ogni modulo ha la propria documentazione dettagliata:

- [`modules/Tezos_module/README.md`](modules/Tezos_module/README.md)
- [`modules/Ethereum_module/README.md`](modules/Ethereum_module/README.md) — include note su sicurezza wallet e reti
- [`modules/Solana_module/README.md`](modules/Solana_module/README.md) — include architettura e diagrammi
- [`rosetta_traces/README.md`](rosetta_traces/README.md) — specifica completa formato trace JSON
