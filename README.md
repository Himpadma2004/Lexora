# 📚 Lexora — AI Language Coach

An AI-powered educational platform for **IELTS Speaking** and **GRE Vocabulary** practice,
built with Python, Streamlit, and Google Gemini.

---

## Modules

| Module | Description |
|--------|-------------|
| 🎤 IELTS Speaking Coach | Practice Parts 1, 2 & 3. Get band scores, strengths, weaknesses & tips. |
| 📖 GRE Vocabulary Coach | Learn 5 new GRE words daily. Quiz yourself with AI-generated MCQs. |
| 📝 Practice Mode | Upload PDFs, images, or camera captures. OCR them, clean the text, and generate GRE-style MCQs with timers. |

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd lexora
pip install -r requirements.txt
```

### 2. Configure the AI backend

Practice Mode works best with a local OpenAI-compatible model server such as LM Studio.

Optional environment variables:

- `LMSTUDIO_HOST` — local OpenAI-compatible endpoint, default `http://127.0.0.1:1234/v1`
- `GROQ_API_KEY` — optional Groq backend key
- `GROQ_BASE_URL` — optional Groq-compatible base URL
- `GROQ_MODEL` — optional Groq model name

If you want to use Gemini for the existing IELTS module, create `.streamlit/secrets.toml` with your `GEMINI_API_KEY`.

### 3. Run

```bash
streamlit run app.py
```

---

## Project Structure

```
lexora/
├── .streamlit/
│   └── config.toml          # Theme & server config
├── data/
│   ├── gre_words.json        # Fallback GRE words (used if API fails)
│   ├── sample_questions.json # Fallback IELTS questions
│   └── history/              # Auto-created — session history (JSON)
├── services/
│   ├── ai.py                 # AI calls for IELTS, GRE, and Practice Mode
│   ├── ocr.py                # PDF/image OCR and cleanup helpers
│   └── db.py                 # JSON file-based history persistence
├── ui/
│   ├── components.py         # CSS injection + shared HTML components
│   └── pages/
│       ├── home.py           # Dashboard / landing page
│       ├── ielts.py          # IELTS Speaking module
│       ├── gre.py            # GRE Vocabulary module
│       └── practice.py       # OCR → cleanup → MCQ practice pipeline
├── app.py                    # Entry point + st.navigation wiring
└── requirements.txt
```

---

## Tech Stack

- **Streamlit** ≥ 1.36 — UI & multi-page navigation
- **PyMuPDF + EasyOCR** — PDF and image text extraction
- **OpenAI-compatible local models** — OCR cleanup and practice-set generation
- **Google Gemini 2.5 Flash** — AI question generation & evaluation
- **JSON files** — Lightweight local history storage

---

## Future Roadmap (v2+)

- IELTS Writing & Listening modules
- Pronunciation scoring (audio input)
- User accounts & progress tracking
- AI Tutor Chat
- Study planner
