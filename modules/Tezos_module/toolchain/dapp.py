import contextlib
import io
import json
from pathlib import Path

import streamlit as st
from pytezos import pytezos

from contractUtils import (
    compileContract,
    entrypointAnalyse,
    entrypointCall,
    callInfoResult,
    runScenario,
    getCompiledRoot,
)
from folderScan import folderScan, contractSuites, scenarioScan
from csvUtils import csvWriter
from jsonUtils import (
    getAddress,
    jsonWriter,
    jsonReaderByContract,
    normalizeContractName,
)
from main import (
    getContractsRoot,
    getTraceRoot,
    getScenariosRoot,
    parseContractId,
    getCompiledContracts,
    resolveCompiledContractInfo,
    resolveTraceContractCandidates,
    resolveTraceContractId,
    deployContract,
    compileAndDeployForTrace,
    normalizeContractToken,
    exportResult,
    executionSetupCsv,
    executionSetupJson,
)

st.set_page_config(
    page_title="Tezos Smart Contract Toolchain",
    layout="centered"
)

st.title("🏗️ Tezos Smart Contract Toolchain")
st.caption("An interface to compile, deploy, interact with, and test Tezos smart contracts.")


# ---------------------------------------------------------------------------
#  Streamlit helpers (UI-only, not business logic)
# ---------------------------------------------------------------------------

def get_client(wallet_id):
    try:
        with open("wallet.json", 'r', encoding='utf-8') as f:
            wallets = json.load(f)
        key = wallets.get(str(wallet_id))
        if not key:
            st.error(f"Wallet with ID {wallet_id} not found in wallet.json.")
            return None
        return pytezos.using(shell="ghostnet", key=key)
    except FileNotFoundError:
        st.error("The wallet.json file was not found. Make sure it is in the correct directory.")
        return None
    except Exception as e:
        st.error(f"Error during client configuration: {e}")
        return None


class StreamlitTerminalWriter(io.TextIOBase):
    def __init__(self, placeholder=None):
        self.placeholder = placeholder
        self.buffer = ""

    def write(self, text):
        if not text:
            return 0
        self.buffer += text
        if self.placeholder is not None:
            self.placeholder.code(self.buffer, language="text")
        return len(text)

    def flush(self):
        if self.buffer and self.placeholder is not None:
            self.placeholder.code(self.buffer, language="text")

    def getvalue(self):
        return self.buffer


def run_with_terminal_output(action, session_key, render_live=True, output_placeholder=None):
    terminal_placeholder = output_placeholder if output_placeholder is not None else (st.empty() if render_live else None)
    terminal_writer = StreamlitTerminalWriter(terminal_placeholder)
    result = None
    exc_to_raise = None

    try:
        with contextlib.redirect_stdout(terminal_writer), contextlib.redirect_stderr(terminal_writer):
            result = action()
    except Exception as exc:
        exc_to_raise = exc

    # Always persist and render whatever was printed, even on failure.
    terminal_output = terminal_writer.getvalue().strip()
    st.session_state[session_key] = terminal_output

    if terminal_placeholder is not None:
        if terminal_output:
            terminal_placeholder.code(terminal_output, language="text")
        else:
            terminal_placeholder.info("No terminal output produced.")

    if exc_to_raise is not None:
        raise exc_to_raise

    return result, terminal_output


def render_terminal_output(session_key, title="Terminal output"):
    output = st.session_state.get(session_key, "").strip()
    if output:
        st.subheader(title)
        st.code(output, language="text")


def st_export_result(opResult):
    exportResult(opResult)
    st.success(f"Result of operation {opResult['entryPoint']} saved to file.")


# ---------------------------------------------------------------------------
#  Trace report helpers (UI rendering)
# ---------------------------------------------------------------------------

def get_trace_report_state():
    return st.session_state.get("trace_report_data")

def queue_trace_view(target_view):
    st.session_state["trace_view_page_target"] = target_view

def save_trace_report(report_data):
    st.session_state["trace_report_data"] = report_data
    queue_trace_view("Trace Report")

def save_trace_setup_config(config_data):
    """Save the last execution setup configuration for re-run"""
    st.session_state["last_trace_setup"] = config_data

def get_last_trace_setup():
    """Retrieve the last execution setup configuration"""
    return st.session_state.get("last_trace_setup")

def restore_trace_setup():
    """Restore the last execution setup and switch to Execution Setup view"""
    queue_trace_view("Execution Setup")

def trace_phase_status_icon(status):
    return {"success": "✅", "error": "❌", "skipped": "➖"}.get(status, "ℹ️")

def render_phase_block(phase_name, phase_data):
    status = phase_data.get("status", "info")
    title = f"{trace_phase_status_icon(status)} {phase_name.title()}"
    with st.expander(title, expanded=status == "error"):
        details = phase_data.get("details")
        if details:
            st.caption(details)
        output = phase_data.get("output", "").strip()
        if output:
            st.code(output, language="text")
        else:
            st.info("No terminal output produced.")
        payload = phase_data.get("payload")
        if payload is not None:
            st.json(payload)

def summarize_trace_payload(payload):
    summary = {"steps": 0, "total_baker_fee": 0, "total_storage": 0, "total_cost": 0, "total_gas": 0}
    if not isinstance(payload, dict):
        return summary
    for _, step in payload.items():
        if not isinstance(step, dict):
            continue
        summary["steps"] += 1
        summary["total_baker_fee"] += int(step.get("BakerFee", 0) or 0)
        summary["total_storage"] += int(step.get("Storage", 0) or 0)
        summary["total_cost"] += int(step.get("TotalCost", 0) or 0)
        summary["total_gas"] += int(step.get("Gas", 0) or 0)
    return summary

def build_trace_result_rows(report):
    rows = []
    for trace_report in report.get("traces", []):
        execute_phase = trace_report.get("phases", {}).get("execute", {})
        payload_summary = summarize_trace_payload(execute_phase.get("payload"))
        rows.append({
            "Trace": trace_report.get("trace_name", "-"),
            "Status": trace_report.get("status", "success"),
            "Steps": payload_summary["steps"],
            "Total cost": payload_summary["total_cost"],
            "Gas": payload_summary["total_gas"],
            "Address": trace_report.get("contract_address", "-"),
        })
    return rows

def render_trace_selection_summary(selected_contract, execution_mode, trace_names, execute_deploy, execute_compile, execute_redeploy, initial_balance, selected_trace_suite, show_live_terminal_output):
    st.subheader("Execution plan")
    left_col, middle_col, right_col = st.columns(3)
    with left_col:
        st.metric("Contract group", selected_contract)
        st.metric("Execution mode", execution_mode)
    with middle_col:
        st.metric("Traces selected", len(trace_names))
        st.metric("Contract suite", selected_trace_suite or "Auto")
    with right_col:
        st.metric("Deploy", "Enabled" if execute_deploy else "Disabled")
        st.metric("Compile", "Enabled" if execute_compile else "Disabled")
    option_labels = []
    if execute_deploy:
        option_labels.append("Deploy before execution")
    if execute_compile:
        option_labels.append("Compile before deploy")
    if execute_redeploy:
        option_labels.append("Re-deploy before each trace")
    if execute_deploy:
        option_labels.append(f"Initial balance: {initial_balance} ꜩ")
    if show_live_terminal_output:
        option_labels.append("Live terminal output enabled")
    if option_labels:
        st.caption(" • ".join(option_labels))
    preview_rows = [{"#": i + 1, "Trace": t} for i, t in enumerate(trace_names)]
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)

def render_execution_phase_payload(payload):
    if not isinstance(payload, dict) or not payload:
        st.info("No structured execution payload available.")
        return
    payload_summary = summarize_trace_payload(payload)
    mc = st.columns(4)
    mc[0].metric("Steps", payload_summary["steps"])
    mc[1].metric("Total cost", payload_summary["total_cost"])
    mc[2].metric("Baker fee", payload_summary["total_baker_fee"])
    mc[3].metric("Storage burn", payload_summary["total_storage"])
    rows = []
    for step_name, step_data in payload.items():
        rows.append({
            "Step": step_name, "Contract": step_data.get("contract", "-"),
            "Entrypoint": step_data.get("entryPoint", "-"), "Hash": step_data.get("Hash", "-"),
            "TotalCost": step_data.get("TotalCost", 0), "BakerFee": step_data.get("BakerFee", 0),
            "Storage": step_data.get("Storage", 0), "Gas": step_data.get("Gas", 0),
            "Weight": step_data.get("Weight", 0),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Raw execution payload"):
        st.json(payload)

def render_live_trace_progress(title, total_traces, show_terminal_output):
    status_box = st.container(border=True)
    with status_box:
        st.subheader("Live execution")
        st.caption(title)
        metrics_placeholder = st.empty()
    progress_bar = st.progress(0.0)
    results_placeholder = st.empty()
    terminal_placeholders = _render_live_phase_terminals(show_terminal_output)
    return status_box, progress_bar, results_placeholder, terminal_placeholders, metrics_placeholder

def update_live_trace_progress(status_box, progress_bar, results_placeholder, completed_items, total_traces, current_trace=None, has_error=False, metrics_placeholder=None):
    completed_count = len(completed_items)
    progress_bar.progress(completed_count / total_traces if total_traces else 0.0)
    # Use metrics_placeholder.container() so content is overwritten on each call
    # instead of being appended to the outer status_box container.
    target = metrics_placeholder if metrics_placeholder is not None else status_box
    with target.container():
        sc = st.columns(3)
        sc[0].metric("Completed", completed_count)
        sc[1].metric("Remaining", max(total_traces - completed_count, 0))
        sc[2].metric("Status", "Error" if has_error else ("Running" if completed_count < total_traces else "Done"))
        if current_trace:
            st.caption(f"Current trace: `{current_trace}`")
    if completed_items:
        results_placeholder.dataframe(completed_items, use_container_width=True, hide_index=True)
    else:
        results_placeholder.info("The execution summary will appear here as traces complete.")

def _render_live_phase_terminals(show_terminal_output):
    if not show_terminal_output:
        return {}
    terminal_box = st.container(border=True)
    with terminal_box:
        st.subheader("Live terminal output")
        tabs = st.tabs(["Compile", "Deploy", "Execute"])
        placeholders = {}
        for i, name in enumerate(["compile", "deploy", "execute"]):
            with tabs[i]:
                placeholders[name] = st.empty()
                placeholders[name].info(f"{name.title()} output will appear here when this phase runs.")
    return placeholders

def render_trace_report():
    report = get_trace_report_state()
    if not report:
        st.info("No trace report available yet.")
        return
    
    # Add header with "Re-run Last Setup" button
    header_col1, header_col2, header_col3 = st.columns([3, 2, 1])
    with header_col1:
        status = report.get("status", "success")
        if status == "success":
            st.success(report.get("title", "Trace execution completed."))
        else:
            st.error(report.get("title", "Trace execution failed."))
    
    last_setup = get_last_trace_setup()
    with header_col2:
        if last_setup and st.button("🔄 Riesegui Ultimo Setup", help="Torna all'Execution Setup con la stessa configurazione", use_container_width=True):
            restore_trace_setup()
            st.rerun()
    
    with header_col3:
        if st.button("🗑️ Clear", help="Cancella il report", use_container_width=True):
            st.session_state.pop("trace_report_data", None)
            st.session_state.pop("last_trace_setup", None)
            queue_trace_view("Execution Setup")
            st.rerun()
    
    summary = report.get("summary", {})
    result_rows = build_trace_result_rows(report)
    tc = st.columns(4)
    tc[0].metric("Executed traces", summary.get("executed_traces", 0))
    tc[1].metric("Execution mode", summary.get("execution_mode", "-"))
    tc[2].metric("Deploy", "Enabled" if summary.get("execute_deploy") else "Disabled")
    tc[3].metric("Contract suite", summary.get("selected_suite") or "Auto")
    if result_rows:
        ac = st.columns(3)
        ac[0].metric("Total steps", sum(r["Steps"] for r in result_rows))
        ac[1].metric("Total cost", sum(r["Total cost"] for r in result_rows))
        ac[2].metric("Total gas", sum(r["Gas"] for r in result_rows))
        st.subheader("Trace overview")
        st.dataframe(result_rows, use_container_width=True, hide_index=True)
    report_error = report.get("error")
    if report_error:
        with st.expander("Execution error", expanded=True):
            st.code(report_error, language="text")
    st.subheader("Detailed results")
    for tr in report.get("traces", []):
        trace_name = tr.get("trace_name", "Trace")
        trace_address = tr.get("contract_address")
        trace_status = tr.get("status", "success")
        label = f"{trace_phase_status_icon(trace_status)} {trace_name}"
        with st.container(border=True):
            hl, hr = st.columns([3, 2])
            with hl:
                st.markdown(f"**{label}**")
                if tr.get("contract_id"):
                    st.caption(f"Contract: `{tr['contract_id']}`")
            with hr:
                if trace_address:
                    st.caption(f"Address: `{trace_address}`")
            phase_tabs = st.tabs(["Summary", "Compile", "Deploy", "Execute"])
            phases = tr.get("phases", {})
            with phase_tabs[0]:
                sr = []
                for pn in ["compile", "deploy", "execute"]:
                    pd = phases.get(pn)
                    if pd is not None:
                        sr.append({"Phase": pn.title(), "Status": pd.get("status", "-"), "Details": pd.get("details", "-")})
                if sr:
                    st.dataframe(sr, use_container_width=True, hide_index=True)
                else:
                    st.info("No phase summary available.")
            for ti, pn in enumerate(["compile", "deploy", "execute"], start=1):
                with phase_tabs[ti]:
                    pd = phases.get(pn)
                    if pd is None:
                        st.info(f"{pn.title()} phase not available for this trace.")
                    else:
                        render_phase_block(pn, pd)
                        if pn == "execute":
                            render_execution_phase_payload(pd.get("payload"))
    if st.button("⬅️ Back to execution setup", key="trace_report_back_button"):
        queue_trace_view("Execution Setup")
        st.rerun()

def create_trace_phase(status, output="", details=None, payload=None):
    phase = {"status": status, "output": output or ""}
    if details:
        phase["details"] = details
    if payload is not None:
        phase["payload"] = payload
    return phase


# ---------------------------------------------------------------------------
#  Views (Streamlit UI wrapping main.py logic)
# ---------------------------------------------------------------------------

def execution_setup_auto(contract, rows):
    if isinstance(rows, dict) and "trace_execution" in rows:
        return executionSetupJson(contractId=contract, traceData=rows)
    return executionSetupCsv(contractId=contract, rows=rows)


def compile_view(client):
    st.header("1. Compile SmartPy Contracts")
    contracts_root = getContractsRoot()
    suites = contractSuites(contracts_root)
    if not suites:
        st.warning("No contract families found in the contracts directory.")
        return
    selected_suite = st.selectbox("Select a contract family:", options=suites, key="compile_suite_select")
    contracts = folderScan(contracts_root, suite=selected_suite)
    if not contracts:
        st.warning(f"No contracts found in '{selected_suite}'.")
        return
    contract_to_compile = st.selectbox("Select a contract to compile:", options=contracts, key="compile_select")
    if st.button("🚀 Compile"):
        if contract_to_compile and client:
            folder, impl = parseContractId(contract_to_compile)
            contract_path = contracts_root / folder / f"{impl}.py"
            with st.spinner(f"Compiling {contract_path}..."):
                try:
                    _, _ = run_with_terminal_output(
                        lambda: compileContract(contractPath=str(contract_path)),
                        "compile_terminal_output"
                    )
                    st.success(f"Contract '{contract_to_compile}' compiled successfully!")
                    st.info(f"The Michelson files have been generated in `{getCompiledRoot()}`.")
                except Exception as e:
                    st.error("Error during compilation")
                    st.code(str(e))
    render_terminal_output("compile_terminal_output")


def deploy_view(client):
    st.header("2. Deploy a Contract (Origination)")
    compiled_contracts = getCompiledContracts()
    if not compiled_contracts:
        st.warning("No compiled contracts found in `toolchain/compiled`. Compile a contract before deploying.")
        return
    contract_to_deploy = st.selectbox("Select a compiled contract to deploy:", options=list(compiled_contracts.keys()), key="deploy_select")
    initial_balance = st.number_input("Initial balance (in tez):", min_value=0, value=1, step=1)
    if st.button("🌐 Deploy"):
        if contract_to_deploy and client:
            with st.spinner("Origination in progress... The operation may take a few minutes."):
                try:
                    results, _ = run_with_terminal_output(
                        lambda: deployContract(client=client, contractId=contract_to_deploy, initialBalance=initial_balance),
                        "deploy_terminal_output"
                    )
                    if results:
                        for r in results:
                            st.success(f"'{r['addressName']}' deployed at `{r['info']['address']}`")
                    else:
                        st.error("Origination failed. Check the console log for details.")
                except Exception as e:
                    st.error(f"Error during deployment: {e}")
    render_terminal_output("deploy_terminal_output")


def interact_view(client):
    st.header("3. Interact with a Contract")
    try:
        deployed_contracts = getAddress()
        if not deployed_contracts:
            st.warning("No deployed contracts found in `addressList.json`.")
            return
    except Exception:
        st.error("`addressList.json` not found or corrupted.")
        return
    contract_name = st.selectbox("Select a contract to interact with:", options=list(deployed_contracts.keys()))
    if contract_name and client:
        contract_address = deployed_contracts[contract_name]
        st.info(f"Contract address: `{contract_address}`")
        try:
            entrypoints_schema = entrypointAnalyse(client=client, contractAddress=contract_address)
            entrypoint_name = st.selectbox("Select an entrypoint:", options=list(entrypoints_schema.keys()))
            params_input = ""
            if entrypoints_schema.get(entrypoint_name) != "unit":
                params_input = st.text_input("Enter the parameters (comma-separated if multiple):", placeholder="value1,value2")
            tez_amount = st.number_input("Amount of Tez to send:", min_value=0.0, value=0.0, step=0.1, format="%.6f")
            if st.button("➡️ Execute Call"):
                parameters = params_input.split(',') if params_input else []
                with st.spinner(f"Calling entrypoint '{entrypoint_name}'..."):
                    try:
                        op_result, _ = run_with_terminal_output(
                            lambda: entrypointCall(client=client, contractAddress=contract_address, entrypointName=entrypoint_name, parameters=parameters, tezAmount=tez_amount),
                            "interact_terminal_output"
                        )
                        info_result = callInfoResult(opResult=op_result)
                        info_result["contract"] = contract_name
                        info_result["entryPoint"] = entrypoint_name
                        st.success("Call executed successfully!")
                        st.json(info_result)
                        if st.checkbox("Save result to CSV/JSON"):
                            st_export_result(info_result)
                    except Exception as e:
                        st.error(f"Error during call: {e}")
            render_terminal_output("interact_terminal_output")
        except Exception as e:
            st.error(f"Unable to analyze contract entrypoints: {e}")


def render_trace_execution(trace_name, trace_data, contract_name, render_live=False, output_placeholder=None):
    with st.spinner(f"Executing trace '{trace_name}'..."):
        results, terminal_output = run_with_terminal_output(
            lambda: execution_setup_auto(contract=trace_name, rows=trace_data),
            f"trace_terminal_output_{contract_name}_{trace_name}",
            render_live=render_live,
            output_placeholder=output_placeholder
        )
        for _, result in results.items():
            exportResult(result)
        return results, terminal_output


def run_trace_with_report(client, selected_contract, trace_name, trace_data, execute_deploy, execute_compile, initial_balance, preferred_suite, compile_before_trace, deploy_before_trace, show_live_terminal_output=False, phase_placeholders=None):
    trace_report = {"trace_name": trace_name, "status": "success", "phases": {}}
    try:
        if execute_deploy:
            # Resolve the contract ID once so both phases share the same target.
            contract_id = resolveTraceContractId(selected_contract, trace_data, preferred_suite)

            # --- Compile phase (output → "Compile" tab) ---
            if compile_before_trace:
                folder, implementation = parseContractId(contract_id)
                contract_path = getContractsRoot() / folder / f"{implementation}.py"
                if not contract_path.exists():
                    raise FileNotFoundError(f"Contract source not found: {contract_path}")
                compile_session_key = f"trace_compile_output_{normalizeContractToken(selected_contract)}"
                try:
                    _, compile_output = run_with_terminal_output(
                        lambda: compileContract(contractPath=str(contract_path)),
                        compile_session_key,
                        render_live=show_live_terminal_output,
                        output_placeholder=(phase_placeholders or {}).get("compile"),
                    )
                except Exception as compile_exc:
                    compile_output = st.session_state.get(compile_session_key, "")
                    trace_report["status"] = "error"
                    trace_report["phases"]["compile"] = create_trace_phase(
                        status="error",
                        output=compile_output,
                        details=f"Compilation of `{contract_id}` failed: {compile_exc}",
                    )
                    raise RuntimeError(str(compile_exc)) from compile_exc
                trace_report["phases"]["compile"] = create_trace_phase(
                    status="success",
                    output=compile_output,
                    details=f"Compiled contract `{contract_id}`.",
                )

            # --- Deploy phase (output → "Deploy" tab) ---
            deploy_results, deploy_output = run_with_terminal_output(
                lambda: deployContract(
                    client=client,
                    contractId=contract_id,
                    initialBalance=initial_balance,
                ),
                f"trace_deploy_output_{normalizeContractToken(selected_contract)}",
                render_live=show_live_terminal_output,
                output_placeholder=(phase_placeholders or {}).get("deploy"),
            )
            main_result = deploy_results[-1]
            contract_info = main_result["info"]
            trace_report["contract_id"] = contract_id
            trace_report["contract_address"] = contract_info["address"]
            trace_report["phases"]["deploy"] = create_trace_phase(
                status="success",
                output=deploy_output,
                details=f"Deployed contract `{contract_id}` to `{contract_info['address']}`.",
                payload=contract_info,
            )
        else:
            trace_report["phases"]["deploy"] = create_trace_phase(status="skipped", details="Deploy step disabled for this execution.")

        execute_output = st.session_state.get(f"trace_terminal_output_{selected_contract}_{trace_name}", "")
        try:
            results, execute_output = render_trace_execution(
                trace_name=trace_name, trace_data=trace_data, contract_name=selected_contract,
                render_live=show_live_terminal_output, output_placeholder=(phase_placeholders or {}).get("execute")
            )
        except Exception as exec_exc:
            execute_output = st.session_state.get(f"trace_terminal_output_{selected_contract}_{trace_name}", "")
            trace_report["status"] = "error"
            trace_report["phases"]["execute"] = create_trace_phase(
                status="error",
                output=execute_output,
                details=f"Trace `{trace_name}` failed during execution: {exec_exc}",
            )
            raise RuntimeError(str(exec_exc)) from exec_exc
        trace_report["phases"]["execute"] = create_trace_phase(status="success", output=execute_output, details=f"Executed trace `{trace_name}`.", payload=results)
        return trace_report
    except RuntimeError:
        raise
    except Exception as exc:
        trace_report["status"] = "error"
        if execute_deploy and deploy_before_trace and "deploy" not in trace_report["phases"]:
            trace_report["phases"]["deploy"] = create_trace_phase(status="error", details="Deploy step failed before execution.", output=str(exc))
        elif "execute" not in trace_report["phases"]:
            trace_report["phases"]["execute"] = create_trace_phase(status="error", details=f"Trace `{trace_name}` failed during execution.", output=str(exc))
        raise RuntimeError(str(exc)) from exc


def trace_view(client):
    st.header("4. Execute Trace")
    trace_root = getTraceRoot()
    st.info(f"Trace source folder: `{trace_root}`")
    pending_trace_view = st.session_state.pop("trace_view_page_target", None)
    if pending_trace_view in {"Execution Setup", "Trace Report"}:
        st.session_state["trace_view_page"] = pending_trace_view
    view_mode = st.radio("View", options=["Execution Setup", "Trace Report"], horizontal=True, key="trace_view_page")
    if view_mode == "Trace Report":
        render_trace_report()
        return
    report = get_trace_report_state()
    if report:
        st.caption("A trace report is available in the dedicated view.")
    try:
        execution_traces_by_contract = jsonReaderByContract(traceRoot=trace_root)
    except Exception as e:
        st.error(f"Error while loading traces: {e}")
        return
    if not execution_traces_by_contract:
        st.warning("No execution traces found.")
        return
    contract_names = list(execution_traces_by_contract.keys())
    
    # Retrieve last setup configuration to restore selections
    last_setup = get_last_trace_setup()
    
    # Initialize default values from last setup if available
    default_contract_index = 0
    if last_setup and last_setup.get("selected_contract") in contract_names:
        default_contract_index = contract_names.index(last_setup["selected_contract"])
    
    selected_contract = st.selectbox("Select a contract:", options=contract_names, index=default_contract_index, key="trace_contract_select")
    contract_traces = execution_traces_by_contract[selected_contract]
    trace_names = list(contract_traces.keys())
    if not trace_names:
        st.warning(f"No execution traces found for '{selected_contract}'.")
        return
    execution_mode_options = ["Single trace"]
    if selected_contract != "Ungrouped":
        execution_mode_options.append("All traces in contract")
    
    configuration_box = st.container(border=True)
    with configuration_box:
        st.subheader("Options")
        option_left, option_right = st.columns([3, 2])
        with option_left:
            # Restore execution mode from last setup
            default_exec_mode_index = 0
            if last_setup and last_setup.get("selected_contract") == selected_contract:
                if last_setup.get("execution_mode") in execution_mode_options:
                    default_exec_mode_index = execution_mode_options.index(last_setup["execution_mode"])
            
            execution_mode = st.radio("Execution mode", options=execution_mode_options, index=default_exec_mode_index, key="trace_execution_mode")
            selected_trace = None
            if execution_mode == "Single trace":
                # Restore selected trace from last setup
                default_trace_index = 0
                if last_setup and last_setup.get("selected_contract") == selected_contract and last_setup.get("selected_trace") in trace_names:
                    default_trace_index = trace_names.index(last_setup["selected_trace"])
                
                selected_trace = st.selectbox("Trace to execute", options=trace_names, index=default_trace_index, key="single_trace_select")
        with option_right:
            # Restore deploy option from last setup
            default_deploy = last_setup.get("execute_deploy", False) if last_setup and last_setup.get("selected_contract") == selected_contract else False
            execute_deploy = st.checkbox("Deploy before execution", value=default_deploy, key=f"trace_execute_deploy_{selected_contract}_{execution_mode}")
            execute_compile = False
            execute_redeploy = False
            initial_balance = 1
            selected_trace_suite = None
            if execute_deploy:
                preview_trace_data = next(iter(contract_traces.values()))
                available_trace_contracts = resolveTraceContractCandidates(selectedContract=selected_contract, traceData=preview_trace_data)
                suite_options = [s for s in ["Legacy", "Rosetta"] if s in available_trace_contracts]
                if suite_options:
                    # Restore suite selection from last setup
                    default_suite_index = 0
                    if last_setup and last_setup.get("selected_contract") == selected_contract and last_setup.get("selected_trace_suite") in suite_options:
                        default_suite_index = suite_options.index(last_setup["selected_trace_suite"])
                    
                    selected_trace_suite = st.radio("Contract suite", options=suite_options, horizontal=True, index=default_suite_index, key=f"trace_contract_variant_{selected_contract}_{execution_mode}")
                
                # Restore compile option from last setup
                default_compile = last_setup.get("execute_compile", False) if last_setup and last_setup.get("selected_contract") == selected_contract else False
                execute_compile = st.checkbox("Compile before deploy", value=default_compile, key=f"trace_execute_compile_{selected_contract}_{execution_mode}")
                
                # Restore initial balance from last setup
                default_balance = last_setup.get("initial_balance", 1) if last_setup and last_setup.get("selected_contract") == selected_contract else 1
                initial_balance = st.number_input("Initial balance (ꜩ)", min_value=0, value=default_balance, step=1, key=f"trace_initial_balance_{selected_contract}_{execution_mode}")
                
                if execution_mode == "All traces in contract":
                    # Restore redeploy option from last setup
                    default_redeploy = last_setup.get("execute_redeploy", False) if last_setup and last_setup.get("selected_contract") == selected_contract else False
                    execute_redeploy = st.checkbox("Re-deploy before each trace", value=default_redeploy, key=f"trace_execute_redeploy_{selected_contract}")
            
            # Restore show live output from last setup
            default_show_live = last_setup.get("show_live_terminal_output", True) if last_setup and last_setup.get("selected_contract") == selected_contract else True
            show_live_terminal_output = st.checkbox("Show live terminal output", value=default_show_live, key=f"trace_show_live_terminal_output_{selected_contract}_{execution_mode}")
    selected_trace_names = [selected_trace] if execution_mode == "Single trace" and selected_trace else trace_names
    render_trace_selection_summary(
        selected_contract=selected_contract, execution_mode=execution_mode, trace_names=selected_trace_names,
        execute_deploy=execute_deploy, execute_compile=execute_compile, execute_redeploy=execute_redeploy,
        initial_balance=initial_balance, selected_trace_suite=selected_trace_suite, show_live_terminal_output=show_live_terminal_output
    )
    if execute_redeploy:
        st.info("The contract will be compiled and deployed again before each trace.")
    button_label = "▶️ Execute selected trace" if execution_mode == "Single trace" else "▶️ Execute all traces in contract"
    if st.button(button_label):
        # Save current setup configuration for "Re-run Last Setup" feature
        current_setup_config = {
            "selected_contract": selected_contract,
            "execution_mode": execution_mode,
            "selected_trace": selected_trace,
            "execute_deploy": execute_deploy,
            "execute_compile": execute_compile,
            "execute_redeploy": execute_redeploy,
            "initial_balance": initial_balance,
            "selected_trace_suite": selected_trace_suite,
            "show_live_terminal_output": show_live_terminal_output,
        }
        save_trace_setup_config(current_setup_config)
        
        trace_report = {
            "title": f"Trace report for {selected_trace if execution_mode == 'Single trace' else selected_contract}",
            "status": "success",
            "summary": {"executed_traces": len(selected_trace_names), "execution_mode": execution_mode, "execute_deploy": execute_deploy, "selected_suite": selected_trace_suite},
            "traces": [],
        }
        status_box, progress_bar, results_placeholder, terminal_placeholders, metrics_placeholder = render_live_trace_progress(title=trace_report["title"], total_traces=len(selected_trace_names), show_terminal_output=show_live_terminal_output)
        completed_rows = []
        try:
            for index, trace_name in enumerate(selected_trace_names):
                compile_before_trace = execute_compile if index == 0 else execute_redeploy
                update_live_trace_progress(status_box=status_box, progress_bar=progress_bar, results_placeholder=results_placeholder, completed_items=completed_rows, total_traces=len(selected_trace_names), current_trace=trace_name, metrics_placeholder=metrics_placeholder)
                trace_entry = run_trace_with_report(
                    client=client, selected_contract=selected_contract, trace_name=trace_name, trace_data=contract_traces[trace_name],
                    execute_deploy=execute_deploy, execute_compile=execute_compile, initial_balance=initial_balance,
                    preferred_suite=selected_trace_suite, compile_before_trace=compile_before_trace, deploy_before_trace=execute_deploy,
                    show_live_terminal_output=show_live_terminal_output, phase_placeholders=terminal_placeholders
                )
                trace_report["traces"].append(trace_entry)
                es = summarize_trace_payload(trace_entry.get("phases", {}).get("execute", {}).get("payload"))
                completed_rows.append({"Trace": trace_name, "Status": trace_entry.get("status", "success"), "Steps": es["steps"], "Total cost": es["total_cost"], "Gas": es["total_gas"]})
                update_live_trace_progress(status_box=status_box, progress_bar=progress_bar, results_placeholder=results_placeholder, completed_items=completed_rows, total_traces=len(selected_trace_names), metrics_placeholder=metrics_placeholder)
            save_trace_report(trace_report)
            st.rerun()
        except Exception as e:
            trace_report["status"] = "error"
            trace_report["error"] = str(e)
            save_trace_report(trace_report)
            update_live_trace_progress(status_box=status_box, progress_bar=progress_bar, results_placeholder=results_placeholder, completed_items=completed_rows, total_traces=len(selected_trace_names), has_error=True, metrics_placeholder=metrics_placeholder)
            st.rerun()


def scenario_view():
    st.header("5. Test Scenario")
    scenarios_root = getScenariosRoot()
    if not scenarios_root.exists():
        st.error(f"Scenario folder not found: {scenarios_root}")
        return
    scenarios = scenarioScan(scenarios_root)
    if not scenarios:
        st.warning("No scenario files found in `contracts/Rosetta/scenarios`.")
        return
    selected_scenario = st.selectbox("Select a scenario to test:", options=scenarios, key="scenario_select")
    scenario_path = scenarios_root / f"{selected_scenario}.py"
    st.caption(f"Resolved path: {scenario_path}")
    if st.button("🧪 Run Scenario"):
        with st.spinner(f"Running {selected_scenario}..."):
            try:
                result = runScenario(str(scenario_path))
                st.success(f"Scenario '{selected_scenario}' executed successfully!")
                if result.stdout.strip():
                    st.code(result.stdout, language="text")
                else:
                    st.info("Scenario executed without console output.")
                if result.stderr.strip():
                    st.warning("Scenario stderr output")
                    st.code(result.stderr, language="text")
            except Exception as e:
                st.error("Error during scenario execution")
                st.code(str(e), language="text")


# ---------------------------------------------------------------------------
#  Sidebar & routing
# ---------------------------------------------------------------------------

st.sidebar.header("🔧 Configuration")
wallet_selection = st.sidebar.selectbox("Select an Account (from wallet.json):", options=["admin", "player1", "player2"])

st.sidebar.header("Features")
operation = st.sidebar.radio("Select an operation:", ("Compile", "Deploy", "Interact", "Execute Trace", "Test Scenario"))

client = get_client(wallet_selection)

if client or operation in {"Execute Trace", "Test Scenario"}:
    if operation == "Compile":
        compile_view(client)
    elif operation == "Deploy":
        deploy_view(client)
    elif operation == "Interact":
        interact_view(client)
    elif operation == "Execute Trace":
        trace_view(client)
    elif operation == "Test Scenario":
        scenario_view()
else:
    st.error("Cannot proceed without a valid Tezos client. Check the wallet selection and the `wallet.json` file.")
