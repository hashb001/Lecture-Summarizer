# 📖 LectureMind — AI Lecture Summarizer

> Upload a PowerPoint lecture. Get instant AI summaries, ask questions, generate quizzes and assignments — all in one place.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green?style=flat-square&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?style=flat-square&logo=postgresql)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Transformers-yellow?style=flat-square&logo=huggingface)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)

---

## 🎯 What is this?

LectureMind is a full-stack AI web application that helps students study smarter. Instead of reading through a 40-slide PowerPoint manually, you upload the file and the app does the hard work — summarizing every slide, answering your questions, and generating quizzes to test your understanding.

**[🌐 View Live Demo Page](https://github.com/hashb001/Lecture-Summarizer)** &nbsp;|&nbsp; **[▶ Watch Video Demo](https://youtu.be/cfCr7p1rOkE)**

---

## ✨ Features

| Feature | Description |
|---|---|
| 📊 **Slide Summarization** | Extracts and summarizes every slide from a `.pptx` file using DistilBART |
| 💬 **Contextual Q&A** | Ask questions about any slide — answers are grounded in your lecture only |
| 📝 **Quiz Generation** | Auto-generates multiple-choice and short-answer quizzes |
| 📘 **Assignment Creation** | Creates structured university-level assignments from lecture content |
| 🗂️ **Course Management** | Organize summaries by course, revisit history, track quizzes |
| 🔒 **Auth System** | JWT authentication with bcrypt hashing + guest mode |
| 🌙 **Dark Mode** | Full dark/light theme toggle |

---

## 🛠️ Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — async Python web framework
- [PostgreSQL](https://www.postgresql.org/) + [SQLAlchemy](https://www.sqlalchemy.org/) — database & ORM
- [python-pptx](https://python-pptx.readthedocs.io/) — PowerPoint text extraction
- JWT + bcrypt — authentication & password security

**AI / ML**
- [HuggingFace Transformers](https://huggingface.co/transformers/) — model inference pipeline
- `sshleifer/distilbart-cnn-12-6` — slide summarization
- `google/flan-t5-base` — Q&A and explanations
- OpenAI `gpt-4o-mini` — optional high-quality fallback

**Frontend**
- Vanilla JS, HTML5, CSS3 — no framework overhead
- Custom dark/light theme with CSS variables
- Responsive design

**Infrastructure**
- Docker + Docker Compose — containerized deployment

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Docker (optional but recommended)

### 1. Clone the repo
```bash
git clone https://github.com/hasb001/ai-lecture-summarizer.git
cd ai-lecture-summarizer
```

### 2. Set up environment
```bash
cp env.example .env
# Edit .env with your database credentials and JWT secret
```

### 3. Start the database
```bash
docker-compose up -d
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the server
```bash
uvicorn backend.app:app --reload
```

### 6. Open in browser
```
http://localhost:8000
```

---

## 📁 Project Structure

```
ai-lecture-summarizer/
├── backend/
│   ├── app.py          # FastAPI routes & endpoints
│   ├── auth.py         # JWT authentication
│   ├── models.py       # SQLAlchemy database models
│   ├── schemas.py      # Pydantic request/response schemas
│   ├── summarize.py    # HuggingFace summarization pipeline
│   ├── qa_model.py     # Q&A and explanation model
│   ├── utils.py        # Session management & helpers
│   └── database.py     # Database connection setup
├── frontend/
│   ├── index.html      # Main SPA shell
│   ├── app.js          # All frontend logic
│   └── styles.css      # Styling & dark mode
├── docker-compose.yml
├── requirements.txt
└── env.example
```

---

## 🔌 API Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create a new account |
| `POST` | `/api/auth/login` | Log in, receive JWT token |
| `POST` | `/api/extract` | Upload .pptx, extract slide text |
| `POST` | `/api/summarize/slide` | Summarize a specific slide |
| `POST` | `/api/chat` | Ask a question about the lecture |
| `POST` | `/api/generate/quiz` | Generate a quiz from lecture |
| `POST` | `/api/generate/assignment` | Generate an assignment |
| `GET` | `/api/courses` | List user's courses |
| `POST` | `/api/summaries` | Save a summary to a course |

---

## 💡 Skills Demonstrated

- **Full-stack development** — designed and built both backend API and frontend UI from scratch
- **AI/ML integration** — integrated multiple HuggingFace transformer models with token management and fallback logic
- **Database design** — modelled relational data across users, courses, sessions, summaries, quizzes, and assignments
- **Authentication** — implemented secure JWT-based auth with bcrypt password hashing
- **REST API design** — structured clean, versioned API endpoints with proper validation using Pydantic
- **Frontend engineering** — built a responsive SPA with theme switching, persistent chat history, and real-time progress feedback
- **DevOps** — containerized the full stack with Docker Compose

---

## 📋 STAR Challenge Report

### Situation
Students receive large lecture PowerPoints but lack tools to quickly extract and understand key content without expensive API subscriptions.

### Task
Build a self-hosted, full-stack AI application that summarizes lecture slides, answers questions from the content, and generates study materials — deployable without any paid AI service.

### Action
- Integrated DistilBART for slide-by-slide summarization with careful input token chunking to avoid model truncation errors
- Built a keyword-based context retrieval system so Q&A responses are always grounded in the correct slide content
- Designed a dual-mode user system (guest and authenticated) backed by PostgreSQL with session persistence that survives server restarts
- Added an optional OpenAI fallback to improve answer quality when an API key is provided, without changing core logic

### Result
The app summarizes a 20-slide lecture in under 30 seconds, generates coherent quizzes and assignments, and reliably persists all user data. The modular AI layer made it straightforward to swap or extend models as the project evolved.

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<div align="center">
  Built with ❤️ as a Final Year Project &nbsp;|&nbsp;
  <a href="https://github.com/hashb001/Lecture-Summarizer">Live Page</a> &nbsp;|&nbsp;
  <a href="https://youtu.be/cfCr7p1rOkE">Video Demo</a>
</div>
