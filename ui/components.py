"""
ui/components.py
Shared CSS and HTML component helpers used across all Lexora pages.
Call inject_css() once at the top of each page.
"""

import streamlit as st

# ── Brand colours (kept in one place for easy restyling) ─────────────────────
PRIMARY   = "#2563EB"
PRIMARY_L = "#EFF6FF"   # light tint
SUCCESS   = "#059669"
SUCCESS_L = "#ECFDF5"
WARNING   = "#D97706"
WARNING_L = "#FFFBEB"
DANGER    = "#DC2626"
DANGER_L  = "#FEF2F2"
TEXT_MAIN = "#1E293B"
TEXT_SUB  = "#64748B"
BORDER    = "#E2E8F0"


def inject_css() -> None:
    """Inject global Lexora CSS once per page render."""
    st.markdown(f"""
<style>
/* ── Page & typography ───────────────────────────────────── */
.stApp {{ background: #F8FAFC; }}

h1, h2, h3 {{ color: {TEXT_MAIN}; font-weight: 700; }}

/* ── Generic card ────────────────────────────────────────── */
.lx-card {{
    background: #fff;
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 24px 28px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
    margin-bottom: 18px;
}}

/* ── Module card (home page) ─────────────────────────────── */
.module-card {{
    background: #fff;
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 32px 28px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,.07);
    transition: box-shadow .2s;
    height: 100%;
}}
.module-card:hover {{ box-shadow: 0 6px 20px rgba(37,99,235,.15); }}
.module-card .icon  {{ font-size: 2.6rem; margin-bottom: 12px; }}
.module-card h3     {{ font-size: 1.3rem; color: {TEXT_MAIN}; margin: 0 0 8px; }}
.module-card p      {{ color: {TEXT_SUB}; font-size: 0.95rem; margin: 0; }}

/* ── Band score badge ────────────────────────────────────── */
.band-badge {{
    display: inline-block;
    background: {PRIMARY};
    color: #fff;
    font-size: 2.4rem;
    font-weight: 800;
    padding: 14px 28px;
    border-radius: 14px;
    letter-spacing: -0.5px;
    line-height: 1;
}}

/* ── Criterion score pill ────────────────────────────────── */
.score-pill {{
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    background: {PRIMARY_L};
    border: 1px solid {PRIMARY};
    border-radius: 12px;
    padding: 10px 18px;
    min-width: 90px;
    margin: 4px;
}}
.score-pill .label {{ font-size: 0.72rem; color: {TEXT_SUB}; font-weight: 600;
                      text-transform: uppercase; letter-spacing: .5px; }}
.score-pill .value {{ font-size: 1.5rem; font-weight: 800; color: {PRIMARY}; }}

/* ── Feedback lists ──────────────────────────────────────── */
.fb-list {{ list-style: none; padding: 0; margin: 0; }}
.fb-list li {{
    padding: 7px 12px 7px 36px;
    border-radius: 8px;
    margin-bottom: 6px;
    font-size: 0.92rem;
    position: relative;
}}
.fb-list li::before {{
    position: absolute; left: 10px; top: 8px; font-size: 1rem;
}}
.fb-strength {{ background: {SUCCESS_L}; color: #065f46; }}
.fb-strength::before {{ content: "✓"; color: {SUCCESS}; }}
.fb-weakness {{ background: {WARNING_L}; color: #92400e; }}
.fb-weakness::before {{ content: "!"; color: {WARNING}; }}
.fb-suggestion {{ background: {PRIMARY_L}; color: #1e3a8a; }}
.fb-suggestion::before {{ content: "→"; color: {PRIMARY}; }}

/* ── Word card ───────────────────────────────────────────── */
.word-card {{
    background: #fff;
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
}}
.word-card .word-title {{
    font-size: 1.7rem; font-weight: 800; color: {TEXT_MAIN}; margin: 0;
}}
.word-card .word-meta {{
    color: {TEXT_SUB}; font-size: 0.88rem; margin: 2px 0 12px;
}}
.word-card .meaning  {{ font-size: 1rem; color: {TEXT_MAIN}; margin-bottom: 8px; }}
.word-card .example  {{ font-style: italic; color: {TEXT_SUB}; font-size: 0.9rem;
                        border-left: 3px solid {PRIMARY}; padding-left: 10px; }}
.word-card .mnemonic {{
    background: {WARNING_L}; border-radius: 8px; padding: 10px 14px;
    font-size: 0.88rem; color: #78350f; margin-top: 12px;
}}

/* ── Chip (synonym / antonym) ────────────────────────────── */
.chip {{
    display: inline-block;
    background: #F1F5F9;
    color: {TEXT_MAIN};
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.82rem;
    margin: 2px 3px;
    border: 1px solid {BORDER};
}}
.chip-syn {{ background: {SUCCESS_L}; color: #065f46; border-color: #a7f3d0; }}
.chip-ant {{ background: {DANGER_L};  color: #991b1b; border-color: #fca5a5; }}

/* ── Difficulty badge ────────────────────────────────────── */
.diff-easy   {{ background:{SUCCESS_L}; color:{SUCCESS}; border:1px solid #a7f3d0; 
                padding:2px 10px; border-radius:20px; font-size:.78rem; font-weight:600; }}
.diff-medium {{ background:{WARNING_L}; color:{WARNING}; border:1px solid #fcd34d;
                padding:2px 10px; border-radius:20px; font-size:.78rem; font-weight:600; }}
.diff-hard   {{ background:{DANGER_L};  color:{DANGER};  border:1px solid #fca5a5;
                padding:2px 10px; border-radius:20px; font-size:.78rem; font-weight:600; }}

/* ── Quiz option buttons ─────────────────────────────────── */
.quiz-correct   {{ color: {SUCCESS} !important; font-weight: 700 !important; }}
.quiz-incorrect {{ color: {DANGER}  !important; font-weight: 700 !important; }}

/* ── Page header strip ───────────────────────────────────── */
.page-header {{
    background: linear-gradient(135deg, {PRIMARY} 0%, #1d4ed8 100%);
    color: #fff;
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 28px;
}}
.page-header h1 {{ color: #fff; margin: 0 0 6px; font-size: 1.8rem; }}
.page-header p  {{ color: rgba(255,255,255,.85); margin: 0; font-size: 0.95rem; }}

/* ── Hide Streamlit default footer & menu ────────────────── */
#MainMenu, footer {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)


# ── Reusable HTML helpers ─────────────────────────────────────────────────────

def page_header(title: str, subtitle: str) -> None:
    """Render the blue gradient page header."""
    st.markdown(f"""
<div class="page-header">
  <h1>{title}</h1>
  <p>{subtitle}</p>
</div>
""", unsafe_allow_html=True)


def card(content_html: str) -> None:
    """Wrap arbitrary HTML in a Lexora card."""
    st.markdown(f'<div class="lx-card">{content_html}</div>', unsafe_allow_html=True)


def band_score_display(result: dict) -> None:
    """
    Render the full IELTS score card from an evaluation result dict.
    Expected keys: overall_band, fluency, grammar, vocabulary, coherence,
                   strengths, weaknesses, suggestions
    """
    overall = result.get("overall_band", 0)
    criteria = {
        "Fluency":     result.get("fluency", 0),
        "Grammar":     result.get("grammar", 0),
        "Vocabulary":  result.get("vocabulary", 0),
        "Coherence":   result.get("coherence", 0),
    }

    # Overall band badge + criterion pills
    pills_html = "".join(
        f'<span class="score-pill"><span class="label">{k}</span>'
        f'<span class="value">{v}</span></span>'
        for k, v in criteria.items()
    )

    st.markdown(f"""
<div class="lx-card">
  <p style="font-size:.85rem;color:#64748b;font-weight:600;text-transform:uppercase;
             letter-spacing:.5px;margin-bottom:10px;">Estimated Band Score</p>
  <span class="band-badge">{overall}</span>
  <div style="margin-top:16px;">{pills_html}</div>
</div>
""", unsafe_allow_html=True)

    # Three feedback columns
    col1, col2, col3 = st.columns(3)

    def _list(items: list, css_class: str) -> str:
        lis = "".join(f'<li class="fb-list {css_class}">{i}</li>' for i in items)
        return f'<ul class="fb-list">{lis}</ul>'

    with col1:
        st.markdown("**✅ Strengths**")
        st.markdown(_list(result.get("strengths", []), "fb-strength"), unsafe_allow_html=True)
    with col2:
        st.markdown("**⚠️ Weaknesses**")
        st.markdown(_list(result.get("weaknesses", []), "fb-weakness"), unsafe_allow_html=True)
    with col3:
        st.markdown("**💡 Suggestions**")
        st.markdown(_list(result.get("suggestions", []), "fb-suggestion"), unsafe_allow_html=True)


def word_card(word_data: dict) -> None:
    """Render a full GRE word card from a word dict."""
    diff = word_data.get("difficulty", "medium")
    diff_class = f"diff-{diff}"

    syn_chips = "".join(
        f'<span class="chip chip-syn">{s}</span>'
        for s in word_data.get("synonyms", [])
    )
    ant_chips = "".join(
        f'<span class="chip chip-ant">{a}</span>'
        for a in word_data.get("antonyms", [])
    )

    st.markdown(f"""
<div class="word-card">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div>
      <p class="word-title">{word_data.get('word','')}</p>
      <p class="word-meta">
        <em>{word_data.get('pos','')}</em> &nbsp;·&nbsp;
        {word_data.get('ipa','')} &nbsp;·&nbsp;
        <strong>{word_data.get('pronunciation','')}</strong>
      </p>
    </div>
    <span class="{diff_class}">{diff.capitalize()}</span>
  </div>

  <p class="meaning"><strong>Meaning:</strong> {word_data.get('meaning','')}</p>
  <p style="font-size:.9rem;color:#475569;margin-bottom:10px;">
    {word_data.get('simple_explanation','')}
  </p>
  <p class="example">"{word_data.get('example','')}"</p>

  <div class="mnemonic">💡 <strong>Mnemonic:</strong> {word_data.get('mnemonic','')}</div>

  <div style="margin-top:14px;">
    <span style="font-size:.8rem;font-weight:600;color:#64748b;">SYNONYMS &nbsp;</span>
    {syn_chips}
  </div>
  <div style="margin-top:6px;">
    <span style="font-size:.8rem;font-weight:600;color:#64748b;">ANTONYMS &nbsp;</span>
    {ant_chips}
  </div>
</div>
""", unsafe_allow_html=True)
