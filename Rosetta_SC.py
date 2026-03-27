import os
import sys
import requests
import json
import asyncio

_base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_base_dir)
sys.path.append(os.path.join(_base_dir, "modules"))
sys.path.append(os.path.join(_base_dir, "modules", "Solana_module"))

from Solana_module.solana_module.anchor_module.dapp_automatic_insertion_manager import  fetch_initialized_programs , build_table
from Rosetta_utils import upload_trace_file
import streamlit as st
import pandas as pd

# ==============================
# Import moduli Solana
# ==============================




TRACES_PATH = os.path.join("Solana_module", "solana_module", "anchor_module", "execution_traces")


# ==============================
# Configurazione pagina
# ==============================
st.set_page_config(
    page_title="Rosetta SC - Home",
    page_icon="🌹",
    layout="wide"
)

# ==============================
# Sidebar
# ==============================


# ==============================
# Titolo e descrizione
# ==============================s
st.title("🌹𓂀 Welcome to Rosetta Smart Contract")
st.markdown("""
This application lets you easily manage your **Smart Contract toolchains**.

### Quick Start Guide:
1. Use the **sidebar** on the left to select the toolchain you want to use:
   - **Solana** to work with Solana smart contracts.
   - **Tezos** to work with Tezos smart contracts.
   - **Ethereum (EVM)** to work with Ethereum smart contracts.
   - **Cardano** to work with Cardano smart contracts.
2. Each toolchain page provides actions like wallet management, compile & deploy, and data insertion.
3. After deploying a program, you can use the **Automatic Data Insertion** feature (available in each toolchain) to test it with predefined execution traces. Results will be printed below after execution.
""")

upload_trace_file()
# ==============================
# Footer
# ==============================
st.markdown("---")
st.write("© 2025 - Rosetta SC")
