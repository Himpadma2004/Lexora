"""
ui/pages/ielts.py
Module A: IELTS Speaking Coach — Voice Input Edition
Flow: pick part → generate questions → record answer → AI evaluates → score cards
"""

import streamlit as st
from services.ai import generate_ielts_questions, evaluate_audio_answer
from services.db import save_result, load_history, clear_history
from ui.components import inject_css, page_header, band_score_display

inject_css()

# ── Extra CSS just for the voice recorder UI ──────────────────────────────────
st.markdown("""
<style>
/* Make the audio recorder widget look more intentional */
.stAudioInput > label { font-weight: 600; color: #1E293B; font-size: 1rem; }
.stAudioInput > div   { border-radius: 14px; border: 2px dashed #2563EB;
                         background: #EFF6FF; padding: 16px; }

/* Transcript box */
.transcript-box {
    background: #F8FAFC; border: 1px solid #E2E8F0;
    border-radius: 10px; padding: 14px 18px;
    font-size: .92rem; color: #334155; line-height: 1.6;
    margin-bottom: 14px;
}
</style>
""", unsafe_allow_html=True)

# ── State initialisation ──────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "ielts_part":      1,
        "ielts_questions": None,   # {topic, questions}
        "ielts_result":    None,   # evaluation dict (includes "transcript")
        "ielts_stage":     "select",  # select | record | result
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Page header ───────────────────────────────────────────────────────────────

page_header(
    "🎤 IELTS Speaking Coach",
    "Record your spoken answer and get instant AI-powered band score feedback."
)

# ════════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Choose a part
# ════════════════════════════════════════════════════════════════════════════════

if st.session_state.ielts_stage == "select":

    st.markdown("### Choose a Speaking Part")

    part_info = {
        1: ("👤 Part 1",    "Introduction & Interview",
            "Short personal questions about familiar topics. ~4–5 minutes."),
        2: ("🃏 Part 2",    "Individual Long Turn",
            "Speak for 1–2 minutes on a cue card topic. 1 minute to prepare."),
        3: ("💬 Part 3",    "Two-Way Discussion",
            "Abstract discussion questions linked to the Part 2 topic. ~4–5 minutes."),
    }

    c1, c2, c3 = st.columns(3)
    cols = {1: c1, 2: c2, 3: c3}

    for part, (label, subtitle, desc) in part_info.items():
        with cols[part]:
            st.markdown(f"""
<div class="lx-card" style="text-align:center;min-height:160px;">
  <p style="font-size:1.5rem;margin:0 0 4px;">{label}</p>
  <p style="font-weight:700;color:#1E293B;margin:0 0 8px;font-size:1rem;">{subtitle}</p>
  <p style="color:#64748B;font-size:.85rem;margin:0;">{desc}</p>
</div>
""", unsafe_allow_html=True)
            if st.button(f"Select Part {part}", key=f"sel_{part}", use_container_width=True):
                with st.spinner("Generating questions…"):
                    st.session_state.ielts_questions = generate_ielts_questions(part)
                st.session_state.ielts_part  = part
                st.session_state.ielts_stage = "record"
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Show questions + voice recorder
# ════════════════════════════════════════════════════════════════════════════════

elif st.session_state.ielts_stage == "record":

    part   = st.session_state.ielts_part
    q_data = st.session_state.ielts_questions
    qs     = q_data.get("questions", [])

    st.markdown(f"### Part {part} — {q_data.get('topic', '')}")

    # ── Display questions ─────────────────────────────────────────────────────
    for i, q in enumerate(qs, 1):
        is_cue_card_header = (part == 2 and i == 1)
        prefix  = "" if is_cue_card_header else f"{i}. "
        bold    = "font-weight:600;" if is_cue_card_header else ""
        st.markdown(f"""
<div class="lx-card" style="padding:14px 20px;">
  <p style="margin:0;font-size:.97rem;color:#1E293B;{bold}">{prefix}{q}</p>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── Tips per part ─────────────────────────────────────────────────────────
    tips = {
        1: "Speak naturally. Aim for 2–3 sentences per question. It's okay to use everyday language.",
        2: "Address all bullet points. Structure: introduce → develop → conclude. Speak for ~2 minutes.",
        3: "Give detailed, opinion-based answers. Use phrases like 'I believe…', 'On the other hand…'.",
    }
    st.info(f"💡 **Tip:** {tips[part]}")

    # ── Voice recorder ────────────────────────────────────────────────────────
    st.markdown("#### 🎙️ Record Your Answer")
    st.markdown(
        "<p style='color:#64748B;font-size:.88rem;margin-bottom:10px;'>"
        "Click the microphone to start recording. Click again to stop.</p>",
        unsafe_allow_html=True,
    )

    audio_value = st.audio_input(
        label="Record your spoken answer",
        label_visibility="collapsed",
        key="ielts_recorder",
    )

    # ── Action buttons ────────────────────────────────────────────────────────
    col_back, col_submit = st.columns([1, 3])

    with col_back:
        if st.button("← Back", use_container_width=True):
            # Clear recorder state and go back to part selection
            if "ielts_recorder" in st.session_state:
                del st.session_state["ielts_recorder"]
            st.session_state.ielts_stage = "select"
            st.rerun()

    with col_submit:
        submit_disabled = audio_value is None
        btn_label = "Submit for Evaluation →" if not submit_disabled else "⏺ Record your answer first"

        if st.button(btn_label, type="primary", use_container_width=True, disabled=submit_disabled):
            audio_bytes = audio_value.getvalue()
            mime_type   = getattr(audio_value, "type", "audio/webm")
            main_q      = qs[0] if qs else "IELTS Speaking"

            with st.spinner("🎧 We're listening and evaluating your answer…"):
                result = evaluate_audio_answer(part, main_q, audio_bytes, mime_type)

            st.session_state.ielts_result = result
            save_result("ielts", {
                "part":         part,
                "topic":        q_data.get("topic", ""),
                "overall_band": result.get("overall_band"),
            })
            # Clear recorder so it doesn't persist to next session
            if "ielts_recorder" in st.session_state:
                del st.session_state["ielts_recorder"]
            st.session_state.ielts_stage = "result"
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Evaluation result
# ════════════════════════════════════════════════════════════════════════════════

elif st.session_state.ielts_stage == "result":

    result = st.session_state.ielts_result

    # ── Transcript (what we heard) ────────────────────────────────────────
    transcript = result.get("transcript", "").strip()
    if transcript:
        st.markdown("#### 📝 What We Heard")
        st.markdown(
            f'<div class="transcript-box">{transcript}</div>',
            unsafe_allow_html=True,
        )

    # ── Score cards ───────────────────────────────────────────────────────────
    st.markdown("#### 📊 Your Evaluation")
    band_score_display(result)

    # ── Navigation buttons ────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎤 Try Another Question", use_container_width=True, type="primary"):
            st.session_state.ielts_stage  = "select"
            st.session_state.ielts_result = None
            st.rerun()
    with col2:
        if st.button("🔁 Re-record This Question", use_container_width=True):
            st.session_state.ielts_stage  = "record"
            st.session_state.ielts_result = None
            st.rerun()

    # ── History ───────────────────────────────────────────────────────────────
    history = load_history("ielts")
    if history:
        st.markdown("---")
        with st.expander(f"📈 My Past Results ({len(history)} sessions)", expanded=False):
            for entry in reversed(history[-10:]):
                ts    = entry.get("timestamp", "")[:16].replace("T", " ")
                band  = entry.get("overall_band", "–")
                topic = entry.get("topic", "General")
                p     = entry.get("part", "–")
                st.markdown(
                    f"- `{ts}` &nbsp; Part {p} — **{topic}** &nbsp;→&nbsp; Band **{band}**"
                )
            if st.button("Clear History", key="clr_hist"):
                clear_history("ielts")
                st.rerun()
