"""
ui/pages/home.py
Lexora home dashboard — shown when the app loads.
"""

import streamlit as st
from ui.components import inject_css

inject_css()

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:40px 20px 20px;">
  <p style="font-size:3rem;margin:0;">📚</p>
  <h1 style="font-size:2.6rem;margin:8px 0 6px;color:#1E293B;">Welcome to <span style="color:#2563EB;">Lexora</span></h1>
  <p style="color:#64748B;font-size:1.1rem;max-width:520px;margin:0 auto 32px;">
    Your AI-powered language learning companion for IELTS Speaking and GRE Vocabulary.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Module cards ──────────────────────────────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
<div class="module-card">
  <div class="icon">🎤</div>
  <h3>IELTS Speaking Coach</h3>
  <p>
    Practice all three parts of the IELTS Speaking test.
    Get AI-powered band scores, detailed feedback, and improvement tips.
  </p>
</div>
""", unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if st.button("Start Speaking Practice →", key="go_ielts", use_container_width=True, type="primary"):
        st.switch_page("ui/pages/ielts.py")

with col2:
    st.markdown("""
<div class="module-card">
  <div class="icon">📖</div>
  <h3>GRE Vocabulary Coach</h3>
  <p>
    Learn 5 new GRE words every day with meanings, mnemonics, and examples.
    Test yourself with AI-generated quizzes.
  </p>
</div>
""", unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if st.button("Start Vocabulary Practice →", key="go_gre", use_container_width=True, type="primary"):
        st.switch_page("ui/pages/gre.py")

# ── Feature strip ─────────────────────────────────────────────────────────────
st.markdown("<hr style='margin:36px 0 28px;border-color:#E2E8F0;'>", unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns(4)
features = [
    ("🤖", "AI Examiner", "Powered by Google Gemini"),
    ("📊", "Band Scores", "Official IELTS 0–9 scale"),
    ("🧠", "Smart Mnemonics", "Remember words faster"),
    ("✅", "Instant Quiz", "Test what you've learnt"),
]
for col, (icon, title, desc) in zip([f1, f2, f3, f4], features):
    with col:
        st.markdown(f"""
<div style="text-align:center;padding:16px 8px;">
  <p style="font-size:1.8rem;margin:0 0 6px;">{icon}</p>
  <p style="font-weight:700;color:#1E293B;margin:0 0 4px;font-size:.95rem;">{title}</p>
  <p style="color:#64748B;font-size:.83rem;margin:0;">{desc}</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<p style="text-align:center;color:#94A3B8;font-size:.8rem;margin-top:32px;">
  Lexora v1.0 &nbsp;·&nbsp; Built with Streamlit & Google Gemini
</p>
""", unsafe_allow_html=True)
