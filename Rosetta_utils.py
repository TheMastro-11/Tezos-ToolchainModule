import os
import sys
import re
import asyncio
import json
import threading
from io import StringIO
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

_base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_base_dir, "modules"))
sys.path.append(os.path.join(_base_dir, "modules", "Solana_module"))

_toolchain_dir = os.path.join(_base_dir, "modules", "Tezos_module", "toolchain")
if _toolchain_dir not in sys.path:
    sys.path.insert(0, _toolchain_dir)

_eth_modules_dir = os.path.join(_base_dir, "modules")
if _eth_modules_dir not in sys.path:
    sys.path.insert(0, _eth_modules_dir)

import streamlit as st
import pandas as pd
from solders.pubkey import Pubkey
from anchorpy import Wallet, Provider
from jsonUtils import jsonReaderByContract
from main import resolveTraceContractCandidates
from trace_utils import (
    get_client,
    get_trace_report_state,
    get_last_trace_setup,
    save_trace_report,
    save_trace_setup_config,
    render_trace_report,
    render_trace_selection_summary,
    render_live_trace_progress,
    update_live_trace_progress,
    run_trace_with_report,
    summarize_trace_payload,
    queue_trace_view,
)

from Cardano_module.cardano_module.cardano_utils import cardano_base_path
from Solana_module.solana_module.anchor_module.anchor_utils import anchor_base_path

try:
    from Ethereum_module.hardhat_module.automatic_execution_manager import exec_contract_automatically
    _evm_available = True
except ImportError:
    _evm_available = False


def render_evm_trace_results():
    """Render EVM execution results stored in session state."""
    evm_results = st.session_state.get("evm_trace_results", [])
    if not evm_results:
        return

    hcol1, hcol2 = st.columns([5, 1])
    with hcol1:
        st.subheader("⚡ Ethereum (EVM) Execution Report")
    with hcol2:
        if st.button("🗑️ Clear EVM", use_container_width=True):
            st.session_state.pop("evm_trace_results", None)
            st.rerun()

    for entry in evm_results:
        trace_name = entry.get("trace_name", "Trace")
        result = entry.get("result", {})
        success = result.get("success", False)
        network = result.get("network", "unknown")
        steps = result.get("results", [])
        global_error = result.get("error")

        status_icon = "✅" if success else "❌"
        with st.container(border=True):
            tcol1, tcol2 = st.columns([4, 2])
            with tcol1:
                st.markdown(f"**{status_icon} {trace_name}**")
            with tcol2:
                st.caption(f"Network: `{network}`")

            if global_error:
                with st.expander("Global error", expanded=True):
                    st.code(global_error, language="text")

            if steps:
                # Metrics row
                total = len(steps)
                passed = sum(1 for s in steps if s.get("success", False))
                failed = total - passed
                total_gas = sum(s.get("gas_used", 0) or 0 for s in steps)
                mc = st.columns(3)
                mc[0].metric("Steps", total)
                mc[1].metric("✅ Passed", passed)
                mc[2].metric("❌ Failed", failed)

                # Steps table
                rows = []
                for s in steps:
                    rows.append({
                        "Step": s.get("step", "-"),
                        "Function": s.get("function_name", "-"),
                        "Status": "✅ OK" if s.get("success", False) else "❌ Fail",
                        "Tx Hash": (s.get("transaction_hash", "") or "")[:20] + "…"
                                   if s.get("transaction_hash") else s.get("return_value", "-"),
                        "Gas": s.get("gas_used", "-"),
                        "Error": s.get("error", ""),
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)

                # Per-step detail in expanders
                failed_steps = [s for s in steps if not s.get("success", False)]
                if failed_steps:
                    with st.expander(f"Failed step details ({len(failed_steps)})", expanded=True):
                        for s in failed_steps:
                            st.error(
                                f"**Step {s.get('step')} — {s.get('function_name')}**: {s.get('error', 'unknown error')}"
                            )
            else:
                st.info("No step results recorded.")


def upload_trace_file():
    """UI component for uploading execution trace files via drag & drop."""
    
    st.subheader(" Upload Execution Trace")
    
    uploaded_file = st.file_uploader(
        "Drag and drop your execution trace JSON file here",
        type=['json'],
        help="Upload a JSON file containing the execution trace"
    )
    
    if uploaded_file is not None:
        try:
            # Read and validate JSON
            file_content = uploaded_file.read()
            json_data = json.loads(file_content)
            
            # Validate required fields
            required_fields = ["trace_title", "trace_execution"]
            missing_fields = [field for field in required_fields if field not in json_data]
            
            if missing_fields:
                st.error(f" Invalid trace file. Missing required fields: {', '.join(missing_fields)}")
                return
            config_list = []

            for configuration in json_data['configuration']:
                
                use = json_data['configuration'][configuration].get("use", "False")

                if use.lower() == 'true':
                    config_list.append(configuration.lower())


            if "solana" in config_list :
                # Save to execution_traces folder
                traces_folder = f"{anchor_base_path}/execution_traces/"
                os.makedirs(traces_folder, exist_ok=True)

                file_path = os.path.join(traces_folder, uploaded_file.name)

                # Save the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2)

            if "tezos" in config_list :
                traces_folder = os.path.join(_base_dir, "rosetta_traces")
                os.makedirs(traces_folder, exist_ok=True)
                file_path = os.path.join(traces_folder, uploaded_file.name)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2)

            if "cardano" in config_list :
                # Save to execution_traces folder
                traces_folder = f"{cardano_base_path}/execution_traces/"
                os.makedirs(traces_folder, exist_ok=True)

                file_path = os.path.join(traces_folder, uploaded_file.name)

                # Save the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2)
            if "evm" in config_list :
                traces_folder = os.path.join(_base_dir, "modules", "Ethereum_module", "hardhat_module", "execution_traces")
                os.makedirs(traces_folder, exist_ok=True)
                file_path = os.path.join(traces_folder, uploaded_file.name)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2)
               
            st.info(f" Saved to: `execution_traces/{uploaded_file.name}`")
            st.success(f" Trace file `{uploaded_file.name}` uploaded successfully , you can find and choose the list of toolchains below:")
            showLinks(config_list)
            
                
        except json.JSONDecodeError:
            st.error("❌ Invalid JSON file. Please upload a valid JSON trace file.")
        except Exception as e:
            st.error(f"❌ Error uploading file: {str(e)}")

def select_trace_file():
    """Full trace execution UI mirroring dapp.py trace_view, using the shared rosetta_traces/ folder."""
    traces_root = os.path.join(_base_dir, "rosetta_traces")

    # View mode toggle (Execution Setup / Trace Report)
    pending_trace_view = st.session_state.pop("trace_view_page_target", None)
    if pending_trace_view in {"Execution Setup", "Trace Report"}:
        st.session_state["trace_view_page"] = pending_trace_view
    view_mode = st.radio("View", options=["Execution Setup", "Trace Report"],
                         horizontal=True, key="trace_view_page")
    if view_mode == "Trace Report":
        render_trace_report()
        render_evm_trace_results()
        return

    report = get_trace_report_state()
    evm_report = st.session_state.get("evm_trace_results")
    if report or evm_report:
        parts = []
        if report:
            parts.append("Tezos trace report")
        if evm_report:
            parts.append("EVM execution report")
        st.caption(f"{' and '.join(parts)} available in the Trace Report view.")

    try:
        traces_by_contract = jsonReaderByContract(traceRoot=traces_root)
    except Exception as e:
        st.error(f"Error loading traces: {e}")
        return

    if not traces_by_contract:
        st.warning("No traces found in `rosetta_traces/`.")
        return

    contract_names = list(traces_by_contract.keys())
    last_setup = get_last_trace_setup()

    default_contract_index = 0
    if last_setup and last_setup.get("selected_contract") in contract_names:
        default_contract_index = contract_names.index(last_setup["selected_contract"])

    selected_contract = st.selectbox(
        "Select a contract:", options=contract_names,
        index=default_contract_index, key="rosetta_contract_select"
    )
    contract_traces = traces_by_contract[selected_contract]
    trace_names = list(contract_traces.keys())
    if not trace_names:
        st.warning(f"No traces found for '{selected_contract}'.")
        return

    # --- Execution mode + trace selection ---
    execution_mode_options = ["Single trace"]
    if selected_contract != "Ungrouped":
        execution_mode_options.append("All traces in contract")

    default_exec_mode_index = 0
    if last_setup and last_setup.get("selected_contract") == selected_contract:
        if last_setup.get("execution_mode") in execution_mode_options:
            default_exec_mode_index = execution_mode_options.index(last_setup["execution_mode"])
    execution_mode = st.radio(
        "Execution mode", options=execution_mode_options,
        index=default_exec_mode_index, horizontal=True, key="rosetta_exec_mode"
    )

    selected_trace = None
    if execution_mode == "Single trace":
        default_trace_index = 0
        if (last_setup and last_setup.get("selected_contract") == selected_contract
                and last_setup.get("selected_trace") in trace_names):
            default_trace_index = trace_names.index(last_setup["selected_trace"])
        selected_trace = st.selectbox(
            "Trace to execute", options=trace_names,
            index=default_trace_index, key="rosetta_trace_select"
        )

    # --- Toolchain map (used later) ---
    preview_data = (contract_traces[selected_trace] if selected_trace
                    else next(iter(contract_traces.values())))
    config_list = [
        k.lower() for k, v in preview_data.get("configuration", {}).items()
        if v.get("use", "false").lower() == "true"
    ]

    _toolchain_label_map = {
        "tezos":   "🔷 Tezos",
        "solana":  "🌞 Solana",
        "evm":     "⚡ Ethereum (EVM)",
        "cardano": "🧩 Cardano",
    }
    toolchain_options = [_toolchain_label_map.get(k, k.title()) for k in config_list]

    # Compute keys after multiselect (rendered later); default all selected
    selected_toolchain_labels = st.session_state.get(
        f"rosetta_toolchain_select_{selected_contract}_{selected_trace}", toolchain_options
    )
    # Filter to valid options only (guards against stale session state)
    selected_toolchain_labels = [l for l in selected_toolchain_labels if l in toolchain_options]
    if not selected_toolchain_labels:
        selected_toolchain_labels = toolchain_options
    selected_toolchain_keys = [
        config_list[toolchain_options.index(lbl)] for lbl in selected_toolchain_labels
    ]
    tezos_selected = "tezos" in selected_toolchain_keys
    evm_selected = "evm" in selected_toolchain_keys and _evm_available

    wallet_selection = "admin"

    # --- Options (always visible) ---
    execute_deploy = False
    execute_compile = False
    execute_redeploy = False
    initial_balance = 1
    selected_trace_suite = None
    show_live_terminal_output = True

    with st.container(border=True):
        st.subheader("Options")
        option_left, option_right = st.columns([3, 2])
        with option_left:
            st.caption("Execution mode and trace are selected above.")
        with option_right:
            default_deploy = (last_setup.get("execute_deploy", False)
                              if last_setup and last_setup.get("selected_contract") == selected_contract
                              else False)
            execute_deploy = st.checkbox(
                "Deploy before execution", value=default_deploy,
                key=f"rosetta_execute_deploy_{selected_contract}_{execution_mode}"
            )

            any_executable_chain = tezos_selected or evm_selected

            if execute_deploy and any_executable_chain:
                # Contract suite selector — Tezos only
                if tezos_selected:
                    preview_trace_data = next(iter(contract_traces.values()))
                    try:
                        available_trace_contracts = resolveTraceContractCandidates(
                            selectedContract=selected_contract, traceData=preview_trace_data
                        )
                    except FileNotFoundError as e:
                        st.warning(f"⚠️ Cannot deploy: no contract source found for **{selected_contract}**. {e}")
                        execute_deploy = False
                        available_trace_contracts = {}

                    suite_options = [s for s in ["Legacy", "Rosetta"] if s in available_trace_contracts]
                    if suite_options:
                        default_suite_index = 0
                        if (last_setup and last_setup.get("selected_contract") == selected_contract
                                and last_setup.get("selected_trace_suite") in suite_options):
                            default_suite_index = suite_options.index(last_setup["selected_trace_suite"])
                        selected_trace_suite = st.radio(
                            "Contract suite", options=suite_options, horizontal=True,
                            index=default_suite_index,
                            key=f"rosetta_contract_variant_{selected_contract}_{execution_mode}"
                        )

                default_compile = (last_setup.get("execute_compile", False)
                                   if last_setup and last_setup.get("selected_contract") == selected_contract
                                   else False)
                execute_compile = st.checkbox(
                    "Compile before deploy", value=default_compile,
                    key=f"rosetta_execute_compile_{selected_contract}_{execution_mode}"
                )

                # Initial balance label — unit depends on active chains
                _balance_unit_map = {"tezos": "ꜩ", "evm": "ETH", "solana": "SOL", "cardano": "ADA"}
                active_units = [_balance_unit_map[k] for k in selected_toolchain_keys if k in _balance_unit_map]
                balance_label = (
                    f"Initial balance ({' / '.join(active_units)})" if active_units else "Initial balance"
                )

                default_balance = (last_setup.get("initial_balance", 1)
                                   if last_setup and last_setup.get("selected_contract") == selected_contract
                                   else 1)
                initial_balance = st.number_input(
                    balance_label, min_value=0, value=default_balance, step=1,
                    key=f"rosetta_initial_balance_{selected_contract}_{execution_mode}"
                )

                if execution_mode == "All traces in contract":
                    default_redeploy = (last_setup.get("execute_redeploy", False)
                                        if last_setup and last_setup.get("selected_contract") == selected_contract
                                        else False)
                    execute_redeploy = st.checkbox(
                        "Re-deploy before each trace", value=default_redeploy,
                        key=f"rosetta_execute_redeploy_{selected_contract}"
                    )

            default_show_live = (last_setup.get("show_live_terminal_output", True)
                                 if last_setup and last_setup.get("selected_contract") == selected_contract
                                 else True)
            show_live_terminal_output = st.checkbox(
                "Show live terminal output", value=default_show_live,
                key=f"rosetta_show_live_{selected_contract}_{execution_mode}"
            )

    selected_trace_names = (
        [selected_trace] if execution_mode == "Single trace" and selected_trace else trace_names
    )

    # --- Execution plan summary (Tezos only) ---
    if tezos_selected:
        render_trace_selection_summary(
            selected_contract=selected_contract, execution_mode=execution_mode,
            trace_names=selected_trace_names, execute_deploy=execute_deploy,
            execute_compile=execute_compile, execute_redeploy=execute_redeploy,
            initial_balance=initial_balance, selected_trace_suite=selected_trace_suite,
            show_live_terminal_output=show_live_terminal_output,
        )
        if execute_redeploy:
            st.info("The contract will be compiled and deployed again before each trace.")

    # --- Toolchains Available (multi-select) — shown last before execute ---
    with st.container(border=True):
        st.subheader("Toolchains Available")
        if toolchain_options:
            st.multiselect(
                "Select toolchains to run the test on:",
                options=toolchain_options,
                default=selected_toolchain_labels,
                key=f"rosetta_toolchain_select_{selected_contract}_{selected_trace}",
            )
        else:
            st.warning("No toolchain configured for this trace.")

    button_label = ("▶️ Execute selected trace" if execution_mode == "Single trace"
                    else "▶️ Execute all traces in contract")

    any_executable = tezos_selected or evm_selected
    if not any_executable and selected_toolchain_keys:
        st.info("ℹ️ Execution for the selected toolchain(s) is not yet integrated in Rosetta. "
                "Use the dedicated toolchain page instead.")

    if any_executable and st.button(button_label):
        save_trace_setup_config({
            "selected_contract": selected_contract, "execution_mode": execution_mode,
            "selected_trace": selected_trace, "execute_deploy": execute_deploy,
            "execute_compile": execute_compile, "execute_redeploy": execute_redeploy,
            "initial_balance": initial_balance, "selected_trace_suite": selected_trace_suite,
            "show_live_terminal_output": show_live_terminal_output,
        })

        # ── 1. Build chain list and column layout ──────────────────────────────────────────────
        _chain_labels = {"tezos": "🔷 Tezos", "evm": "⚡ Ethereum (EVM)"}
        chains_to_run = [k for k in ("tezos", "evm") if (tezos_selected if k == "tezos" else evm_selected)]
        n = len(chains_to_run)
        exec_cols = st.columns(n) if n > 1 else [st.container()]
        col_map = {key: col for key, col in zip(chains_to_run, exec_cols)}

        # ── 2 & 3. Chain execution (parallel when both selected) ────────────────────────────────

        ctx = get_script_run_ctx()

        def _exec_tezos():
            tezos_col = col_map["tezos"]

            client = get_client(wallet_selection)

            trace_title = f"Trace report for {selected_trace if execution_mode == 'Single trace' else selected_contract}"
            trace_report = {
                "title": trace_title,
                "status": "success",
                "summary": {
                    "executed_traces": len(selected_trace_names), "execution_mode": execution_mode,
                    "execute_deploy": execute_deploy, "selected_suite": selected_trace_suite,
                },
                "traces": [],
            }

            with tezos_col:
                st.subheader(_chain_labels["tezos"])
                (status_box, progress_bar, results_placeholder,
                 terminal_placeholders, metrics_placeholder) = render_live_trace_progress(
                    title=trace_title,
                    total_traces=len(selected_trace_names),
                    show_terminal_output=show_live_terminal_output,
                )

            completed_rows = []
            try:
                for index, trace_name in enumerate(selected_trace_names):
                    compile_before_trace = execute_compile if index == 0 else execute_redeploy
                    update_live_trace_progress(
                        status_box=status_box, progress_bar=progress_bar,
                        results_placeholder=results_placeholder, completed_items=completed_rows,
                        total_traces=len(selected_trace_names), current_trace=trace_name,
                        metrics_placeholder=metrics_placeholder,
                    )
                    with tezos_col:
                        trace_entry = run_trace_with_report(
                            client=client, selected_contract=selected_contract,
                            trace_name=trace_name, trace_data=contract_traces[trace_name],
                            execute_deploy=execute_deploy, execute_compile=execute_compile,
                            initial_balance=initial_balance, preferred_suite=selected_trace_suite,
                            compile_before_trace=compile_before_trace, deploy_before_trace=execute_deploy,
                            show_live_terminal_output=show_live_terminal_output,
                            phase_placeholders=terminal_placeholders,
                        )

                    trace_report["traces"].append(trace_entry)
                    es = summarize_trace_payload(
                        trace_entry.get("phases", {}).get("execute", {}).get("payload")
                    )
                    completed_rows.append({
                        "Trace": trace_name, "Status": trace_entry.get("status", "success"),
                        "Steps": es["steps"], "Total cost": es["total_cost"], "Gas": es["total_gas"],
                    })
                    update_live_trace_progress(
                        status_box=status_box, progress_bar=progress_bar,
                        results_placeholder=results_placeholder, completed_items=completed_rows,
                        total_traces=len(selected_trace_names), metrics_placeholder=metrics_placeholder,
                    )
                save_trace_report(trace_report)
            except Exception as e:
                trace_report["status"] = "error"
                trace_report["error"] = str(e)
                save_trace_report(trace_report)
                update_live_trace_progress(
                    status_box=status_box, progress_bar=progress_bar,
                    results_placeholder=results_placeholder, completed_items=completed_rows,
                    total_traces=len(selected_trace_names), has_error=True,
                    metrics_placeholder=metrics_placeholder,
                )

        def _exec_evm():
            evm_col = col_map["evm"]
            evm_collected = []

            # Pre-filter EVM-enabled traces
            evm_trace_list = [
                t for t in selected_trace_names
                if contract_traces[t].get("configuration", {}).get("evm", {}).get("use", "false").lower() == "true"
            ]

            with evm_col:
                st.subheader(_chain_labels["evm"])
                evm_progress = st.progress(0.0)
                evm_caption = st.empty()

            try:
                for evm_idx, trace_name in enumerate(evm_trace_list):
                    trace_data = contract_traces[trace_name]
                    contract_deployment_id = trace_data.get("trace_title", selected_contract).lower()

                    with evm_col:
                        evm_caption.caption(
                            f"⏳ Traccia corrente: `{trace_name}` ({evm_idx + 1}/{len(evm_trace_list)})"
                        )
                        deploy_phase_status = (
                            st.status(f"🔄 Deploy — `{trace_name}`", expanded=True)
                            if execute_deploy else None
                        )
                        execute_phase_status = st.status(
                            f"▶️ Execute — `{trace_name}`", expanded=True
                        )

                    with evm_col:
                        result = exec_contract_automatically(
                            contract_deployment_id,
                            trace_data=trace_data,
                            execute_deploy=execute_deploy,
                            execute_compile=execute_compile,
                            initial_balance=initial_balance if execute_deploy else None,
                            phase_statuses={"deploy": deploy_phase_status, "execute": execute_phase_status},
                        )

                    evm_collected.append({"trace_name": trace_name, "result": result or {}})
                    with evm_col:
                        evm_progress.progress((evm_idx + 1) / max(len(evm_trace_list), 1))
                        if evm_idx + 1 == len(evm_trace_list):
                            evm_caption.caption(
                                f"✅ Completate {len(evm_trace_list)}/{len(evm_trace_list)} tracce"
                            )

            except Exception as e:
                evm_collected.append({
                    "trace_name": "unknown",
                    "result": {"success": False, "error": str(e), "results": [], "network": "unknown"},
                })
                with evm_col:
                    st.error(f"❌ EVM execution error: {e}")

            if evm_collected:
                st.session_state["evm_trace_results"] = evm_collected
                if not tezos_selected:
                    queue_trace_view("Trace Report")

        if tezos_selected and evm_selected:
            t_tezos = threading.Thread(target=_exec_tezos, name="rosetta-tezos")
            t_evm   = threading.Thread(target=_exec_evm,   name="rosetta-evm")
            add_script_run_ctx(t_tezos, ctx)
            add_script_run_ctx(t_evm,   ctx)
            t_tezos.start()
            t_evm.start()
            t_tezos.join()
            t_evm.join()
        elif tezos_selected:
            _exec_tezos()
        elif evm_selected:
            _exec_evm()

        st.rerun()


def showLinks(config_list):
    """Show links to relevant toolchain pages based on configuration."""
    col1, = st.columns(1)
    with col1:
        if "solana" in config_list :
            st.page_link("pages/Solana.py", label="🌞 Solana Toolchain")
        if "tezos" in config_list :
            st.page_link("pages/Tezos.py", label="🔷 Tezos Toolchain")
        if "evm" in config_list :
            st.page_link("pages/Ethereum.py", label="⚡ Ethereum Toolchain")
        if "cardano" in config_list :
            st.page_link("pages/Cardano.py", label="🧩 Cardano Toolchain")



