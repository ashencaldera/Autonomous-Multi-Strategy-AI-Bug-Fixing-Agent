# ⚡ BugFixAI — Autonomous Multi-Strategy Python Bug-Fixing Agent

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203.3%2070B-FF6B35?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**An autonomous AI agent that executes, analyses, reflects, generates multiple fixes, validates each one, and returns the best working solution — with zero manual debugging.**

[▶ Watch Demo](https://youtube.com/shorts/YOUR_LINK) · [🚀 Quick Start](#-quick-start) · [🏗 Architecture](#-architecture)

</div>

---

## 🤔 What is This?

BugFixAI is **not a chatbot**. It is an autonomous AI agent.

Most AI coding tools work like this:
> User pastes error → AI guesses a fix → User hopes it works

BugFixAI works like this:
> Agent **executes** the code → **captures** the real error → **analyses** the root cause → **generates 4 different fixes** using different strategies → **tests every single one** → **scores them** → **returns the verified best**

The agent loops, reflects on failures, and self-corrects — just like a real developer debugging a problem.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔁 **Autonomous Loop** | Runs up to 3 full fix attempts without human input |
| 🧠 **LLM Reasoning** | Uses Groq's LLaMA 3.3 70B for deep error analysis |
| 🎯 **Multi-Strategy** | Generates Minimal, Defensive, Refactored, and Typed fixes |
| 🪞 **Self-Reflection** | Analyses why previous fixes failed before retrying |
| 🧪 **Candidate Testing** | Executes and scores every fix — picks the best one |
| ✅ **6-Layer Validation** | Syntax → Runtime → Output → Tests → Quality → Score |
| 📊 **Live Streaming** | Real-time agent steps via Server-Sent Events (SSE) |
| 🔴🟢 **Diff View** | Side-by-side comparison of buggy vs fixed code |
| 💾 **Session Memory** | Tracks all attempts, reflections, and decisions |
| 🔒 **Safe Execution** | Sandboxed subprocess with timeout and blocked dangerous patterns |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    USER INTERFACE                    │
│         Flask + HTML/CSS/JS  (SSE Streaming)         │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 AGENT CONTROLLER                     │
│           Autonomous orchestration loop              │
└──┬──────────┬────────┬───────────┬──────────┬───────┘
   │          │        │           │          │
┌──▼──┐  ┌───▼───┐ ┌──▼──┐  ┌────▼───┐ ┌────▼────┐
│Exec │  │Error  │ │Refl-│  │Planner │ │Validat- │
│-utor│  │Search │ │ector│  │(Fixer) │ │  or     │
│     │  │  er   │ │     │  │        │ │         │
└──┬──┘  └───┬───┘ └──┬──┘  └────┬───┘ └────┬────┘
   │          │        │           │          │
   └──────────┴────────┴─────┬─────┴──────────┘
                              │
                    ┌─────────▼─────────┐
                    │   AGENT MEMORY    │
                    │  Session history  │
                    │  attempts, steps  │
                    │  reflections      │
                    └───────────────────┘
```

### Agent Components

| Module | Role |
|--------|------|
| `agent/controller.py` | ★ Main autonomous loop — orchestrates everything |
| `agent/executor.py` | Runs Python code safely in an isolated subprocess |
| `agent/error_searcher.py` | LLM-powered root cause analysis and diagnostic insight |
| `agent/reflector.py` | Metacognitive self-correction — learns from failed fixes |
| `agent/planner.py` | Generates 4 candidate fixes with different strategies |
| `agent/validator.py` | 6-layer validation pipeline with numerical scoring |
| `agent/memory.py` | Full session state — attempts, steps, candidates, results |
| `llm/groq_client.py` | Groq API client with retry logic, JSON mode, token tracking |

---

## 🔁 How the Agent Works

```
User submits buggy code
         │
         ▼
┌─────────────────┐
│ STEP 1          │  Execute original code in sandboxed subprocess
│ Execute         │  Capture stdout, stderr, traceback
└────────┬────────┘
         ▼
┌─────────────────┐
│ STEP 2          │  LLM analyses the error type, root cause,
│ Analyse Error   │  contributing factors, and fix hints
└────────┬────────┘
         ▼
    ╔═══════════════════════════════════════╗
    ║        LOOP (max 3 attempts)          ║
    ║                                       ║
    ║  ┌─────────────────┐                 ║
    ║  │ STEP 3          │  Review what    ║
    ║  │ Reflect         │  failed before  ║
    ║  └────────┬────────┘                 ║
    ║           ▼                           ║
    ║  ┌─────────────────┐                 ║
    ║  │ STEP 4          │  4 strategies:  ║
    ║  │ Generate Fixes  │  • Minimal      ║
    ║  │                 │  • Defensive    ║
    ║  │                 │  • Refactored   ║
    ║  │                 │  • Typed        ║
    ║  └────────┬────────┘                 ║
    ║           ▼                           ║
    ║  ┌─────────────────┐                 ║
    ║  │ STEP 5          │  Execute each   ║
    ║  │ Test & Validate │  Score 0–100%   ║
    ║  └────────┬────────┘                 ║
    ║           ▼                           ║
    ║  ┌─────────────────┐                 ║
    ║  │ STEP 6          │  Pick highest   ║
    ║  │ Select Best     │  scoring fix    ║
    ║  └────────┬────────┘                 ║
    ║           │                           ║
    ║  Score ≥ 80% → STOP immediately      ║
    ║  Score ≥ 55% → Accept & finish       ║
    ║  Score < 55% → Retry next attempt    ║
    ╚═══════════════════════════════════════╝
         │
         ▼
Return best fix with diff view,
syntax highlighting & explanation
```

---

## 🎯 Fix Strategies Explained

| Strategy | Approach | Best For |
|----------|----------|----------|
| **Minimal** | Smallest possible change | Quick syntax/name errors |
| **Defensive** | Adds error handling, input guards | Runtime & type errors |
| **Refactored** | Clean rewrite, PEP 8 compliant | Logic & structure errors |
| **Typed** | Adds type hints and docstrings | Professional code quality |

---

## 🧪 Validation Pipeline

Each candidate fix is scored through 6 layers:

```
Layer 1 — Syntax Check      (+15%)  Does it parse without error?
Layer 2 — Safety Check      (gate)  No dangerous patterns?
Layer 3 — Execution Check   (+30%)  Does it run without crashing?
Layer 4 — Output Check      (+10%)  Does output match expectations?
Layer 5 — Test Cases        (+35%)  Does it pass generated assertions?
Layer 6 — Code Quality      (+10%)  Heuristic quality score
                            ──────
Maximum Score               100%
Acceptance Threshold         55%
Auto-stop Threshold          80%
```

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/bugfix-ai-agent.git
cd bugfix-ai-agent
```

### 2. Create virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment
```bash
cp .env.example .env
```
Edit `.env` and add your Groq API key:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```
Get a free key at → **https://console.groq.com/keys**

### 5. Run
```bash
python app.py
```
Open **http://localhost:5000**

---

## 📁 Project Structure

```
bugfix-ai-agent/
├── app.py                  Flask server + SSE streaming
├── config.py               Centralised configuration
├── requirements.txt        Dependencies
├── .env.example            Environment template
├── README.md
│
├── agent/
│   ├── __init__.py
│   ├── controller.py       ★ Main agent loop
│   ├── memory.py           Session state & data models
│   ├── executor.py         Safe subprocess code runner
│   ├── error_searcher.py   LLM error analysis
│   ├── reflector.py        Self-correction module
│   ├── planner.py          Multi-strategy fix generator
│   └── validator.py        6-layer validation system
│
├── llm/
│   ├── __init__.py
│   └── groq_client.py      Groq API wrapper
│
├── templates/
│   └── index.html          Web UI
│
└── static/
    ├── css/style.css       Cyberpunk dark theme
    └── js/main.js          SSE client + diff engine + syntax highlighter
```

---

## ⚙️ Configuration

All settings are controlled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | **Required.** Your Groq API key |
| `MAX_ATTEMPTS` | `3` | Fix attempts before giving up |
| `MAX_CANDIDATES` | `4` | Fix strategies per attempt |
| `EXECUTION_TIMEOUT` | `10` | Code execution timeout (seconds) |
| `MIN_VALIDATION_SCORE` | `0.55` | Minimum score to accept a fix |
| `MAX_CODE_LENGTH` | `5000` | Max input code characters |
| `FLASK_DEBUG` | `false` | Enable debug mode |

---

## 🔒 Security

- Code runs in an **isolated subprocess** — not eval, not exec
- **Dangerous patterns blocked**: `os.system`, `subprocess`, file writes, `eval`
- **10-second execution timeout** — no infinite loops
- **5000 character input limit**
- No user code ever touches the host filesystem

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/api/fix` | Start fix session → `{ session_id }` |
| `GET` | `/api/stream/<id>` | SSE stream of agent events |
| `GET` | `/api/examples` | Built-in example snippets |
| `GET` | `/api/health` | Health check |

### SSE Event Types

```
step                → Agent step started / completed
error_analysis      → LLM error explanation result
reflection          → Self-correction reasoning
candidates_generated → N fixes created
candidate_result    → Single fix tested and scored
best_selected       → Winning candidate identified
result              → Final fixed code
done                → Session complete
```

---

## 🐛 What It Can Fix

- ✅ `SyntaxError` — missing colons, brackets, indentation
- ✅ `NameError` — undefined variables, typos
- ✅ `TypeError` — wrong argument types, bad concatenation
- ✅ `IndexError` — out of range access
- ✅ `AttributeError` — wrong method names
- ✅ `ZeroDivisionError` — division by zero / empty list
- ✅ `ValueError` — bad type conversions
- ✅ Logic errors — wrong operators (`=+` vs `+=`), off-by-one
- ✅ Missing return statements
- ✅ Wrong string formatting

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask 3.0 |
| LLM | Groq API — LLaMA 3.3 70B |
| Streaming | Server-Sent Events (SSE) |
| Execution | Python `subprocess` + `tempfile` |
| Frontend | Vanilla HTML/CSS/JS |
| Fonts | Oxanium (display), JetBrains Mono (code) |

---

## 🎓 Academic Context

Built as a demonstration of the core components of a production-grade AI agent:

- **Brain** → LLM reasoning via Groq
- **Tools** → Code execution, error lookup, test runner
- **Memory** → Full session history with attempt tracking
- **Planning** → Multi-strategy candidate generation
- **Autonomy** → Self-directed loop with stopping criteria
- **Self-correction** → Reflection and retry on failure
- **Validation** → Verifies correctness, not just syntax

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <strong>Built with ⚡ by [Ashen Caldera]</strong><br/>
  <sub>Powered by Groq · LLaMA 3.3 70B · Flask · Python</sub>
</div>
