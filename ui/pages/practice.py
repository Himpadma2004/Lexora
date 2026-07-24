"""
ui/pages/practice.py
Lexora Practice Mode — upload PDFs/images, OCR them, clean the text, and
turn the material into GRE-style multiple-choice practice.
"""

from __future__ import annotations

import ast
import hashlib
import operator as op
import time

import streamlit as st

from services.ai import generate_practice_set_from_text
from services.db import clear_history, load_history, save_result
from services.ocr import extract_text_from_sources
from ui.components import inject_css, page_header

inject_css()

st.markdown(
	"""
<style>
.practice-card {
	background: #fff;
	border: 1px solid #E2E8F0;
	border-radius: 16px;
	padding: 22px 24px;
	box-shadow: 0 1px 4px rgba(0,0,0,.06);
	margin-bottom: 18px;
}
.practice-meta {
	color: #64748B;
	font-size: .88rem;
	margin-bottom: 6px;
}
.practice-question {
	font-size: 1.05rem;
	font-weight: 650;
	color: #1E293B;
	line-height: 1.55;
	margin: 0 0 12px;
}
.practice-pill {
	display: inline-block;
	border-radius: 999px;
	padding: 3px 10px;
	font-size: .76rem;
	font-weight: 700;
	margin-left: 6px;
}
.practice-pill.easy { background:#ECFDF5; color:#059669; }
.practice-pill.medium { background:#FFFBEB; color:#D97706; }
.practice-pill.hard { background:#FEF2F2; color:#DC2626; }
.practice-status-dot {
	width: 12px; height: 12px; border-radius: 50%; display: inline-block;
	margin-right: 6px; vertical-align: middle; border: 1px solid rgba(15,23,42,.12);
}
.practice-status-dot.current { background:#2563EB; }
.practice-status-dot.answered { background:#059669; }
.practice-status-dot.skipped { background:#D97706; }
.practice-status-dot.flagged { background:#7C3AED; }
.practice-status-dot.pending { background:#CBD5E1; }
.practice-lock {
	background: linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 100%);
	border: 1px solid #BFDBFE;
	border-radius: 18px;
	padding: 28px;
	text-align: center;
	box-shadow: 0 10px 30px rgba(37,99,235,.08);
}
.calc-display {
	background: #0F172A;
	color: #F8FAFC;
	border-radius: 12px;
	padding: 12px 14px;
	font-size: 1.1rem;
	font-weight: 700;
	letter-spacing: .3px;
	overflow-x: auto;
}
.calc-grid button {
	width: 100%;
}
</style>
""",
	unsafe_allow_html=True,
)

TIMER_MODES = {
	"Just practice": 240,
	"Improvement practice": 165,
	"Test mode": 105,
}

BACKEND_OPTIONS = {
	"Offline local LLM (LM Studio)": "local",
	"Groq API (OpenAI-compatible)": "groq",
}


def _init_state() -> None:
	defaults = {
		"practice_stage": "setup",
		"practice_sources": [],
		"practice_provider_label": "Offline local LLM (LM Studio)",
		"practice_timer_label": "Test mode",
		"practice_set": None,
		"practice_current_idx": 0,
		"practice_answers": {},
		"practice_results": {},
		"practice_flags": {},
		"practice_question_started_at": None,
		"practice_timer_limit": TIMER_MODES["Test mode"],
		"practice_paused": False,
		"practice_pause_started_at": None,
		"practice_pause_total": 0.0,
		"practice_saved": False,
		"practice_calc_expr": "0",
		"practice_calc_memory": 0.0,
		"practice_session_started_at": None,
	}
	for key, value in defaults.items():
		if key not in st.session_state:
			st.session_state[key] = value


_init_state()


def _fmt_seconds(value: float | int) -> str:
	seconds = max(0, int(round(value)))
	minutes, remaining = divmod(seconds, 60)
	return f"{minutes:02d}:{remaining:02d}"


def _sha1(data: bytes) -> str:
	return hashlib.sha1(data).hexdigest()


def _source_key(name: str, data: bytes) -> str:
	return f"{name}:{len(data)}:{_sha1(data)}"


def _add_sources(files, kind: str) -> None:
	for item in files or []:
		content = item.getvalue()
		key = _source_key(item.name, content)
		exists = any(source["key"] == key for source in st.session_state.practice_sources)
		if exists:
			continue
		st.session_state.practice_sources.append(
			{
				"key": key,
				"name": item.name,
				"bytes": content,
				"mime_type": getattr(item, "type", None),
				"kind": kind,
				"size": len(content),
			}
		)


def _remove_source(key: str) -> None:
	st.session_state.practice_sources = [s for s in st.session_state.practice_sources if s["key"] != key]


def _start_question_timer() -> None:
	st.session_state.practice_question_started_at = time.time()
	st.session_state.practice_pause_started_at = None
	st.session_state.practice_pause_total = 0.0
	st.session_state.practice_paused = False


def _current_elapsed() -> float:
	started = st.session_state.practice_question_started_at
	if started is None:
		return 0.0

	elapsed = time.time() - started - float(st.session_state.practice_pause_total or 0.0)
	if st.session_state.practice_paused and st.session_state.practice_pause_started_at is not None:
		elapsed -= max(0.0, time.time() - st.session_state.practice_pause_started_at)
	return max(0.0, elapsed)


def _remaining_seconds() -> float:
	return float(st.session_state.practice_timer_limit) - _current_elapsed()


def _question_stats(questions: list[dict]) -> dict:
	counts = {"easy": 0, "medium": 0, "hard": 0}
	for item in questions:
		diff = (item.get("difficulty") or "medium").lower()
		if diff in counts:
			counts[diff] += 1
	return counts


def _safe_eval(expr: str):
	allowed = {
		ast.Add: op.add,
		ast.Sub: op.sub,
		ast.Mult: op.mul,
		ast.Div: op.truediv,
		ast.Pow: op.pow,
		ast.Mod: op.mod,
		ast.USub: op.neg,
		ast.UAdd: op.pos,
	}

	def _eval(node):
		if isinstance(node, ast.Expression):
			return _eval(node.body)
		if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
			return node.value
		if isinstance(node, ast.Num):  # pragma: no cover - older AST nodes
			return node.n
		if isinstance(node, ast.BinOp) and type(node.op) in allowed:
			return allowed[type(node.op)](_eval(node.left), _eval(node.right))
		if isinstance(node, ast.UnaryOp) and type(node.op) in allowed:
			return allowed[type(node.op)](_eval(node.operand))
		raise ValueError("Unsupported expression")

	return _eval(ast.parse(expr, mode="eval"))


def _calc_press(token: str) -> None:
	expr = st.session_state.practice_calc_expr
	if token == "C":
		expr = "0"
	elif token == "⌫":
		expr = expr[:-1] if len(expr) > 1 else "0"
	elif token == "=":
		try:
			expr = str(round(float(_safe_eval(expr)), 8))
		except Exception:
			expr = "Error"
	elif token == "MC":
		st.session_state.practice_calc_memory = 0.0
	elif token == "MR":
		expr = str(st.session_state.practice_calc_memory)
	elif token == "M+":
		try:
			st.session_state.practice_calc_memory += float(_safe_eval(expr))
		except Exception:
			pass
	elif token == "M-":
		try:
			st.session_state.practice_calc_memory -= float(_safe_eval(expr))
		except Exception:
			pass
	else:
		if expr == "0" and token not in ".)" and token not in "+-*/%":
			expr = token
		else:
			expr += token
	st.session_state.practice_calc_expr = expr


def _render_calculator() -> None:
	st.markdown("### 🧮 Calculator")
	st.markdown(f'<div class="calc-display">{st.session_state.practice_calc_expr}</div>', unsafe_allow_html=True)

	rows = [
		["MC", "MR", "M+", "M-"],
		["7", "8", "9", "/"],
		["4", "5", "6", "*"],
		["1", "2", "3", "-"],
		["0", ".", "⌫", "+"],
		["(", ")", "%", "="] ,
	]

	for row in rows:
		cols = st.columns(len(row), gap="small")
		for col, token in zip(cols, row):
			with col:
				st.button(token, key=f"calc_{token}_{row.index(token)}_{id(row)}", use_container_width=True, on_click=_calc_press, args=(token,))


def _render_source_queue() -> None:
	if not st.session_state.practice_sources:
		st.info("Add at least one PDF, image, or camera capture to begin.")
		return

	st.markdown("#### Source queue")
	for source in st.session_state.practice_sources:
		left, right = st.columns([5, 1])
		with left:
			st.markdown(
				f"""
<div class="practice-card" style="margin-bottom:10px;padding:14px 16px;">
  <p style="margin:0 0 4px;font-weight:700;color:#1E293B;">{source['name']}</p>
  <p style="margin:0;color:#64748B;font-size:.82rem;">
	{source['kind'].title()} &nbsp;·&nbsp; {round(source['size'] / 1024, 1)} KB
  </p>
</div>
""",
				unsafe_allow_html=True,
			)
		with right:
			st.button("Remove", key=f"rm_{source['key']}", use_container_width=True, on_click=_remove_source, args=(source["key"],))


def _set_quiz_session(practice_set: dict, timer_label: str) -> None:
	st.session_state.practice_set = practice_set
	st.session_state.practice_stage = "quiz"
	st.session_state.practice_current_idx = 0
	st.session_state.practice_answers = {}
	st.session_state.practice_results = {}
	st.session_state.practice_flags = {}
	st.session_state.practice_saved = False
	st.session_state.practice_timer_limit = TIMER_MODES[timer_label]
	st.session_state.practice_session_started_at = time.time()
	_start_question_timer()


def _advance_question(step: int = 1) -> None:
	total = len(st.session_state.practice_set.get("questions", [])) if st.session_state.practice_set else 0
	st.session_state.practice_current_idx = max(0, min(total, st.session_state.practice_current_idx + step))
	if st.session_state.practice_current_idx >= total:
		st.session_state.practice_stage = "result"
		return
	_start_question_timer()


def _store_answer(idx: int, choice: int, skipped: bool = False) -> None:
	questions = st.session_state.practice_set.get("questions", []) if st.session_state.practice_set else []
	if idx >= len(questions):
		return

	question = questions[idx]
	correct_index = int(question.get("correct_index", -1))
	correct = (choice == correct_index) and not skipped
	time_spent = _current_elapsed()
	st.session_state.practice_answers[idx] = choice
	st.session_state.practice_results[idx] = {
		"correct": correct,
		"skipped": skipped,
		"choice": choice,
		"time_spent": round(time_spent, 2),
	}


def _toggle_pause() -> None:
	if not st.session_state.practice_paused:
		st.session_state.practice_paused = True
		st.session_state.practice_pause_started_at = time.time()
	else:
		if st.session_state.practice_pause_started_at is not None:
			st.session_state.practice_pause_total = float(st.session_state.practice_pause_total or 0.0) + (
				time.time() - st.session_state.practice_pause_started_at
			)
		st.session_state.practice_paused = False
		st.session_state.practice_pause_started_at = None


def _render_setup_stage() -> None:
	st.markdown("### 1. Add study material")

	left, right = st.columns([1.45, 1], gap="large")

	with left:
		uploads = st.file_uploader(
			"Upload PDFs or images",
			type=["pdf", "png", "jpg", "jpeg"],
			accept_multiple_files=True,
			label_visibility="visible",
			key="practice_uploads",
		)
		if uploads and st.button("Add selected uploads", type="primary", use_container_width=True):
			_add_sources(uploads, kind="upload")
			st.rerun()

		st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
		capture = st.camera_input("Capture a page", key="practice_camera")
		if capture is not None:
			st.image(capture, caption="Latest capture", use_container_width=True)
			if st.button("Add camera capture", use_container_width=True):
				_add_sources([capture], kind="camera")
				st.rerun()

		st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
		_render_source_queue()

	with right:
		st.markdown("#### Practice settings")
		st.session_state.practice_provider_label = st.selectbox(
			"AI backend",
			list(BACKEND_OPTIONS.keys()),
			index=list(BACKEND_OPTIONS.keys()).index(st.session_state.practice_provider_label),
			help="Offline local mode uses your LM Studio server. Groq is optional and requires an API key.",
		)
		st.session_state.practice_timer_label = st.selectbox(
			"Timer mode",
			list(TIMER_MODES.keys()),
			index=list(TIMER_MODES.keys()).index(st.session_state.practice_timer_label),
		)
		st.markdown(
			"""
<div class="practice-card">
  <p style="margin:0 0 8px;font-weight:700;color:#1E293B;">How the pipeline works</p>
  <ol style="margin:0;padding-left:18px;color:#475569;font-size:.92rem;line-height:1.7;">
	<li>OCR extracts text from PDFs, images, or camera captures.</li>
	<li>An AI cleanup step repairs broken lines and spelling noise.</li>
	<li>The model converts the text into GRE-style MCQs and labels difficulty.</li>
	<li>You answer them one by one with a timer, pause lock, and calculator.</li>
  </ol>
</div>
""",
			unsafe_allow_html=True,
		)

		st.success("All questions detected in your uploaded file will be used. No manual question count is needed.")

		st.warning(
			"Pause mode freezes the timer and hides the quiz. Browser tab blocking and screenshots cannot be fully enforced in a Streamlit app, so this is best-effort study protection.",
			icon="🛡️",
		)

	st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
	process_disabled = not st.session_state.practice_sources
	if st.button("🚀 Build practice set", type="primary", use_container_width=True, disabled=process_disabled):
		provider = BACKEND_OPTIONS[st.session_state.practice_provider_label]
		timer_label = st.session_state.practice_timer_label

		with st.spinner("Running OCR, cleaning the text, and generating MCQs…"):
			raw_text = extract_text_from_sources(st.session_state.practice_sources)
			if not raw_text.strip():
				st.error("No readable text was extracted from the uploaded files. Try a sharper scan or a different page image.")
				return

			document_name = st.session_state.practice_sources[0]["name"] if st.session_state.practice_sources else "Uploaded Practice Set"
			practice_set = generate_practice_set_from_text(
				raw_text=raw_text,
				provider=provider,
				document_name=document_name,
			)

		if not practice_set.get("questions"):
			st.error("The practice set could not be built from the extracted text. Try a cleaner PDF or image.")
			return

		_set_quiz_session(practice_set, timer_label)
		st.rerun()


def _render_quiz_stage() -> None:
	practice_set = st.session_state.practice_set or {}
	questions = practice_set.get("questions", [])
	total = len(questions)

	if not questions:
		st.warning("No questions are loaded yet. Go back and upload a document.")
		st.session_state.practice_stage = "setup"
		return

	if callable(getattr(st, "autorefresh", None)) and not st.session_state.practice_paused:
		st.autorefresh(interval=1000, key="practice_timer_tick")

	current_idx = min(st.session_state.practice_current_idx, total - 1)
	question = questions[current_idx]

	if st.session_state.practice_paused:
		st.markdown(
			"""
<div class="practice-lock">
  <p style="font-size:2.2rem;margin:0 0 10px;">⏸️</p>
  <h3 style="margin:0 0 8px;">Practice paused</h3>
  <p style="margin:0 0 18px;color:#475569;">The quiz is frozen and the timer is stopped.</p>
""",
			unsafe_allow_html=True,
		)
		if st.button("Resume practice", type="primary"):
			_toggle_pause()
			st.rerun()
		st.markdown("</div>", unsafe_allow_html=True)
		return

	if st.session_state.practice_question_started_at is None:
		_start_question_timer()

	remaining = _remaining_seconds()
	if remaining <= 0:
		_store_answer(current_idx, choice=-1, skipped=True)
		_advance_question(1)
		st.rerun()

	answered = current_idx in st.session_state.practice_results
	chosen = st.session_state.practice_answers.get(current_idx)
	correct_index = int(question.get("correct_index", 0))
	options = question.get("options", [])

	st.markdown(
		f"""
<div class="practice-card">
  <div class="practice-meta">{practice_set.get('document_title', 'Practice Set')}</div>
  <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;">
	<div>
	  <span style="font-weight:700;color:#1E293B;">Question {current_idx + 1} of {total}</span>
	  <span class="practice-pill {question.get('difficulty', 'medium')}">{question.get('difficulty', 'medium').title()}</span>
	</div>
	<div style="color:#0F172A;font-weight:800;font-size:1.15rem;">⏱️ {_fmt_seconds(remaining)}</div>
  </div>
  <div style="margin-top:10px;">
	<span style="display:inline-block;background:#EFF6FF;color:#1D4ED8;border-radius:999px;padding:4px 10px;font-size:.78rem;font-weight:700;">{st.session_state.practice_timer_label}</span>
  </div>
</div>
""",
		unsafe_allow_html=True,
	)

	st.markdown(f"<div class='practice-card'><p class='practice-question'>{question.get('question', '')}</p></div>", unsafe_allow_html=True)

	if not answered:
		choice = st.radio(
			"Choose one answer",
			options=list(range(len(options))),
			format_func=lambda i: f"{chr(65 + i)}. {options[i]}",
			key=f"practice_radio_{current_idx}",
			label_visibility="collapsed",
		)

		col_left, col_mid, col_right = st.columns([1, 1, 1])
		with col_left:
			if st.button("⏭️ Skip", use_container_width=True):
				_store_answer(current_idx, choice=-1, skipped=True)
				_advance_question(1)
				st.rerun()
		with col_mid:
			if st.button("⏸️ Pause", use_container_width=True):
				_toggle_pause()
				st.rerun()
		with col_right:
			if st.button("✅ Check & Next", type="primary", use_container_width=True):
				_store_answer(current_idx, choice=int(choice), skipped=False)
				_advance_question(1)
				st.rerun()
	else:
		is_correct = bool(st.session_state.practice_results[current_idx].get("correct"))
		for i, option in enumerate(options):
			if i == correct_index:
				st.success(f"✓ {chr(65 + i)}. {option}")
			elif chosen == i and not is_correct:
				st.error(f"✗ {chr(65 + i)}. {option}")
			else:
				st.markdown(f"&nbsp;&nbsp;&nbsp;{chr(65 + i)}. {option}", unsafe_allow_html=True)

		st.markdown(
			f"""
<div class="practice-card" style="background:{'#ECFDF5' if is_correct else '#FEF2F2'};border-color:{'#A7F3D0' if is_correct else '#FCA5A5'};">
  <p style="margin:0 0 4px;font-weight:800;color:#1E293B;">{('Correct' if is_correct else 'Review this one')}</p>
  <p style="margin:0;color:#475569;">{question.get('explanation', '')}</p>
</div>
""",
			unsafe_allow_html=True,
		)

		col_prev, col_change, col_flag, col_pause, col_next = st.columns([1, 1, 1, 1, 1])
		with col_prev:
			st.button("← Prev", use_container_width=True, disabled=current_idx == 0, on_click=_advance_question, args=(-1,))
		with col_change:
			if st.button("✏️ Change", use_container_width=True):
				st.session_state.practice_answers.pop(current_idx, None)
				st.session_state.practice_results.pop(current_idx, None)
				_start_question_timer()
				st.rerun()
		with col_flag:
			label = "Unflag" if st.session_state.practice_flags.get(current_idx) else "Flag"
			if st.button(f"🚩 {label}", use_container_width=True):
				st.session_state.practice_flags[current_idx] = not st.session_state.practice_flags.get(current_idx, False)
				st.rerun()
		with col_pause:
			if st.button("⏸️ Pause", use_container_width=True):
				_toggle_pause()
				st.rerun()
		with col_next:
			if st.button("Next →", type="primary", use_container_width=True):
				_advance_question(1)
				st.rerun()

	answered_count = len(st.session_state.practice_results)
	correct_count = sum(1 for result in st.session_state.practice_results.values() if result.get("correct"))
	skipped_count = sum(1 for result in st.session_state.practice_results.values() if result.get("skipped"))
	pct = int((correct_count / answered_count) * 100) if answered_count else 0

	st.progress((current_idx + 1) / total)
	m1, m2, m3, m4 = st.columns(4)
	m1.metric("Answered", f"{answered_count}/{total}")
	m2.metric("Correct", correct_count)
	m3.metric("Skipped", skipped_count)
	m4.metric("Accuracy", f"{pct}%")

	with st.sidebar:
		st.markdown("### Practice overview")
		overview = []
		for idx, item in enumerate(questions):
			if idx == current_idx:
				status = "current"
			elif idx in st.session_state.practice_results:
				status = "answered" if st.session_state.practice_results[idx].get("correct") else "skipped" if st.session_state.practice_results[idx].get("skipped") else "answered"
			elif st.session_state.practice_flags.get(idx):
				status = "flagged"
			else:
				status = "pending"
			overview.append(f"<span class='practice-status-dot {status}'></span>{idx + 1} · {item.get('difficulty', 'medium').title()}")

		st.markdown("<br/>".join(overview), unsafe_allow_html=True)
		st.markdown("---")
		st.metric("Timer mode", st.session_state.practice_timer_label)
		st.metric("Limit / q", _fmt_seconds(st.session_state.practice_timer_limit))
		st.metric("Flags", sum(1 for value in st.session_state.practice_flags.values() if value))
		_render_calculator()


def _render_results_stage() -> None:
	practice_set = st.session_state.practice_set or {}
	questions = practice_set.get("questions", [])
	total = len(questions)
	results = st.session_state.practice_results
	correct = sum(1 for result in results.values() if result.get("correct"))
	skipped = sum(1 for result in results.values() if result.get("skipped"))
	answered = len(results)
	accuracy = int((correct / answered) * 100) if answered else 0
	total_time = 0.0
	for result in results.values():
		total_time += float(result.get("time_spent", 0.0))

	if not st.session_state.practice_saved:
		save_result(
			"practice",
			{
				"title": practice_set.get("document_title", "Practice Set"),
				"mode": st.session_state.practice_timer_label,
				"questions": total,
				"answered": answered,
				"correct": correct,
				"skipped": skipped,
				"accuracy": accuracy,
				"backend": st.session_state.practice_provider_label,
			},
		)
		st.session_state.practice_saved = True

	st.markdown("### Results")
	c1, c2, c3, c4 = st.columns(4)
	c1.metric("Score", f"{correct}/{total}")
	c2.metric("Accuracy", f"{accuracy}%")
	c3.metric("Skipped", skipped)
	c4.metric("Time spent", _fmt_seconds(total_time))

	st.markdown(
		f"""
<div class="practice-card">
  <p style="margin:0 0 8px;font-weight:800;color:#1E293B;">{practice_set.get('document_title', 'Practice Set')}</p>
  <p style="margin:0;color:#475569;">{practice_set.get('summary', 'Practice session complete.')}</p>
</div>
""",
		unsafe_allow_html=True,
	)

	if practice_set.get("repair_notes"):
		with st.expander("OCR cleanup notes", expanded=False):
			for note in practice_set.get("repair_notes", []):
				st.markdown(f"- {note}")

	st.markdown("### Review")
	for idx, question in enumerate(questions):
		result = results.get(idx, {})
		correct_index = int(question.get("correct_index", 0))
		chosen = st.session_state.practice_answers.get(idx)
		is_correct = bool(result.get("correct"))
		status = "Correct" if is_correct else "Skipped" if result.get("skipped") else "Wrong" if chosen is not None else "Not answered"

		with st.expander(f"Q{idx + 1} — {status}", expanded=idx == 0):
			st.markdown(f"**Difficulty:** {question.get('difficulty', 'medium').title()}")
			st.markdown(question.get("question", ""))
			for i, option in enumerate(question.get("options", [])):
				if i == correct_index:
					st.success(f"✓ {chr(65 + i)}. {option}")
				elif chosen == i and not is_correct:
					st.error(f"✗ {chr(65 + i)}. {option}")
				else:
					st.markdown(f"{chr(65 + i)}. {option}")
			st.info(question.get("explanation", ""))
			if question.get("source_excerpt"):
				st.caption(f"Source excerpt: {question.get('source_excerpt')}")

	st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
	c_restart, c_reset, c_clear = st.columns(3)
	with c_restart:
		if st.button("↩ Start again", type="primary", use_container_width=True):
			st.session_state.practice_stage = "setup"
			st.session_state.practice_current_idx = 0
			st.session_state.practice_answers = {}
			st.session_state.practice_results = {}
			st.session_state.practice_flags = {}
			st.session_state.practice_saved = False
			st.session_state.practice_question_started_at = None
			st.rerun()
	with c_reset:
		if st.button("🧹 Clear history", use_container_width=True):
			clear_history("practice")
			st.rerun()
	with c_clear:
		if st.button("Upload new documents", use_container_width=True):
			st.session_state.practice_stage = "setup"
			st.session_state.practice_sources = []
			st.session_state.practice_set = None
			st.session_state.practice_current_idx = 0
			st.session_state.practice_answers = {}
			st.session_state.practice_results = {}
			st.session_state.practice_flags = {}
			st.session_state.practice_saved = False
			st.session_state.practice_question_started_at = None
			st.rerun()

	history = load_history("practice")
	if history:
		with st.expander(f"Past practice sessions ({len(history)})", expanded=False):
			for entry in reversed(history[-10:]):
				ts = entry.get("timestamp", "")[:16].replace("T", " ")
				st.markdown(
					f"- `{ts}` · **{entry.get('title', 'Practice Set')}** · {entry.get('correct', 0)}/{entry.get('questions', 0)} correct · {entry.get('accuracy', 0)}%"
				)


page_header(
	"📝 Practice Mode",
	"Upload PDFs, images, or camera captures. Lexora will OCR them, clean the text, and turn the material into GRE-style practice questions.",
)

st.caption(
	"Best for study material, scanned handouts, worksheets, and question banks. OCR quality still matters — sharper scans produce much better questions."
)

if st.session_state.practice_stage == "setup":
	_render_setup_stage()
elif st.session_state.practice_stage == "quiz":
	_render_quiz_stage()
else:
	_render_results_stage()

