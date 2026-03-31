import streamlit as st

pg = st.navigation(
    {
        "MultiModular Toolchain": [
            st.Page("pages/Rosetta.py", title="MultiModular Toolchain", icon="🔀", default=True),
        ],
        "Single Toolchain": [
            st.Page("pages/Solana.py",   title="Solana",            icon="🌞"),
            st.Page("pages/Tezos.py",    title="Tezos",             icon="🔷"),
            st.Page("pages/Ethereum.py", title="Ethereum (EVM)",    icon="⚡"),
            st.Page("pages/Cardano.py",  title="Cardano",           icon="🧩"),
        ],
    }
)
pg.run()
