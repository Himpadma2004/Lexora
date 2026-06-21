"""
ui/pages/gre.py
Module B: GRE Vocabulary Coach
Generates 5 daily words and an MCQ quiz for each one.
"""

import streamlit as st
from services.ai import generate_gre_words, generate_word_quiz
from services.db import save_result, load_history, clear_history
from ui.components import inject_css, page_header, word_card

inject_css()

# ── State initialisation ──────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "gre_words": None,           # list of word dicts
        "gre_quizzes": {},           # {word_index: quiz_dict}
        "gre_answers": {},           # {word_index: chosen_index}
        "gre_tab": "words",          # "words" | "quiz"
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_state()

# ── Page header ───────────────────────────────────────────────────────────────

page_header(
    "📖 GRE Vocabulary Coach",
    "Learn 5 new high-frequency GRE words every day, then test yourself with a quiz."
)

# ── Load / refresh daily words ─────────────────────────────────────────────────

col_load, col_tab = st.columns([2, 3])

with col_load:
    if st.button("🔄 Generate Today's Words", type="primary", use_container_width=True):
        with st.spinner("Generating your daily GRE words…"):
            st.session_state.gre_words   = generate_gre_words(easy=2, medium=2, hard=1)
            st.session_state.gre_quizzes = {}
            st.session_state.gre_answers = {}

with col_tab:
    tab_choice = st.radio(
        "View",
        ["📚 Word Cards", "✅ Quiz Mode"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.session_state.gre_tab = "words" if "Word" in tab_choice else "quiz"

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ── No words loaded yet ───────────────────────────────────────────────────────

if st.session_state.gre_words is None:
    st.markdown("""
<div class="lx-card" style="text-align:center;padding:48px 24px;">
  <p style="font-size:2rem;margin:0 0 12px;">📖</p>
  <p style="color:#64748B;font-size:1rem;margin:0;">
    Click <strong>Generate Today's Words</strong> to load your daily GRE vocabulary set.
  </p>
</div>
""", unsafe_allow_html=True)
    st.stop()

words = st.session_state.gre_words

# ════════════════════════════════════════════════════════════════════════════════
# TAB A: Word Cards
# ════════════════════════════════════════════════════════════════════════════════

if st.session_state.gre_tab == "words":

    st.markdown(f"### Today's {len(words)} Words")

    for word_data in words:
        word_card(word_data)

    # Prompt user to take quiz
    st.markdown("""
<div class="lx-card" style="text-align:center;padding:20px;">
  <p style="margin:0;color:#64748B;">
    Done reading? Switch to <strong>Quiz Mode</strong> above to test yourself! 🎯
  </p>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB B: Quiz Mode
# ════════════════════════════════════════════════════════════════════════════════

else:
    st.markdown("### Quiz Yourself")
    st.markdown(
        "<p style='color:#64748B;font-size:.9rem;margin-bottom:20px;'>"
        "A quiz question for each word. Select your answer and check it.</p>",
        unsafe_allow_html=True,
    )

    all_correct = 0
    all_answered = 0

    for idx, word_data in enumerate(words):
        word  = word_data.get("word", f"Word {idx+1}")
        diff  = word_data.get("difficulty", "medium")
        diff_class = f"diff-{diff}"

        with st.expander(f"**{word}** — Quiz", expanded=(idx == 0)):

            # ── Load or generate quiz for this word ──────────────────────────
            if idx not in st.session_state.gre_quizzes:
                if st.button(f"Generate Quiz for '{word}'", key=f"gen_quiz_{idx}"):
                    with st.spinner(f"Creating quiz for {word}…"):
                        quiz = generate_word_quiz(
                            word    = word,
                            meaning = word_data.get("meaning", ""),
                            example = word_data.get("example", ""),
                        )
                        st.session_state.gre_quizzes[idx] = quiz
                    st.rerun()
                continue  # nothing more to show until quiz is generated

            quiz = st.session_state.gre_quizzes[idx]

            # ── Show question ─────────────────────────────────────────────────
            st.markdown(f"**{quiz.get('question','')}**")

            options = quiz.get("options", [])
            chosen  = st.session_state.gre_answers.get(idx)

            if chosen is None:
                # Present radio for unanswered quiz
                choice = st.radio(
                    "Choose your answer",
                    options=range(len(options)),
                    format_func=lambda i: f"{chr(65+i)}. {options[i]}",
                    key=f"radio_{idx}",
                    label_visibility="collapsed",
                )
                if st.button("Check Answer", key=f"check_{idx}", type="primary"):
                    st.session_state.gre_answers[idx] = choice
                    # Save to history
                    is_correct = (choice == quiz.get("correct_index", -1))
                    save_result("gre", {"word": word, "correct": is_correct})
                    st.rerun()
            else:
                # Show result
                correct_idx = quiz.get("correct_index", -1)
                is_correct  = (chosen == correct_idx)
                all_answered += 1
                if is_correct:
                    all_correct += 1

                for i, opt in enumerate(options):
                    if i == correct_idx:
                        st.success(f"✓ {chr(65+i)}. {opt}")
                    elif i == chosen and not is_correct:
                        st.error(f"✗ {chr(65+i)}. {opt}")
                    else:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;{chr(65+i)}. {opt}")

                explanation = quiz.get("explanation", "")
                if explanation:
                    st.markdown(f"""
<div class="lx-card" style="background:#EFF6FF;border-color:#BFDBFE;padding:12px 16px;">
  <p style="margin:0;font-size:.9rem;color:#1e3a8a;">
    💡 <strong>Explanation:</strong> {explanation}
  </p>
</div>
""", unsafe_allow_html=True)

                if st.button("Retry", key=f"retry_{idx}"):
                    del st.session_state.gre_answers[idx]
                    st.rerun()

    # ── Session score summary ─────────────────────────────────────────────────
    if all_answered > 0:
        pct = int((all_correct / all_answered) * 100)
        colour = "#059669" if pct >= 70 else "#D97706" if pct >= 40 else "#DC2626"
        st.markdown(f"""
<div class="lx-card" style="text-align:center;padding:20px;">
  <p style="font-size:.85rem;color:#64748B;margin-bottom:6px;">SESSION SCORE</p>
  <p style="font-size:2rem;font-weight:800;color:{colour};margin:0;">
    {all_correct} / {all_answered} &nbsp; ({pct}%)
  </p>
</div>
""", unsafe_allow_html=True)

# ── History sidebar ───────────────────────────────────────────────────────────
history = load_history("gre")
if history:
    with st.sidebar:
        st.markdown("### 📈 GRE History")
        total   = len(history)
        correct = sum(1 for h in history if h.get("correct"))
        pct     = int((correct / total) * 100) if total else 0
        st.metric("Words Attempted", total)
        st.metric("Accuracy", f"{pct}%")
        if st.button("Clear GRE History"):
            clear_history("gre")
            st.rerun()
