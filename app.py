"""
app.py
Lexora entry point.
Run with: streamlit run app.py
"""

import streamlit as st

# ── Page config (must be the very first Streamlit call) ───────────────────────

st.set_page_config(
    page_title     = "Lexora — AI Language Coach",
    page_icon      = "📚",
    layout         = "wide",
    initial_sidebar_state = "collapsed",
)

# ── Navigation ────────────────────────────────────────────────────────────────
# Uses the modern st.navigation API (Streamlit ≥ 1.36).
# Pages are plain Python files — they don't need to be in a top-level pages/ folder.

pages = [
    st.Page("ui/pages/home.py",  title="Home",            icon="🏠", default=True),
    st.Page("ui/pages/ielts.py", title="IELTS Speaking",  icon="🎤"),
    st.Page("ui/pages/gre.py",   title="GRE Vocabulary",  icon="📖"),
]

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
