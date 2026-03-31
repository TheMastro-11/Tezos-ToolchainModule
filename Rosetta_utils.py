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
    restore_trace_setup,
    trace_phase_status_icon,
    render_phase_block,
)

from Cardano_module.cardano_module.cardano_utils import cardano_base_path
from Solana_module.solana_module.anchor_module.anchor_utils import anchor_base_path

try:
    from Ethereum_module.hardhat_module.automatic_execution_manager import exec_contract_automatically
    _evm_available = True
except ImportError:
    _evm_available = False


def _render_evm_execution_payload(steps, global_error=None):
    """Render EVM step metrics, table, optional global error, and raw payload.

    Mirrors render_execution_phase_payload() from trace_utils but with EVM fields.
    """
    total = len(steps)
    passed = sum(1 for s in steps if s.get("success", False))
    failed = total - passed
    total_gas = sum(s.get("gas_used", 0) or 0 for s in steps)

    mc = st.columns(4)
    mc[0].metric("Steps", total)
    mc[1].metric("Passed", passed)
    mc[2].metric("Failed", failed)
    mc[3].metric("Total gas", total_gas)

    rows = []
    for s in steps:
        tx = s.get("transaction_hash") or ""
        rows.append({
            "Step": s.get("step", "-"),
            "Function": s.get("function_name", "-"),
            "Status": "OK" if s.get("success", False) else "Fail",
            "Tx Hash": (tx[:20] + "…") if tx else s.get("return_value", "-"),
            "Gas": s.get("gas_used", "-"),
            "Error": s.get("error", ""),
        })
    st.dataframe(rows, width='stretch', hide_index=True)

    if global_error:
        with st.expander("Global error", expanded=True):
            st.code(global_error, language="text")

    with st.expander("Raw execution payload"):
        st.json(steps)


def render_evm_trace_results():
    """Render EVM execution results stored in session state.

    Visual structure mirrors render_trace_report() from trace_utils.
    """
    evm_results = st.session_state.get("evm_trace_results", [])
    if not evm_results:
        return

    last_setup = get_last_trace_setup()
    has_tezos_report = bool(get_trace_report_state())

    # ── 1. Header: status banner | Riesegui | Clear ───────────────────────────
    overall_success = all(
        entry.get("result", {}).get("success", False) for entry in evm_results
    )
    hcol1, hcol2, hcol3 = st.columns([3, 2, 1])
    with hcol1:
        if overall_success:
            st.success("⚡ EVM execution completed successfully.")
        else:
            st.error("⚡ EVM execution completed with errors.")
    with hcol2:
        if last_setup and not has_tezos_report:
            if st.button("🔄 Riesegui Ultimo Setup", width='stretch',
                         help="Torna all'Execution Setup con la stessa configurazione"):
                restore_trace_setup()
                st.rerun()
    with hcol3:
        if st.button("🗑️ Clear EVM", width='stretch'):
            st.session_state.pop("evm_trace_results", None)
            st.rerun()

    # ── 2. 4 summary metrics ──────────────────────────────────────────────────
    first_result = evm_results[0].get("result", {}) if evm_results else {}
    network_label = first_result.get("network", "unknown")
    deploy_enabled = any(
        (entry.get("result", {}).get("phases") or {}).get("deploy", {}).get("status") == "success"
        for entry in evm_results
    )
    tc = st.columns(4)
    tc[0].metric("Executed traces", len(evm_results))
    tc[1].metric("Network", network_label)
    tc[2].metric("Deploy", "Enabled" if deploy_enabled else "Disabled")
    tc[3].metric("Platform", "Ethereum")

    # ── 3. Aggregate metrics + trace overview dataframe ───────────────────────
    result_rows = []
    for entry in evm_results:
        result = entry.get("result", {})
        steps = result.get("results", [])
        result_rows.append({
            "Trace": entry.get("trace_name", "Trace"),
            "Status": "success" if result.get("success", False) else "error",
            "Steps": len(steps),
            "Gas": sum(s.get("gas_used", 0) or 0 for s in steps),
            "Address": result.get("contract_address") or "-",
        })

    if result_rows:
        ac = st.columns(3)
        ac[0].metric("Total steps", sum(r["Steps"] for r in result_rows))
        ac[1].metric("Total gas", sum(r["Gas"] for r in result_rows))
        ac[2].metric("Passed traces", sum(1 for r in result_rows if r["Status"] == "success"))
        st.subheader("Trace overview")
        st.dataframe(result_rows, width='stretch', hide_index=True)

    # ── 4. Detailed results ───────────────────────────────────────────────────
    st.subheader("Detailed results")
    for entry in evm_results:
        trace_name = entry.get("trace_name", "Trace")
        result = entry.get("result", {})
        success = result.get("success", False)
        network = result.get("network", "unknown")
        steps = result.get("results", [])
        global_error = result.get("error")
        address = result.get("contract_address")
        # Backward-compat: phases key may be absent in results from older sessions
        phases = result.get("phases") or {}

        status_label = "success" if success else "error"
        status_icon = trace_phase_status_icon(status_label)

        with st.container(border=True):
            hl, hr = st.columns([3, 2])
            with hl:
                st.markdown(f"**{status_icon} {trace_name}**")
            with hr:
                if address:
                    st.caption(f"Address: `{address}`")
                else:
                    st.caption(f"Network: `{network}`")

            phase_tabs = st.tabs(["Summary", "Deploy", "Execute"])

            # Summary tab: phase status table
            with phase_tabs[0]:
                summary_rows = []
                for pn in ["deploy", "execute"]:
                    pd_data = phases.get(pn)
                    if pd_data is not None:
                        summary_rows.append({
                            "Phase": pn.title(),
                            "Status": pd_data.get("status", "-"),
                            "Details": pd_data.get("details", "-"),
                        })
                if summary_rows:
                    st.dataframe(summary_rows, width='stretch', hide_index=True)
                else:
                    st.info("No phase summary available.")

            # Deploy tab
            with phase_tabs[1]:
                deploy_phase = phases.get("deploy")
                if deploy_phase is not None:
                    render_phase_block("deploy", deploy_phase)
                else:
                    st.info("Deploy phase not available for this trace.")

            # Execute tab
            with phase_tabs[2]:
                execute_phase = phases.get("execute")
                if execute_phase is not None:
                    render_phase_block("execute", execute_phase)
                if steps:
                    _render_evm_execution_payload(steps, global_error)
                elif global_error:
                    with st.expander("Global error", expanded=True):
                        st.code(global_error, language="text")
                else:
                    st.info("No step results recorded.")

    # ── 5. Back button ────────────────────────────────────────────────────────
    if st.button("⬅️ Back to execution setup", key="evm_report_back_button"):
        queue_trace_view("Execution Setup")
        st.rerun()


def render_cross_chain_comparison():
    """Render a side-by-side cost comparison between Tezos and EVM results."""
    tezos_report = get_trace_report_state()
    evm_results  = st.session_state.get("evm_trace_results", [])
    if not tezos_report or not evm_results:
        return

    st.subheader("📊 Cross-Chain Cost Comparison")

    # Build lookup: trace_name → payload (Tezos) / steps list (EVM)
    tezos_by_name = {}
    for tr in tezos_report.get("traces", []):
        name    = tr.get("trace_name", "")
        payload = tr.get("phases", {}).get("execute", {}).get("payload") or {}
        tezos_by_name[name] = payload

    evm_by_name = {}
    for entry in evm_results:
        name  = entry.get("trace_name", "")
        steps = entry.get("result", {}).get("results", [])
        evm_by_name[name] = steps

    all_names = list(dict.fromkeys(list(tezos_by_name) + list(evm_by_name)))

    for trace_name in all_names:
        tezos_payload = tezos_by_name.get(trace_name, {})
        evm_steps     = evm_by_name.get(trace_name, [])

        comp_rows = []
        total_tezos = 0
        total_evm   = 0
        seen_funcs  = set()

        # Tezos steps
        for seq_id, step in tezos_payload.items():
            fn       = step.get("entryPoint") or step.get("function_name", "")
            tz_cost  = int(step.get("TotalCost", 0) or 0)
            total_tezos += tz_cost
            seen_funcs.add(fn)
            evm_match = next((s for s in evm_steps if s.get("function_name") == fn), None)
            evm_gas   = evm_match.get("gas_used", 0) if evm_match else None
            if isinstance(evm_gas, int):
                total_evm += evm_gas
            comp_rows.append({
                "Step": str(seq_id),
                "Function": fn,
                "Tezos (mutez)": tz_cost,
                "ETH (gas)": evm_gas if evm_gas is not None else "",
            })

        # EVM-only steps (not in Tezos)
        for evm_step in evm_steps:
            fn = evm_step.get("function_name", "")
            if fn not in seen_funcs:
                evm_gas = evm_step.get("gas_used", 0) or 0
                total_evm += evm_gas
                comp_rows.append({
                    "Step": str(evm_step.get("step", "")),
                    "Function": fn,
                    "Tezos (mutez)": "",
                    "ETH (gas)": evm_gas,
                })

        if comp_rows:
            comp_rows.append({
                "Step": "Total",
                "Function": "",
                "Tezos (mutez)": total_tezos,
                "ETH (gas)": total_evm,
            })

        with st.expander(f"📈 {trace_name}", expanded=True):
            if comp_rows:
                _df = pd.DataFrame(comp_rows)
                # Ensure uniform types — Arrow requires each column to have one dtype
                for _col in ("Tezos (mutez)", "ETH (gas)"):
                    if _col in _df.columns:
                        _df[_col] = _df[_col].apply(
                            lambda v: int(v) if isinstance(v, (int, float)) and v != "" else (v if v != "" else 0)
                        )
                st.dataframe(_df, width='stretch', hide_index=True)
            else:
                st.info("No execution data available for this trace.")


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
        render_cross_chain_comparison()
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

    # Se "Riesegui" è stato cliccato, forza il multiselect al valore salvato
    last_setup = get_last_trace_setup()
    if st.session_state.pop("_rosetta_restore_pending", False):
        if (last_setup and "selected_toolchain_keys" in last_setup and
                last_setup.get("selected_contract") == selected_contract):
            _saved_labels = [
                _toolchain_label_map.get(k, k.title())
                for k in last_setup["selected_toolchain_keys"]
                if k in config_list
            ]
            _valid_labels = [l for l in _saved_labels if l in toolchain_options]
            if _valid_labels:
                st.session_state[
                    f"rosetta_toolchain_select_{selected_contract}_{selected_trace}"
                ] = _valid_labels

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

    # --- Network Selection (Change 7) ---
    selected_networks: dict = {}
    with st.container(border=True):
        st.subheader("🌐 Network Selection")
        active_chain_keys = [k for k in selected_toolchain_keys if k in ("tezos", "evm", "solana")]
        if active_chain_keys:
            net_cols = st.columns(len(active_chain_keys))
            for _i, _chain_key in enumerate(active_chain_keys):
                with net_cols[_i]:
                    if _chain_key == "tezos":
                        selected_networks["tezos"] = st.selectbox(
                            "🔷 Tezos",
                            options=["ghostnet"],
                            key=f"rosetta_network_tezos_{selected_contract}_{execution_mode}",
                        )
                    elif _chain_key == "evm":
                        selected_networks["evm"] = st.selectbox(
                            "⚡ Ethereum (EVM)",
                            options=["localhost", "sepolia", "mainnet"],
                            key=f"rosetta_network_evm_{selected_contract}_{execution_mode}",
                        )
                    elif _chain_key == "solana":
                        selected_networks["solana"] = st.selectbox(
                            "🌞 Solana",
                            options=["devnet", "testnet", "mainnet-beta"],
                            key=f"rosetta_network_solana_{selected_contract}_{execution_mode}",
                        )
        else:
            st.caption("Select at least one toolchain to configure the network.")

    # --- Execution Plan (Change 5) ---
    _plan_trace_data = (
        contract_traces[selected_trace]
        if selected_trace and selected_trace in contract_traces
        else next(iter(contract_traces.values()))
    )
    with st.expander("📋 Execution Plan", expanded=True):
        _plan_rows = []
        for _step in _plan_trace_data.get("trace_execution", []):
            _row = {
                "Seq": _step.get("sequence_id", ""),
                "Function": _step.get("function_name", ""),
                "Actors": ", ".join(_step.get("actors", [])),
                "Wait (blocks)": _step.get("waiting_time", 0),
                "Args": str(_step.get("args", {})),
            }
            if "evm" in selected_toolchain_keys:
                _row["EVM method"] = _step.get("evm", {}).get("method", _step.get("function_name", ""))
            if "tezos" in selected_toolchain_keys:
                _row["Tezos entrypoint"] = _step.get("tezos", {}).get("entrypoint", "")
            _plan_rows.append(_row)
        if _plan_rows:
            st.dataframe(pd.DataFrame(_plan_rows), width='stretch', hide_index=True)
        else:
            st.info("No execution steps found in this trace.")

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
            "selected_toolchain_keys": selected_toolchain_keys,
            "selected_networks": selected_networks,
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

            evm_title = (
                f"Trace report for {selected_trace if execution_mode == 'Single trace' else selected_contract}"
            )

            with evm_col:
                st.subheader(_chain_labels["evm"])
                (evm_status_box, evm_progress_bar, evm_results_placeholder,
                 _evm_terminals, evm_metrics_placeholder) = render_live_trace_progress(
                    title=evm_title,
                    total_traces=len(evm_trace_list),
                    show_terminal_output=False,
                )

            completed_rows = []
            try:
                for evm_idx, trace_name in enumerate(evm_trace_list):
                    trace_data = contract_traces[trace_name]
                    contract_deployment_id = trace_data.get("trace_title", selected_contract).lower()

                    update_live_trace_progress(
                        status_box=evm_status_box, progress_bar=evm_progress_bar,
                        results_placeholder=evm_results_placeholder, completed_items=completed_rows,
                        total_traces=len(evm_trace_list), current_trace=trace_name,
                        metrics_placeholder=evm_metrics_placeholder,
                    )

                    with evm_col:
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
                            network_override=selected_networks.get("evm", "localhost"),
                        )

                    evm_collected.append({"trace_name": trace_name, "result": result or {}})

                    _steps = (result or {}).get("results", [])
                    completed_rows.append({
                        "Trace": trace_name,
                        "Status": "success" if (result or {}).get("success", False) else "error",
                        "Steps": len(_steps),
                        "Gas": sum(s.get("gas_used", 0) or 0 for s in _steps),
                        "Address": (result or {}).get("contract_address") or "-",
                    })
                    update_live_trace_progress(
                        status_box=evm_status_box, progress_bar=evm_progress_bar,
                        results_placeholder=evm_results_placeholder, completed_items=completed_rows,
                        total_traces=len(evm_trace_list),
                        metrics_placeholder=evm_metrics_placeholder,
                    )

            except Exception as e:
                evm_collected.append({
                    "trace_name": "unknown",
                    "result": {"success": False, "error": str(e), "results": [], "network": "unknown"},
                })
                update_live_trace_progress(
                    status_box=evm_status_box, progress_bar=evm_progress_bar,
                    results_placeholder=evm_results_placeholder, completed_items=completed_rows,
                    total_traces=len(evm_trace_list), has_error=True,
                    metrics_placeholder=evm_metrics_placeholder,
                )
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



