"""
trace_utils.py – Streamlit UI helpers and trace execution logic shared between
dapp.py (Tezos toolchain) and Rosetta_utils.py (Rosetta SC home page).
"""
import contextlib
import io
import json
from pathlib import Path

import streamlit as st
from pytezos import pytezos

from contractUtils import compileContract
from main import (
    getContractsRoot,
    parseContractId,
    resolveTraceContractId,
    deployContract,
    normalizeContractToken,
    exportResult,
    exportTraceResult,
    executionSetupCsv,
    executionSetupJson,
)


# ---------------------------------------------------------------------------
#  Client
# ---------------------------------------------------------------------------

def get_client(wallet_id):
    try:
        with open(Path(__file__).resolve().parent / "wallet.json", "r", encoding="utf-8") as f:
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


# ---------------------------------------------------------------------------
#  Terminal writer
# ---------------------------------------------------------------------------

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
#  Trace report / session helpers
# ---------------------------------------------------------------------------

def get_trace_report_state():
    return st.session_state.get("trace_report_data")


def queue_trace_view(target_view):
    st.session_state["trace_view_page_target"] = target_view


def save_trace_report(report_data):
    st.session_state["trace_report_data"] = report_data
    queue_trace_view("Trace Report")


def save_trace_setup_config(config_data):
    st.session_state["last_trace_setup"] = config_data


def get_last_trace_setup():
    return st.session_state.get("last_trace_setup")


def restore_trace_setup():
    st.session_state["_rosetta_restore_pending"] = True
    queue_trace_view("Execution Setup")


# ---------------------------------------------------------------------------
#  Trace report rendering
# ---------------------------------------------------------------------------

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


def render_trace_selection_summary(selected_contract, execution_mode, trace_names, execute_deploy,
                                   execute_compile, execute_redeploy, initial_balance,
                                   selected_trace_suite, show_live_terminal_output):
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
            "Step": step_name,
            "Contract": step_data.get("contract", "-"),
            "Entrypoint": step_data.get("entryPoint", "-"),
            "Hash": step_data.get("Hash", "-"),
            "TotalCost": step_data.get("TotalCost", 0),
            "BakerFee": step_data.get("BakerFee", 0),
            "Storage": step_data.get("Storage", 0),
            "Gas": step_data.get("Gas", 0),
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


def update_live_trace_progress(status_box, progress_bar, results_placeholder, completed_items,
                               total_traces, current_trace=None, has_error=False, metrics_placeholder=None):
    completed_count = len(completed_items)
    progress_bar.progress(completed_count / total_traces if total_traces else 0.0)
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
    header_col1, header_col2, header_col3 = st.columns([3, 2, 1])
    with header_col1:
        status = report.get("status", "success")
        if status == "success":
            st.success(report.get("title", "Trace execution completed."))
        else:
            st.error(report.get("title", "Trace execution failed."))
    last_setup = get_last_trace_setup()
    with header_col2:
        if last_setup and st.button("🔄 Riesegui Ultimo Setup",
                                    help="Torna all'Execution Setup con la stessa configurazione",
                                    use_container_width=True):
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
                    pd_data = phases.get(pn)
                    if pd_data is not None:
                        sr.append({"Phase": pn.title(), "Status": pd_data.get("status", "-"),
                                   "Details": pd_data.get("details", "-")})
                if sr:
                    st.dataframe(sr, use_container_width=True, hide_index=True)
                else:
                    st.info("No phase summary available.")
            for ti, pn in enumerate(["compile", "deploy", "execute"], start=1):
                with phase_tabs[ti]:
                    pd_data = phases.get(pn)
                    if pd_data is None:
                        st.info(f"{pn.title()} phase not available for this trace.")
                    else:
                        render_phase_block(pn, pd_data)
                        if pn == "execute":
                            render_execution_phase_payload(pd_data.get("payload"))
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
#  Execution helpers
# ---------------------------------------------------------------------------

def execution_setup_auto(contract, rows):
    if isinstance(rows, dict) and "trace_execution" in rows:
        return executionSetupJson(contractId=contract, traceData=rows)
    return executionSetupCsv(contractId=contract, rows=rows)


def render_trace_execution(trace_name, trace_data, contract_name, render_live=False, output_placeholder=None):
    with st.spinner(f"Executing trace '{trace_name}'..."):
        results, terminal_output = run_with_terminal_output(
            lambda: execution_setup_auto(contract=trace_name, rows=trace_data),
            f"trace_terminal_output_{contract_name}_{trace_name}",
            render_live=render_live,
            output_placeholder=output_placeholder,
        )
        exportTraceResult(traceData=trace_data, resultsDict=results, traceName=trace_name)
        return results, terminal_output


def run_trace_with_report(client, selected_contract, trace_name, trace_data, execute_deploy,
                          execute_compile, initial_balance, preferred_suite, compile_before_trace,
                          deploy_before_trace, show_live_terminal_output=False, phase_placeholders=None):
    trace_report = {"trace_name": trace_name, "status": "success", "phases": {}}
    try:
        if execute_deploy:
            contract_id = resolveTraceContractId(selected_contract, trace_data, preferred_suite)

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

            deploy_results, deploy_output = run_with_terminal_output(
                lambda: deployContract(client=client, contractId=contract_id, initialBalance=initial_balance),
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
            trace_report["phases"]["deploy"] = create_trace_phase(
                status="skipped", details="Deploy step disabled for this execution."
            )

        execute_output = st.session_state.get(
            f"trace_terminal_output_{selected_contract}_{trace_name}", ""
        )
        try:
            results, execute_output = render_trace_execution(
                trace_name=trace_name,
                trace_data=trace_data,
                contract_name=selected_contract,
                render_live=show_live_terminal_output,
                output_placeholder=(phase_placeholders or {}).get("execute"),
            )
        except Exception as exec_exc:
            execute_output = st.session_state.get(
                f"trace_terminal_output_{selected_contract}_{trace_name}", ""
            )
            trace_report["status"] = "error"
            trace_report["phases"]["execute"] = create_trace_phase(
                status="error",
                output=execute_output,
                details=f"Trace `{trace_name}` failed during execution: {exec_exc}",
            )
            raise RuntimeError(str(exec_exc)) from exec_exc

        trace_report["phases"]["execute"] = create_trace_phase(
            status="success",
            output=execute_output,
            details=f"Executed trace `{trace_name}`.",
            payload=results,
        )
        return trace_report
    except RuntimeError:
        raise
    except Exception as exc:
        trace_report["status"] = "error"
        if execute_deploy and deploy_before_trace and "deploy" not in trace_report["phases"]:
            trace_report["phases"]["deploy"] = create_trace_phase(
                status="error", details="Deploy step failed before execution.", output=str(exc)
            )
        elif "execute" not in trace_report["phases"]:
            trace_report["phases"]["execute"] = create_trace_phase(
                status="error",
                details=f"Trace `{trace_name}` failed during execution.",
                output=str(exc),
            )
        raise RuntimeError(str(exc)) from exc
