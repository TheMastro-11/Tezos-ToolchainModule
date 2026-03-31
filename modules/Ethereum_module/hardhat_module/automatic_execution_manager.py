import json
import os
import streamlit as st
import time
from contextlib import nullcontext

from Ethereum_module.hardhat_module.contract_utils import (
    get_deployment_info,
    load_wallet_from_file,
    create_web3_instance,
    build_function_call_data,
    fetch_contract_context,
    get_default_network
)
from Ethereum_module.hardhat_module.meta_transaction import metaTransaction
from Ethereum_module.hardhat_module.compiler_and_deployer import automatic_compile_and_deploy_contracts
from Ethereum_module.ethereum_utils import ethereum_base_path, hardhat_base_path ,read_json , \
bind_actors , build_complete_dict , set_guidance_parameters
from Ethereum_module.interactive_interface import get_function_guidance

from Ethereum_module.streamlit_constructor_interface import automatic_constructor_collector
from eth_account import Account
import traceback



contracts_path = os.path.join(hardhat_base_path, "contracts")
traces_path = os.path.join(hardhat_base_path, "execution_traces")
def get_execution_traces():
    """Get list of available execution traces."""
   
    if not os.path.exists(traces_path):
        return []
    
    traces = []
    for file in os.listdir(traces_path):
        if file.endswith('.json'):
            traces.append(file)
    return traces

#def exec_contract_automatically(contract_deployment_id, 
#                        ):

def exec_contract_automatically(contract_deployment_id, trace_data=None,
                                execute_deploy=True, execute_compile=True,
                                initial_balance=None, phase_statuses=None,
                                network_override=None):

    # Use global default network if none specified
    #address_inputs questi sono gli indirizzi da sostituire nei parametri di tipo address , da aggiungere
    address_inputs = []

    if trace_data is not None:
        json_file = trace_data
    else:
        contract_file = contract_deployment_id + ".json"
        json_file = read_json(f"{traces_path}/{contract_file}")
        if json_file is None:
            st.error(f" Failed to read trace file: {contract_file}")
            return

    # Get network configuration — network_override from UI takes priority over trace JSON
    _trace_network = json_file.get("configuration", {}).get("evm", {}).get("network", get_default_network())
    network = network_override if network_override else _trace_network
    contract_name = json_file.get("trace_title", "") + ".sol"
    actors_dict = bind_actors(contract_deployment_id, trace_data=json_file)
    if not actors_dict:
        st.error(" Failed to bind actors to wallets")
        return {
            "success": False,
            "error": "Failed to bind actors to wallets",
            "results": []
        }

    # Get all trace execution steps
    trace_executions = json_file.get("trace_execution", [])

    # Rosetta traces use "evm" as the config key; standalone traces may use "ethereum"
    deploy_config = (
        json_file.get("configuration", {}).get("evm", {}).get("deploy_config")
        or json_file.get("configuration", {}).get("ethereum", {}).get("deploy_config")
        or {}
    )

    # Store results for all function executions
    all_results = []

    # Resolve phase status containers (may be None → nullcontext)
    _deploy_ctx = (phase_statuses or {}).get("deploy")
    _execute_ctx = (phase_statuses or {}).get("execute")

    # Phase tracking — populated in every branch, included in the return dict
    _deploy_phase = None
    _execute_phase = None
    contract_address = None

    #section for automatic deployment
    try:
        if execute_deploy:
            settings = deploy_config.get("settings", {})

            # sender_wallet: from deploy_config > first trace actor > first actor in binding
            sender_wallet_name = (
                settings.get("sender_wallet")
                or (json_file.get("trace_actors") or [None])[0]
                or next(iter(actors_dict), None)
            )
            sender_wallet = actors_dict.get(sender_wallet_name) or next(iter(actors_dict.values()), None)

            if sender_wallet is None:
                raise ValueError("No sender wallet available for deployment — check actor binding.")

            # initial_balance overrides value_in_ether when explicitly provided
            value_in_ether = (
                initial_balance if initial_balance is not None
                else settings.get("value_in_ether", 0)
            )
            constr_dict = actors_dict | deploy_config

            with (_deploy_ctx if _deploy_ctx else nullcontext()):
                automatic_compile_and_deploy_contracts(sender_wallet, network, True, contract_name, constr_dict, value_in_ether)
            if _deploy_ctx:
                _deploy_ctx.update(label="✅ Deploy completato", state="complete", expanded=False)
            _deploy_phase = {"status": "success", "details": "Contract deployed."}

        elif not execute_deploy:
            if _deploy_ctx:
                _deploy_ctx.update(label="⏭️ Deploy saltato", state="complete", expanded=False)
            st.info("ℹ️ Deployment skipped (Deploy before execution is disabled).")
            _deploy_phase = {"status": "skipped", "details": "Deploy disabled."}
        else:
            if _deploy_ctx:
                _deploy_ctx.update(label="⏭️ Nessuna configurazione deploy", state="complete", expanded=False)
            st.info("ℹ No deployment configuration found, skipping deployment step.")
            _deploy_phase = {"status": "skipped", "details": "No deploy configuration found."}

    except Exception as e:
        if _deploy_ctx:
            _deploy_ctx.update(label="❌ Deploy fallito", state="error", expanded=True)
        st.info(f" Error automatically deploying the contract: {str(e)}")
        _deploy_phase = {"status": "error", "details": f"Deploy failed: {str(e)}"}

    try:
        # Get deployment info (common for all functions)
        deployment_info = get_deployment_info(contract_deployment_id)
        contract_address = deployment_info['address']
        abi = deployment_info['abi']
        
        # Create Web3 instance (common for all functions)
        w3 = create_web3_instance(network)
        if not w3.is_connected():
            raise ValueError(f"Could not connect to network: {network}")
        
        # Create contract instance (common for all functions)
        contract = w3.eth.contract(address=contract_address, abi=abi)
        

        
        
        
        # Execute each function in the trace
        with (_execute_ctx if _execute_ctx else nullcontext()):
            for i, execution_step in enumerate(trace_executions):
                # Support Rosetta multi-chain format (platform_specs.evm) and
                # standalone EVM format (direct "ethereum" key)
                evm_spec = execution_step.get("platform_specs", {}).get("evm")
                if evm_spec is None and not execution_step.get("ethereum"):
                    continue  # skip steps with no EVM config at all

                st.info(f" Executing step {i+1}/{len(trace_executions)}: {execution_step['function_name']}")
                if execution_step.get("waiting_time", 0) > 0:
                    wait_time = execution_step.get("waiting_time", 0)
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for j in range(wait_time):
                        progress = (j + 1) / wait_time
                        progress_bar.progress(progress)
                        status_text.info(f"Waiting... {wait_time - j}s remaining")
                        time.sleep(1)

                    progress_bar.empty()
                    status_text.empty()
                try:
                    # Get function name and parameters
                    function_name = execution_step["function_name"]

                    # Build step-specific complete_dict
                    step_complete_dict = {}

                    # Args dal livello superiore (condivisi tra chain)
                    if "args" in execution_step:
                        step_complete_dict.update(execution_step["args"])

                    # Config EVM: Rosetta format (platform_specs.evm) con
                    # fallback al formato standalone (chiave "ethereum" diretta)
                    evm_config = evm_spec if evm_spec else execution_step.get("ethereum", {})
                    step_complete_dict.update(evm_config)

                    # Default sender_wallet → primo attore del passo se non esplicitato
                    if "sender_wallet" not in step_complete_dict:
                        actors = execution_step.get("actors", [])
                        if actors:
                            step_complete_dict["sender_wallet"] = actors[0]

                    # Default eth_value → campo "value" del passo se non esplicitato
                    if "eth_value" not in step_complete_dict and "value" in execution_step:
                        step_complete_dict["eth_value"] = execution_step["value"]

                    # Get sender wallet actor name for this step
                    sender_wallet_actor = step_complete_dict.get("sender_wallet", None)
                    if sender_wallet_actor is None:
                        st.error(f"❌ sender_wallet not specified for step {i+1} — execution stopped")
                        all_results.append({
                            "step": i+1,
                            "function_name": function_name,
                            "success": False,
                            "error": "sender_wallet not specified in execution step"
                        })
                        break

                    # Resolve actor name to actual wallet file
                    actual_wallet_file = actors_dict.get(sender_wallet_actor, None)
                    if actual_wallet_file is None:
                        st.error(f"❌ Actor '{sender_wallet_actor}' not found in binding — execution stopped")
                        all_results.append({
                            "step": i+1,
                            "function_name": function_name,
                            "success": False,
                            "error": f"Actor '{sender_wallet_actor}' not found in actor binding"
                        })
                        break

                    # Load wallet for this step
                    wallet_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ethereum_wallets", actual_wallet_file)
                    wallet_data = load_wallet_from_file(wallet_path)
                    if not wallet_data:
                        st.error(f"❌ Could not load wallet: {actual_wallet_file} — execution stopped")
                        all_results.append({
                            "step": i+1,
                            "function_name": function_name,
                            "success": False,
                            "error": f"Could not load wallet file: {actual_wallet_file}"
                        })
                        break

                    # Get function guidance and parameters
                    guidance = get_function_guidance(contract_deployment_id, function_name)
                    param_values = set_guidance_parameters(guidance, step_complete_dict)
                    if param_values is None:
                        missing = [
                            p["name"] for p in guidance.get("parameters", [])
                            if p.get("type") != "address" and p["name"] not in step_complete_dict
                        ]
                        st.error(f"❌ Step {i+1} ({function_name}): missing parameters: {missing} — execution stopped")
                        all_results.append({
                            "step": i+1,
                            "function_name": function_name,
                            "success": False,
                            "error": f"Missing required parameters: {missing}"
                        })
                        break

                    # Build function call arguments
                    call_args = build_function_call_data(contract_deployment_id, function_name, param_values, address_inputs)

                    # Get function context
                    ctx = fetch_contract_context(contract_deployment_id, function_name)

                    # Create account from private key
                    account = Account.from_key(wallet_data["private_key"])

                    # Resolve actor name for this step
                    step_actor = execution_step.get("actors", [sender_wallet_actor])[0] if execution_step.get("actors") else sender_wallet_actor

                    if ctx['is_view']:
                        # Call view function (no transaction)
                        try:
                            result = getattr(contract.functions, function_name)(*call_args).call()
                            step_result = {
                                "step": i+1,
                                "function_name": function_name,
                                "actor": step_actor,
                                "success": True,
                                "return_value": str(result),
                                "transaction_hash": "",
                                "gas_used": 0,
                                "size_in_bytes": 0
                            }
                            all_results.append(step_result)
                            st.success(f"✅ Step {i+1} completed - View function result: {result}")

                        except Exception as e:
                            step_result = {
                                "step": i+1,
                                "function_name": function_name,
                                "actor": step_actor,
                                "success": False,
                                "error": f"View function call failed: {str(e)}",
                                "transaction_hash": "",
                                "gas_used": 0,
                                "size_in_bytes": 0
                            }
                            all_results.append(step_result)
                            st.error(f"❌ Step {i+1} failed - View function error: {str(e)}")

                    else:
                        # Send transaction
                        try:
                            # Get ETH value for this step
                            value_eth = step_complete_dict.get("eth_value", 0)
                            value_wei = w3.to_wei(float(value_eth), 'ether') if value_eth else 0

                            # Use metaTransaction function (blocks until receipt confirmed)
                            receipt = metaTransaction(w3, account, contract, value_wei, function_name, *call_args)

                            step_result = {
                                "step": i+1,
                                "function_name": function_name,
                                "actor": step_actor,
                                "success": True,
                                "transaction_hash": receipt['transactionHash'].hex(),
                                "gas_used": receipt.get('gasUsed', 0),
                                "size_in_bytes": receipt.get('size_in_bytes', 0)
                            }
                            all_results.append(step_result)
                            st.success(f"✅ Step {i+1} completed - Transaction: {receipt['transactionHash'].hex()}")

                        except Exception as e:
                            step_result = {
                                "step": i+1,
                                "function_name": function_name,
                                "actor": step_actor,
                                "success": False,
                                "error": f"Transaction failed: {str(e)}",
                                "transaction_hash": "",
                                "gas_used": 0,
                                "size_in_bytes": 0
                            }
                            all_results.append(step_result)
                            st.error(f"❌ Step {i+1} failed - Transaction error: {str(e)}")

                    # Stop the sequence if this step failed
                    if not step_result.get("success", True):
                        st.warning(f"⛔ Execution halted at step {i+1} — subsequent steps skipped")
                        break

                except Exception as e:
                    # Try to get actor and wallet info if they were defined
                    try:
                        actor_info = {
                            "sender_actor": sender_wallet_actor,
                            "sender_wallet": actual_wallet_file
                        }
                    except NameError:
                        # Variables not yet defined in this step
                        evm_fb = execution_step.get("platform_specs", {}).get("evm") or execution_step.get("ethereum", {})
                        actor_info = {
                            "sender_actor": evm_fb.get("sender_wallet", "unknown"),
                            "sender_wallet": "not_resolved"
                        }

                    step_result = {
                        "step": i+1,
                        "function_name": execution_step.get("function_name", "unknown"),
                        "success": False,
                        "error": f"Step execution failed: {str(e)}",
                        **actor_info
                    }
                    all_results.append(step_result)
                    st.error(f"❌ Step {i+1} failed - General error: {str(e)}")
                    st.warning(f"⛔ Execution halted at step {i+1} — subsequent steps skipped")
                    break
        
        if _execute_ctx:
            _execute_ctx.update(label="✅ Esecuzione completata", state="complete", expanded=False)
        _execute_phase = {"status": "success", "details": f"Executed {len(all_results)} steps."}

        # --- Build Tezos-compatible output format ---
        trace_title = json_file.get("trace_title", contract_deployment_id)

        # Aggregate costs per actor
        actor_costs = {}
        for step in all_results:
            actor = step.get("actor", "unknown")
            gas = step.get("gas_used", 0) if step.get("success", False) else 0
            size = step.get("size_in_bytes", 0) if step.get("success", False) else 0
            if actor not in actor_costs:
                actor_costs[actor] = {"total_cost": 0, "miner_fee": 0, "chain_fee": 0}
            actor_costs[actor]["total_cost"] += gas
            actor_costs[actor]["miner_fee"] += gas

        # Total costs
        total_gas = sum(s.get("gas_used", 0) for s in all_results if s.get("success", False))
        total_weight = sum(s.get("size_in_bytes", 0) for s in all_results if s.get("success", False))

        # Per-step costs (Tezos format)
        trace_execution_costs = {}
        for step in all_results:
            seq_id = str(step.get("step", ""))
            gas = step.get("gas_used", 0) if step.get("success", False) else 0
            trace_execution_costs[seq_id] = {
                "function_name": step.get("function_name", ""),
                "actor": step.get("actor", ""),
                "total_cost": gas,
                "miner_fee": gas,
                "chain_fee": 0,
                "weight": step.get("size_in_bytes", 0),
                "hash": step.get("transaction_hash", ""),
                "block_delay": 0,
                "success": step.get("success", False),
            }
            if not step.get("success", False) and step.get("error"):
                trace_execution_costs[seq_id]["error"] = step.get("error", "")

        output_json = {
            "trace_title": trace_title,
            "trace_actors_costs": actor_costs,
            "total_sequence_execution_costs": {
                "total_cost": total_gas,
                "miner_fee": total_gas,
                "chain_fee": 0,
                "weight": total_weight,
                "average_block_delay": 0.0,
            },
            "trace_execution_costs": trace_execution_costs,
        }

        # Internal return dict keeps extra fields needed by the UI
        final_results = {
            "network": network,
            "success": True,
            "platform": "Ethereum",
            "trace_title": trace_title,
            "contract_address": contract_address,
            "phases": {
                "deploy": _deploy_phase,
                "execute": _execute_phase,
            },
            "results": all_results,
            "output": output_json,
        }

        # Save Tezos-compatible JSON to trace_results/
        result_filename = f"{contract_deployment_id}_result.json"
        trace_results_dir = os.path.join(hardhat_base_path, "trace_results")
        os.makedirs(trace_results_dir, exist_ok=True)
        result_filepath = os.path.join(trace_results_dir, result_filename)

        try:
            with open(result_filepath, 'w', encoding='utf-8') as f:
                json.dump(output_json, f, indent=2, ensure_ascii=False)

            st.success(f"✅ Results saved to: {result_filename}")

            with open(result_filepath, 'r', encoding='utf-8') as f:
                json_data = f.read()

            st.download_button(
                label=" Download Results JSON",
                data=json_data,
                file_name=result_filename,
                mime="application/json",
                help=f"Download the execution results as {result_filename}"
            )

        except Exception as e:
            st.warning(f" Could not save results file: {str(e)}")

        return final_results
                
    except Exception as e:
        if _execute_ctx:
            _execute_ctx.update(label="❌ Esecuzione fallita", state="error", expanded=True)
        _execute_phase = {"status": "error", "details": f"Execution failed: {str(e)}"}
        # Prepare error results
        st.error(f" Execution failed: {str(e)}")
        st.error(traceback.format_exc())
        _execute_phase = {"status": "error", "details": f"Execution failed: {str(e)}"}

        # Build partial Tezos-compatible output for error case
        trace_title = json_file.get("trace_title", contract_deployment_id) if 'json_file' in locals() else contract_deployment_id
        actor_costs_err = {}
        trace_execution_costs_err = {}
        for step in all_results:
            actor = step.get("actor", "unknown")
            if actor not in actor_costs_err:
                actor_costs_err[actor] = {"total_cost": 0, "miner_fee": 0, "chain_fee": 0}
            seq_id = str(step.get("step", ""))
            trace_execution_costs_err[seq_id] = {
                "function_name": step.get("function_name", ""),
                "actor": actor,
                "total_cost": step.get("gas_used", 0),
                "miner_fee": step.get("gas_used", 0),
                "chain_fee": 0,
                "weight": step.get("size_in_bytes", 0),
                "hash": step.get("transaction_hash", ""),
                "block_delay": 0,
                "success": step.get("success", False),
                "error": step.get("error", ""),
            }

        output_json_err = {
            "trace_title": trace_title,
            "trace_actors_costs": actor_costs_err,
            "total_sequence_execution_costs": {
                "total_cost": 0, "miner_fee": 0, "chain_fee": 0,
                "weight": 0, "average_block_delay": 0.0,
            },
            "trace_execution_costs": trace_execution_costs_err,
            "error": str(e),
        }

        error_results = {
            "network": network if 'network' in locals() else "unknown",
            "success": False,
            "platform": "Ethereum",
            "trace_title": trace_title,
            "contract_address": contract_address,
            "phases": {
                "deploy": _deploy_phase,
                "execute": _execute_phase,
            },
            "error": f"Global execution failed: {str(e)}",
            "results": all_results,
            "output": output_json_err,
        }

        # Save partial results to trace_results/
        result_filename = f"{contract_deployment_id}_result.json"
        trace_results_dir = os.path.join(hardhat_base_path, "trace_results")
        os.makedirs(trace_results_dir, exist_ok=True)
        result_filepath = os.path.join(trace_results_dir, result_filename)
        try:
            with open(result_filepath, 'w', encoding='utf-8') as f:
                json.dump(output_json_err, f, indent=2, ensure_ascii=False)
            st.error(f"❌ Execution failed but partial results saved to: {result_filename}")
            with open(result_filepath, 'r', encoding='utf-8') as f:
                json_data = f.read()
            st.download_button(
                label=" Download Partial Results JSON",
                data=json_data,
                file_name=result_filename,
                mime="application/json",
                help=f"Download the partial execution results as {result_filename}"
            )
        except Exception as save_error:
            st.warning(f" Could not save error results file: {str(save_error)}")
        return error_results

def find_execution_traces():
    """Compatibility function - alias for get_execution_traces()"""
    return get_execution_traces()

# Main streamlit app
if __name__ == "__main__":
    streamlit_execution_interface()
