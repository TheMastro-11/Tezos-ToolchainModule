import os
import sys

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_base_dir)
sys.path.append(os.path.join(_base_dir, "modules"))
sys.path.append(os.path.join(_base_dir, "modules", "Solana_module"))

from Rosetta_utils import upload_trace_file, select_trace_file
import streamlit as st

st.title("🌹𓂀 Welcome to Rosetta Smart Contract")
st.markdown("""
This application lets you easily manage your **Smart Contract toolchains**.

### Quick Start Guide:
1. Use the **sidebar** on the left to select the toolchain you want to use:
   - **Solana**, **Tezos**, **Ethereum (EVM)**, **Cardano** — accessible under **Single Toolchain**
2. Each toolchain page provides actions like wallet management, compile & deploy, and data insertion.
3. Use the tabs below to select or upload an **execution trace** and run it across one or more toolchains.
""")

tab_select, tab_upload = st.tabs(["📂 Select Trace", "⬆️ Upload Trace"])
with tab_select:
    select_trace_file()
with tab_upload:
    upload_trace_file()

st.markdown("---")
st.write("© 2025 - Rosetta SC")
