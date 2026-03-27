# Tezos interface per Flask backend - Bridge functions

import os
import json

from .tezos_utils import (
    get_available_contracts,
    compile_tezos_contract,
    deploy_tezos_contract,
    get_deployed_contracts,
    get_contract_entrypoints,
    call_contract_entrypoint,
    save_contract_file,
    is_tezos_available,
    tezos_base_path,
    _get_addresses,
)


def compile_and_deploy_tezos_contracts(contract_name=None, deploy=False, initial_balance=0):
    """
    Compila e opzionalmente deploya contratti Tezos.
    Usa il pattern simile a Ethereum per consistenza UI.
    """
    results = []
    
    if not is_tezos_available():
        return {"success": False, "error": "Tezos modules not available", "contracts": []}
    
    # Se non specificato, prendi tutti i contratti
    if contract_name is None:
        contracts = get_available_contracts()
    else:
        contracts = [contract_name] if contract_name in get_available_contracts() else []
    
    if not contracts:
        error_msg = f"Contract '{contract_name}' not found" if contract_name else "No contracts found"
        return {"success": False, "error": error_msg, "contracts": []}
    
    for contract in contracts:
        contract_result = {
            "contract": contract,
            "compiled": False,
            "deployed": False,
            "contract_address": None,
            "transaction_hash": None,
            "errors": []
        }
        
        try:
            # STEP 1: Compilazione
            compile_result = compile_tezos_contract(contract)
            contract_result["compiled"] = compile_result["success"]
            
            if not compile_result["success"]:
                contract_result["errors"].append(compile_result["error"])
                results.append(contract_result)
                continue
            
            # STEP 2: Deploy (se richiesto)
            if deploy:
                deploy_result = deploy_tezos_contract(contract, initial_balance)
                contract_result["deployed"] = deploy_result["success"]
                
                if deploy_result["success"]:
                    contract_result["contract_address"] = deploy_result["contract_address"]
                    contract_result["transaction_hash"] = deploy_result["transaction_hash"]
                else:
                    contract_result["errors"].append(deploy_result["error"])
                    
        except Exception as e:
            contract_result["errors"].append(str(e))
        
        results.append(contract_result)
    
    return {"success": True, "contracts": results}


def fetch_tezos_contracts():
    """Ottiene lista contratti deployati per UI."""
    if not is_tezos_available():
        return []
    return get_deployed_contracts()


def fetch_tezos_entrypoints(contract_name):
    """Ottiene entrypoints per un contratto specifico."""
    if not is_tezos_available():
        return []
    return get_contract_entrypoints(contract_name)


def fetch_tezos_contract_context(contract_name, entrypoint_name):
    """
    Ottiene informazioni su un entrypoint specifico.
    Per ora ritorna struttura base, può essere espansa analizzando il contratto.
    """
    return {
        "contract": contract_name,
        "entrypoint": entrypoint_name,
        "parameters_schema": "dynamic",  # Da implementare analisi schema
        "is_payable": True  # Tezos supporta sempre invio XTZ
    }


def interact_with_tezos_contract(contract_name, entrypoint_name, parameters, tez_amount):
    """
    Interagisce con un contratto Tezos deployato.
    """
    if not is_tezos_available():
        return {"success": False, "error": "Tezos modules not available"}
    
    try:
        # Prepara parametri se forniti
        processed_params = None
        if parameters and parameters.strip():
            # Se contiene virgole, split in lista
            if "," in parameters:
                processed_params = [p.strip() for p in parameters.split(",")]
            else:
                processed_params = [parameters.strip()]
        
        # Chiama l'entrypoint usando le funzioni esistenti
        result = call_contract_entrypoint(
            contract_name=contract_name,
            entrypoint_name=entrypoint_name,
            parameters=processed_params,
            tez_amount=tez_amount
        )
        
        return result
        
    except Exception as e:
        return {"success": False, "error": f"Interaction error: {str(e)}"}


def upload_tezos_contract(contract_name, contract_content):
    """Upload di un nuovo contratto SmartPy."""
    if not is_tezos_available():
        return {"success": False, "error": "Tezos modules not available"}

    return save_contract_file(contract_name, contract_content)


def get_tezos_json_traces():
    """Returns list of available Rosetta JSON trace files for Tezos."""
    traces_dir = os.path.join(tezos_base_path, "tezos_module", "execution_traces")
    if not os.path.exists(traces_dir):
        return []
    return [f for f in os.listdir(traces_dir) if f.endswith(".json")]


def execute_tezos_trace(trace_file_name):
    """
    Execute a Rosetta JSON trace on Tezos.

    The trace must have configuration.tezos.use == "True".
    Each execution step with tezos.send_transaction == true will be executed.
    The step's function_name is used as the entrypoint name.
    args.contract_instance identifies the deployed contract.
    tez_amount is read from tezos.tez_amount or parsed from args._amount (mutez format).
    """
    if not is_tezos_available():
        return {"success": False, "error": "Tezos modules not available"}

    traces_dir = os.path.join(tezos_base_path, "tezos_module", "execution_traces")
    trace_file_path = os.path.join(traces_dir, trace_file_name)

    if not os.path.exists(trace_file_path):
        return {"success": False, "error": f"Trace file not found: {trace_file_name}"}

    with open(trace_file_path, "r", encoding="utf-8") as f:
        trace_data = json.load(f)

    tezos_config = trace_data.get("configuration", {}).get("tezos", {})
    if str(tezos_config.get("use", "False")).lower() != "true":
        return {"success": False, "error": "Tezos not enabled in this trace (configuration.tezos.use must be 'True')"}

    try:
        addresses = _get_addresses()
    except Exception as e:
        return {"success": False, "error": f"Could not read deployed contracts: {e}"}

    results = []
    for step in trace_data.get("trace_execution", []):
        step_tezos = step.get("tezos", {})
        if not step_tezos.get("send_transaction", False):
            results.append({
                "sequence_id": step.get("sequence_id"),
                "function_name": step.get("function_name"),
                "skipped": True,
            })
            continue

        function_name = step.get("function_name")
        args = step.get("args", {})
        contract_instance = args.get("contract_instance")

        if not contract_instance:
            results.append({
                "sequence_id": step.get("sequence_id"),
                "function_name": function_name,
                "success": False,
                "error": "args.contract_instance not specified",
            })
            continue

        if contract_instance not in addresses:
            results.append({
                "sequence_id": step.get("sequence_id"),
                "function_name": function_name,
                "success": False,
                "error": f"Contract '{contract_instance}' not found in deployed contracts",
            })
            continue

        # Parse tez amount
        tez_amount = float(step_tezos.get("tez_amount", 0))
        if tez_amount == 0 and "_amount" in args:
            amount_str = str(args["_amount"])
            if "mutez(" in amount_str:
                try:
                    mutez_val = int(amount_str.replace("mutez(", "").replace(")", "").strip())
                    tez_amount = mutez_val / 1_000_000
                except ValueError:
                    pass

        # Build parameters list (exclude special fields)
        explicit_params = step_tezos.get("parameters", None)
        if explicit_params is not None:
            parameters = explicit_params if isinstance(explicit_params, list) else [explicit_params]
        else:
            param_args = {k: v for k, v in args.items() if k not in ("contract_instance", "_amount")}
            parameters = [f"{k}={v}" for k, v in param_args.items()] if param_args else []

        result = call_contract_entrypoint(
            contract_name=contract_instance,
            entrypoint_name=function_name,
            parameters=parameters,
            tez_amount=tez_amount,
        )

        results.append({
            "sequence_id": step.get("sequence_id"),
            "function_name": function_name,
            **result,
        })

    return {
        "success": True,
        "trace_title": trace_data.get("trace_title"),
        "results": results,
    }