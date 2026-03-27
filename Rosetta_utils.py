import os
import sys
import re
import asyncio
import json
from io import StringIO

_base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_base_dir, "modules"))
sys.path.append(os.path.join(_base_dir, "modules", "Solana_module"))

_toolchain_dir = os.path.join(_base_dir, "modules", "Tezos_module", "toolchain")
if _toolchain_dir not in sys.path:
    sys.path.insert(0, _toolchain_dir)

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
)

from Cardano_module.cardano_module.cardano_utils import cardano_base_path
from Solana_module.solana_module.anchor_module.anchor_utils import anchor_base_path


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
        return

    report = get_trace_report_state()
    if report:
        st.caption("A trace report is available in the dedicated view.")

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

            if execute_deploy and tezos_selected:
                preview_trace_data = next(iter(contract_traces.values()))
                try:
                    _orig = os.getcwd()
                    os.chdir(_toolchain_dir)
                    try:
                        available_trace_contracts = resolveTraceContractCandidates(
                            selectedContract=selected_contract, traceData=preview_trace_data
                        )
                    finally:
                        os.chdir(_orig)
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

                default_balance = (last_setup.get("initial_balance", 1)
                                   if last_setup and last_setup.get("selected_contract") == selected_contract
                                   else 1)
                initial_balance = st.number_input(
                    "Initial balance (ꜩ)", min_value=0, value=default_balance, step=1,
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

    if tezos_selected and st.button(button_label):
        save_trace_setup_config({
            "selected_contract": selected_contract, "execution_mode": execution_mode,
            "selected_trace": selected_trace, "execute_deploy": execute_deploy,
            "execute_compile": execute_compile, "execute_redeploy": execute_redeploy,
            "initial_balance": initial_balance, "selected_trace_suite": selected_trace_suite,
            "show_live_terminal_output": show_live_terminal_output,
        })

        _orig = os.getcwd()
        os.chdir(_toolchain_dir)
        try:
            client = get_client(wallet_selection)
        finally:
            os.chdir(_orig)

        trace_report = {
            "title": f"Trace report for {selected_trace if execution_mode == 'Single trace' else selected_contract}",
            "status": "success",
            "summary": {
                "executed_traces": len(selected_trace_names), "execution_mode": execution_mode,
                "execute_deploy": execute_deploy, "selected_suite": selected_trace_suite,
            },
            "traces": [],
        }
        status_box, progress_bar, results_placeholder, terminal_placeholders, metrics_placeholder = (
            render_live_trace_progress(
                title=trace_report["title"], total_traces=len(selected_trace_names),
                show_terminal_output=show_live_terminal_output,
            )
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
                _orig2 = os.getcwd()
                os.chdir(_toolchain_dir)
                try:
                    trace_entry = run_trace_with_report(
                        client=client, selected_contract=selected_contract,
                        trace_name=trace_name, trace_data=contract_traces[trace_name],
                        execute_deploy=execute_deploy, execute_compile=execute_compile,
                        initial_balance=initial_balance, preferred_suite=selected_trace_suite,
                        compile_before_trace=compile_before_trace, deploy_before_trace=execute_deploy,
                        show_live_terminal_output=show_live_terminal_output,
                        phase_placeholders=terminal_placeholders,
                    )
                finally:
                    os.chdir(_orig2)

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
            st.rerun()
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



