# 📚 Lexora — AI Language Coach

An AI-powered educational platform for **IELTS Speaking** and **GRE Vocabulary** practice,
built with Python, Streamlit, and Google Gemini.

---

## Modules

| Module | Description |
|--------|-------------|
| 🎤 IELTS Speaking Coach | Practice Parts 1, 2 & 3. Get band scores, strengths, weaknesses & tips. |
| 📖 GRE Vocabulary Coach | Learn 5 new GRE words daily. Quiz yourself with AI-generated MCQs. |

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd lexora
pip install -r requirements.txt
```

### 2. Add your Gemini API key

Create `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your-key-here"
```

Get a free API key at [Google AI Studio](https://aistudio.google.com/).

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
│   ├── ai.py                 # All Gemini API calls
│   └── db.py                 # JSON file-based history persistence
├── ui/
│   ├── components.py         # CSS injection + shared HTML components
│   └── pages/
│       ├── home.py           # Dashboard / landing page
│       ├── ielts.py          # IELTS Speaking module
│       └── gre.py            # GRE Vocabulary module
├── app.py                    # Entry point + st.navigation wiring
└── requirements.txt
```

---

## Tech Stack

- **Streamlit** ≥ 1.36 — UI & multi-page navigation
- **Google Gemini 2.5 Flash** — AI question generation & evaluation
- **google-generativeai** — Gemini Python SDK
- **JSON files** — Lightweight local history storage

---

## Future Roadmap (v2+)

- IELTS Writing & Listening modules
- Pronunciation scoring (audio input)
- User accounts & progress tracking
- AI Tutor Chat
- Study planner
