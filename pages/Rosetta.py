import os
import sys

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_base_dir)
sys.path.append(os.path.join(_base_dir, "modules"))
sys.path.append(os.path.join(_base_dir, "modules", "Solana_module"))

from Rosetta_utils import upload_trace_file, select_trace_file
import streamlit as st

st.title("🔀 MultiModular Toolchain")
st.markdown("""
A unified platform to **compile, deploy, and interact** with smart contracts across multiple blockchains from a single interface.

### Quick Start Guide:
1. Use the **sidebar** on the left to access individual toolchains:
   - **Solana**,
   - **Tezos**,
   - **Ethereum (EVM)**,
   - **Cardano** — accessible under **Single Toolchain**
2. Each toolchain page provides: wallet management, compile & deploy, and interactive data insertion.
3. Use the tabs below to select or upload an **execution trace** and run it simultaneously across one or more blockchains.
""")

tab_select, tab_upload = st.tabs(["📂 Select Trace", "⬆️ Upload Trace"])
with tab_select:
    select_trace_file()
with tab_upload:
    upload_trace_file()

st.markdown("---")
st.write("© 2025 - MultiModular Toolchain")
