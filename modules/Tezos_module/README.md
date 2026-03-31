# Tezos Module

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![SmartPy](https://img.shields.io/badge/SmartPy-latest-teal)
![PyTezos](https://img.shields.io/badge/PyTezos-latest-purple)
![Network](https://img.shields.io/badge/Network-Ghostnet-lightblue)

Modulo completo per la **gestione del ciclo di vita dei smart contract Tezos**: compilazione SmartPy → Michelson, deployment su Ghostnet, interazione con entrypoint, esecuzione di trace automatizzate e analisi dei costi di transazione.

---

## Indice

- [Struttura del modulo](#struttura-del-modulo)
- [Prerequisiti](#prerequisiti)
- [Configurazione](#configurazione)
- [Contratti disponibili](#contratti-disponibili)
- [Architettura del toolchain](#architettura-del-toolchain)
- [Componenti principali](#componenti-principali)
- [Workflow operativi](#workflow-operativi)
- [Formato Trace](#formato-trace)
- [Output e report](#output-e-report)
- [Modello di fee Tezos](#modello-di-fee-tezos)
- [Integrazione con il backend Flask](#integrazione-con-il-backend-flask)

---

## Struttura del modulo

```
Tezos_module/
├── contracts/
│   ├── addressList.json             # Indirizzi KT1... dei contratti deployati
│   ├── deploymentLevels.json        # Livelli di blocco dei deployment
│   ├── Library/
│   │   └── fa2Lib.py                # Libreria standard FA2 (token)
│   ├── Legacy/                      # Implementazioni originali (vecchia sintassi)
│   │   ├── Auction/
│   │   ├── CrowdFunding/
│   │   ├── Escrow/
│   │   ├── HTLC/
│   │   ├── SimpleTransfer/
│   │   ├── Storage/
│   │   ├── Vault/
│   │   ├── Vesting/
│   │   └── ... (altri 9 contratti)
│   └── Rosetta/                     # Implementazioni standardizzate (sintassi attuale)
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
│       └── scenarios/               # Scenari di test SmartPy per ogni contratto
│
└── toolchain/
    ├── main.py                      # Orchestratore CLI (847 righe)
    ├── contractUtils.py             # Operazioni blockchain via PyTezos (442 righe)
    ├── trace_utils.py               # Utility Streamlit e logica trace (520 righe)
    ├── jsonUtils.py                 # Persistenza JSON indirizzi e trace (308 righe)
    ├── folderScan.py                # Scanner directory contratti (72 righe)
    ├── dapp.py                      # Interfaccia web Streamlit (387 righe)
    ├── wallet.json                  # Chiavi private wallet (edsk...)
    ├── pubKeyAddr.json              # Mapping label → indirizzo tz1...
    ├── compiled/                    # Artefatti Michelson compilati
    │   └── <Suite>_<Contract>_<Impl>/
    │       ├── step_001_cont_0_contract.tz
    │       ├── step_001_cont_0_storage.tz
    │       ├── step_001_cont_0_contract.json
    │       ├── step_001_cont_0_storage.json
    │       ├── step_001_cont_0_types.py
    │       └── log.txt
    ├── output_traces/               # Report JSON delle trace eseguite
    │   ├── Auction.json
    │   ├── SimpleWallet.json
    │   └── template.json
    └── transactionsOutput.json      # Sommario JSON delle ultime transazioni
```

---

## Prerequisiti

### Dipendenze Python

Installate tramite `requirements.txt` nella root del progetto:

```
pytezos
smartpy-tezos
```

### Dipendenza nativa: libsodium

PyTezos richiede la libreria nativa `libsodium`:

```bash
# macOS
brew install libsodium

# Ubuntu / WSL
sudo apt-get install libsodium-dev
```

### SmartPy CLI

Richiesta per la compilazione. Installazione ufficiale:

```bash
pip install smartpy-tezos
```

Verifica:

```bash
python -c "import smartpy; print(smartpy.__version__)"
```

---

## Configurazione

### wallet.json

Contiene le chiavi private dei wallet utilizzati nel toolchain. Va posizionato in `toolchain/wallet.json`:

```json
{
    "admin":   "edsk...",
    "oracle":  "edsk...",
    "player1": "edsk...",
    "player2": "edsk...",
    "player3": "edsk..."
}
```

> Le chiavi `edsk...` sono chiavi private Tezos in formato base58. Usa account Ghostnet senza fondi reali.

### pubKeyAddr.json

Mapping opzionale da label a indirizzo pubblico `tz1...`. Usato dalla funzione `resolveAddressOf` per sostituire label come `{"address_of": "player1"}` con l'indirizzo reale nei parametri delle trace:

```json
{
    "admin":   "tz1SL2xBdmLSD2W3Hs84SfH912xDpYtAjsaa",
    "oracle":  "tz1ZNfCeehri4t8oFNB187DDEAqtdu3Ayc1z",
    "player1": "tz1SL2xBdmLSD2W3Hs84SfH912xDpYtAjsaa",
    "player2": "tz1aLPm3WynyHRXFvjjdHZDKEjHZVvQMGxqU",
    "player3": "tz1ZNfCeehri4t8oFNB187DDEAqtdu3Ayc1z"
}
```

### Rete

Il modulo opera su **Ghostnet** (testnet pubblica Tezos). La connessione è gestita da PyTezos:

```python
client = pytezos.using(shell="ghostnet", key=private_key)
```

---

## Contratti disponibili

### Suite Rosetta (implementazioni correnti)

| Contratto | Descrizione | Entrypoint principali |
|---|---|---|
| **Auction** | Asta inglese on-chain | `start`, `bid`, `withdraw`, `end` |
| **Bet** | Scommessa tra due parti | `create`, `join`, `resolve` |
| **Crowdfund** | Raccolta fondi con obiettivo | `contribute`, `withdraw`, `claim` |
| **Escrow** | Deposito fiduciario controllato | `deposit`, `release`, `refund` |
| **Factory** | Pattern factory per contratti | `create`, `get` |
| **HTLC** | Hash Time Locked Contract (atomic swap) | `lock`, `redeem`, `refund` |
| **Lottery** | Lotteria con estrazione | `buy`, `draw`, `claim` |
| **PaymentSplitter** | Divisione revenue tra beneficiari | `addPayee`, `release` |
| **PriceBet** | Scommessa su prezzo oracle | `bet`, `resolve` |
| **SimpleTransfer** | Trasferimento XTZ base | `transfer` |
| **SimpleWallet** | Wallet multi-sig | `deposit`, `withdraw`, `approve` |
| **Storage** | Storage generico dati | `store`, `retrieve` |
| **UpgradableProxy** | Proxy pattern aggiornabile | `upgrade`, `call` |
| **Vault** | Vault/staking token | `deposit`, `withdraw` |
| **Vesting** | Vesting schedule token | `release`, `revoke` |
| **AnonymousData** | Storage dati con anonimato | `submit`, `retrieve` |
| **ConstantProductAmm** | AMM (Automated Market Maker) | `addLiquidity`, `swap`, `removeLiquidity` |
| **TicketGenerator** | Generatore ticket Tezos | `mint`, `transfer`, `burn` |

### Suite Legacy

Versioni precedenti degli stessi contratti, scritte con la sintassi SmartPy pre-unificata. Mantenute per compatibilità e confronto.

### Scenari di test

Ogni contratto Rosetta ha una cartella `scenarios/` con scenari SmartPy eseguibili per verificarne la logica localmente:

```
contracts/Rosetta/Auction/scenarios/
└── AuctionScenario.py   # Test scenario SmartPy completo
```

---

## Architettura del toolchain

```
                ┌─────────────────────┐
                │  Interfacce utente  │
                ├──────────┬──────────┤
                │  dapp.py │ main.py  │
                │(Streamlit)│  (CLI)   │
                └────┬─────┴────┬─────┘
                     │          │
          ┌──────────▼──────────▼──────────┐
          │          main.py               │
          │  (orchestratore operazioni)    │
          └──┬───────────┬────────────┬───┘
             │           │            │
   ┌─────────▼──┐  ┌─────▼──────┐  ┌─▼──────────┐
   │contractUtils│  │ jsonUtils  │  │ trace_utils │
   │(blockchain) │  │(persistenza│  │(UI helpers) │
   └─────────┬──┘  │ dati)      │  └─────────────┘
             │     └─────┬──────┘
   ┌─────────▼──┐        │
   │  PyTezos   │  ┌─────▼──────┐
   │  (RPC)     │  │folderScan  │
   └─────────┬──┘  └────────────┘
   ┌─────────▼──────────────────┐
   │       Tezos Ghostnet       │
   │  (nodo RPC pubblico)       │
   └────────────────────────────┘
```

### Separazione delle responsabilità

| Modulo | Responsabilità |
|---|---|
| `main.py` | Orchestrazione, menu CLI, parsing parametri, risoluzione indirizzi, esecuzione trace |
| `contractUtils.py` | Tutte le operazioni blockchain (compile, originate, call, inspect) |
| `jsonUtils.py` | Lettura/scrittura di `addressList.json`, `deploymentLevels.json`, trace JSON, output report |
| `trace_utils.py` | Componenti UI Streamlit, cattura output, rendering report, session state |
| `folderScan.py` | Scansione directory contratti e scenari |
| `dapp.py` | Routing viste Streamlit, interfaccia web completa |

---

## Componenti principali

### `contractUtils.py` — Operazioni blockchain

#### Compilazione

```python
compileContract(contractPath: str) -> subprocess.CompletedProcess
```

Esegue il file `.py` del contratto SmartPy come subprocess. SmartPy genera automaticamente i file Michelson nella directory di output:
- `step_001_cont_0_contract.tz` — codice Michelson
- `step_001_cont_0_storage.tz` — storage iniziale
- `log.txt` — metadati e placeholder

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

Origina il contratto sulla blockchain. Converte Michelson in formato Micheline, forgia e firma l'operazione, attende la conferma (timeout: 500s, polling ogni 15s).

Per contratti multipli dallo stesso artefatto:

```python
multiOrigination(
    client, artifactDir, contractId, initialBalance,
    normalizeContractNameFn, addressUpdateFn, updateDeploymentLevelFn
) -> list[dict]
```

---

#### Chiamata entrypoint

```python
entrypointCall(
    client: PyTezos,
    contractAddress: str,        # KT1...
    entrypointName: str,
    parameters: list | dict,
    tezAmount: Decimal           # in tez (non mutez)
) -> dict | None
```

---

#### Ispezione entrypoint

```python
entrypointAnalyse(client: PyTezos, contractAddress: str) -> dict
```

Restituisce lo schema degli entrypoint del contratto deployato, utile per la modalità interattiva.

---

#### Risultato operazione — strutture dati

**Deploy report** (da `contractInfoResult`):

```python
{
    "hash":           str,   # hash operazione
    "address":        str,   # KT1... indirizzo contratto deployato
    "BakerFee":       int,   # fee baker in mutez
    "Gas":            int,   # gas consumato in milligas
    "Storage":        int,   # costo storage in mutez (size × 250)
    "TotalCost":      int,   # BakerFee + Storage
    "ConfirmedLevel": int    # livello blocco di conferma
}
```

**Call report** (da `callInfoResult`):

```python
{
    "Hash":       str,   # hash operazione
    "BakerFee":   int,   # fee baker in mutez
    "Gas":        int,   # gas consumato in milligas
    "Storage":    int,   # incremento storage in mutez
    "TotalCost":  int,   # BakerFee + Storage
    "Weight":     int    # peso operazione in byte
}
```

---

### `main.py` — Orchestratore

#### Funzioni chiave di risoluzione

```python
# Analisi AST del sorgente SmartPy per estrarre parametri
getEntrypointParameterNames(contractId, entrypointName) -> list[str]
getEntrypointParameterTypes(contractId, entrypointName) -> dict[str, str]

# Risoluzione indirizzi da label ({"address_of": "player1"} → "tz1...")
resolveAddressOf(value) -> any

# Coercizione parametri al formato PyTezos
coerceParameterForTezos(value, param_type_str) -> any

# Parsing importi (supporta "0.5")
parseAmountToTez(amountValue) -> Decimal
```

#### Normalizzazione label wallet

Tutti i label sono normalizzati a minuscolo senza spazi:

```
"Player1" → "player1"
"ADMIN"   → "admin"
" Oracle" → "oracle"
```

#### Catena di risoluzione indirizzi contratto

Quando cerca l'indirizzo di un contratto in `addressList.json`, il sistema prova in ordine:
1. Contract ID esatto
2. Nome contratto normalizzato
3. Nome cartella (se contiene ":")
4. Basename cartella
5. Nome cartella normalizzato
6. Formato doppio-normalizzato (`"SimpleTransfer_SimpleTransfer"`)

---

### `jsonUtils.py` — Persistenza dati

#### Gestione indirizzi

```python
addressUpdate(contract: str, newAddress: str) -> dict
# Aggiorna addressList.json con il nuovo indirizzo KT1...

getAddress() -> dict
# Legge e restituisce addressList.json completo

resolveAddress(addressValid: dict, contractId: str) -> str
# Cerca indirizzo con fallback multipli
```

#### Gestione trace

```python
jsonReader(traceRoot: Path) -> dict
# Legge tutti i file .json trace da una directory
# Ritorna: {trace_name: trace_data}

jsonReaderByContract(traceRoot: Path) -> dict
# Legge trace organizzate per cartella contratto
# Ritorna: {contract: {trace_name: trace_data}}
```

#### Livelli di deployment

```python
updateDeploymentLevel(contract: str, confirmedLevel: int) -> dict
# Aggiorna deploymentLevels.json con il livello blocco

getDeploymentLevel(contractId: str) -> int | None
# Recupera livello di deployment (usato per calcolo block delay)
```

---

### `trace_utils.py` — Utility Streamlit

#### Cattura output terminale

```python
class StreamlitTerminalWriter(io.TextIOBase):
    # Stream testuale per catturare stdout/stderr in Streamlit
    def write(self, text: str) -> int
    def getvalue(self) -> str

run_with_terminal_output(action, session_key, render_live, output_placeholder)
# Esegue action() catturando tutto l'output in Streamlit
```

#### Gestione session state

```python
get_trace_report_state() -> dict | None
save_trace_report(report_data: dict) -> None
save_trace_setup_config(config_data: dict) -> None
get_last_trace_setup() -> dict | None
```

#### Rendering report

```python
render_trace_report() -> None
# Renderizza il report completo trace con metriche, fasi e dettagli

render_live_trace_progress(title, total_traces, show_terminal_output)
# Crea elementi UI per il progresso in tempo reale

render_execution_phase_payload(payload: dict) -> None
# Mostra statistiche dettagliate di esecuzione
```

#### Esecuzione trace con report

```python
run_trace_with_report(
    trace_name, trace_data, contract_name,
    should_compile, initial_balance, preferred_suite,
    render_live, output_placeholder
) -> dict
```

Esegue l'intera pipeline (compilazione → deployment → esecuzione) restituendo un report strutturato con tre fasi:

```python
{
    "compile":  {"status": "success"|"error"|"skipped", "output": str, "payload": dict},
    "deploy":   {"status": "success"|"error"|"skipped", "output": str, "payload": dict},
    "execute":  {"status": "success"|"error",           "output": str, "payload": dict}
}
```

---

## Workflow operativi

### Workflow A — Compilazione

```
1. Selezione suite (Legacy / Rosetta)
2. Selezione contratto dalla directory
3. compileContract(contractPath)
   └── Subprocess: python <contratto>.py
       └── SmartPy genera:
           ├── step_001_cont_0_contract.tz   (codice Michelson)
           ├── step_001_cont_0_storage.tz    (storage iniziale)
           ├── step_001_cont_0_contract.json
           └── log.txt
4. Salvataggio in compiled/<Suite>_<Contract>_<Impl>/
```

---

### Workflow B — Deployment (Origination)

```
1. Selezione contratto compilato
2. Impostazione bilancio iniziale (in tez)
3. Lettura file Michelson da compiled/
4. Conversione Michelson → Micheline (PyTezos)
5. client.origination(script={code, storage}, balance=initialBalance)
6. Attesa conferma (timeout 500s, polling 15s)
7. Estrazione indirizzo KT1... dal risultato
8. Aggiornamento addressList.json
9. Aggiornamento deploymentLevels.json (livello blocco)
```

---

### Workflow C — Interazione interattiva

```
1. Selezione contratto da addressList.json
2. entrypointAnalyse(client, KT1...) → schema entrypoint
3. Selezione entrypoint
4. Input parametri (con type-coercion automatica)
5. Input importo tez
6. entrypointCall(client, KT1..., entrypoint, params, amount)
7. Attesa conferma
8. callInfoResult(opResult) → {BakerFee, Gas, Storage, Weight, Hash}
9. Export opzionale in JSON
```

---

### Workflow D — Esecuzione trace JSON automatizzata

```
1. Lettura trace da rosetta_traces/ o execution_traces/
2. normalizeJsonTrace(traceData):
   ├── Estrazione label wallet (trace_actors + provider_wallet)
   ├── Costruzione wallet map (label → wallet_id)
   └── Per ogni step:
       ├── resolveStepWallet() → wallet da usare
       ├── buildStepParameters() → parametri con address resolution
       └── parseAmountToTez() → importo in tez
3. executionSetupJson():
   ├── getAddress() → indirizzo contratto da addressList.json
   └── Per ogni step in ordine:
       ├── waitForBlockDelay() se waiting_time > 0
       ├── entrypointCall(client, KT1..., ...)
       └── callInfoResult() → costi step
4. exportTraceResult():
   ├── Aggregazione costi per actor
   ├── Calcolo statistiche totali
   └── Scrittura output_traces/<TraceName>.json
```

---

### Workflow E — Test scenario SmartPy

```
1. scenarioScan() → lista scenari disponibili
2. Selezione scenario
3. runScenario(scenarioPath) → subprocess python scenario.py
4. Output HTML/log risultato SmartPy
```

---

## Formato Trace

### Trace JSON (formato unificato Rosetta)

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

#### Campi specifici per Tezos nel blocco `tezos`

| Campo | Tipo | Descrizione |
|---|---|---|
| `entrypoint` | string | Nome dell'entrypoint da chiamare |
| `provider_wallet` | string | Label del wallet che firma la transazione |
| `mutez` | number | Importo in mutez da inviare (0 se nessuno) |
| `tezAmount` | number/string | Alternativa a `mutez`, in tez |
| `address` | string | Indirizzo contratto (override di `addressList.json`) |
| `send_transaction` | boolean | Se `false`, lo step viene saltato |
| `parameters` | object/string | Override parametri (sostituisce `args`) |

#### Risoluzione indirizzi in `args`

Nei parametri è possibile usare la sintassi `{"address_of": "label"}` per riferirsi all'indirizzo di un actor:

```json
{
  "args": {
    "recipient": { "address_of": "player2" }
  }
}
```

Il sistema risolve automaticamente `"player2"` → `"tz1..."` da `pubKeyAddr.json`.

#### Parsing importi (`mutez` / `args`)

Il modulo accetta importi in vari formati:

| Formato | Risultato |
|---|---|
| `"0.5"` | 0.5 tez |

---

## Output e report

### `output_traces/<TraceName>.json`

Report strutturato completo con analisi dei costi per trace eseguita:

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

#### Campi del report

| Campo | Descrizione |
|---|---|
| `total_cost` | Costo totale in mutez (miner_fee + chain_fee) |
| `miner_fee` | Fee pagata al baker (miner) in mutez |
| `chain_fee` | Costo storage on-chain in mutez (size × 250) |
| `weight` | Peso operazione in byte |
| `block_delay` | Blocchi attesi tra un'operazione e la successiva |
| `hash` | Hash operazione Tezos |

### `compiled/<Suite>_<Contract>_<Impl>/`

Artefatti di compilazione per ogni contratto:

| File | Contenuto |
|---|---|
| `step_001_cont_0_contract.tz` | Codice contratto in Michelson testuale |
| `step_001_cont_0_contract.json` | Codice contratto in Micheline JSON |
| `step_001_cont_0_storage.tz` | Storage iniziale in Michelson |
| `step_001_cont_0_storage.json` | Storage iniziale in Micheline JSON |
| `step_001_cont_0_types.py` | Definizioni dei tipi Python |
| `log.txt` | Log compilazione con placeholder e metadati |

---

## Modello di fee Tezos

Il modulo estrae e calcola le seguenti metriche di costo per ogni operazione:

| Metrica | Formula | Unità |
|---|---|---|
| **Baker Fee** | Estratto da `content.fee` | mutez |
| **Gas consumato** | Estratto da `consumed_milligas` | milligas |
| **Costo storage** | `paid_storage_size_diff × 250` | mutez |
| **Costo totale** | `baker_fee + storage_cost` | mutez |
| **Peso operazione** | Estratto da `paid_storage_size_diff` | byte |

### Parametri di riferimento (post-Delphi)

| Parametro | Valore |
|---|---|
| Fee minima base | 100 µꜩ |
| Costo per byte | 250 µꜩ/B |
| Gas limit per operazione | 1.040.000 gu |
| Storage burn | 250 µꜩ/B (0.25 ꜩ/kB) |

---

## Integrazione con il backend Flask

Il modulo Tezos espone le sue funzionalità tramite 7 endpoint nel backend Flask (`flask_backend.py`):

| Method | Endpoint | Funzione interna chiamata | Descrizione |
|---|---|---|---|
| `POST` | `/tezos_compile_deploy` | `compileAndDeployForTrace()` | Compila e/o origina un contratto |
| `GET` | `/tezos_get_contracts` | `getCompiledContracts()` | Lista contratti compilati disponibili |
| `POST` | `/tezos_get_entrypoints` | `entrypointAnalyse()` | Schema entrypoint di un contratto |
| `POST` | `/tezos_get_contract_context` | `getEntrypointParameterTypes()` | Tipi parametri di un entrypoint |
| `POST` | `/tezos_interact_contract` | `entrypointCall()` | Chiama un entrypoint |
| `GET` | `/tezos_get_json_traces` | `jsonReaderByContract()` | Lista trace JSON disponibili |
| `POST` | `/tezos_automatic_execution` | `execution_setup_auto()` | Esegui trace automatica |

Questi endpoint sono consumati dall'interfaccia Streamlit in `pages/Tezos.py`.
