import json
from pathlib import Path

import streamlit as st

from contractUtils import (
    entrypointAnalyse,
    entrypointCall,
    callInfoResult,
    runScenario,
    getCompiledRoot,
)
from folderScan import folderScan, contractSuites, scenarioScan
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
    exportResult,
)
from trace_utils import (
    get_client,
    StreamlitTerminalWriter,
    run_with_terminal_output,
    render_terminal_output,
    st_export_result,
    get_trace_report_state,
    queue_trace_view,
    save_trace_report,
    save_trace_setup_config,
    get_last_trace_setup,
    restore_trace_setup,
    trace_phase_status_icon,
    render_phase_block,
    summarize_trace_payload,
    build_trace_result_rows,
    render_trace_selection_summary,
    render_execution_phase_payload,
    render_live_trace_progress,
    update_live_trace_progress,
    _render_live_phase_terminals,
    render_trace_report,
    create_trace_phase,
    execution_setup_auto,
    render_trace_execution,
    run_trace_with_report,
)

st.set_page_config(
    page_title="Tezos Smart Contract Toolchain",
    layout="centered"
)

st.title("🏗️ Tezos Smart Contract Toolchain")
st.caption("An interface to compile, deploy, interact with, and test Tezos smart contracts.")


# ---------------------------------------------------------------------------
#  Views (Streamlit UI wrapping main.py logic)
# ---------------------------------------------------------------------------


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
                        if st.checkbox("Save result to JSON"):
                            st_export_result(info_result)
                    except Exception as e:
                        st.error(f"Error during call: {e}")
            render_terminal_output("interact_terminal_output")
        except Exception as e:
            st.error(f"Unable to analyze contract entrypoints: {e}")


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
                try:
                    available_trace_contracts = resolveTraceContractCandidates(selectedContract=selected_contract, traceData=preview_trace_data)
                except FileNotFoundError as e:
                    st.warning(f"⚠️ Cannot deploy: no contract source found for **{selected_contract}**. {e}")
                    execute_deploy = False
                    available_trace_contracts = {}
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
