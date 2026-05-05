import logging
import os
import re
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import create_access_token, decode_access_token, get_password_hash, verify_password
from .database import Base, engine, get_db
from .models import Assignment, Course, Quiz, Summary, User
from .qa_model import (
    answer_question,
    explain_slide,
    generate_assignment_from_lecture,
    generate_quiz_from_lecture,
)
from .schemas import (
    AssignmentOut,
    CourseCreate,
    CourseOut,
    LoginRequest,
    QuizOut,
    SummaryCreate,
    SummaryOut,
    TokenResponse,
    UserCreate,
    UserOut,
)
from .summarize import summarize_slide
from .utils import create_session, extract_text_by_slide, get_session, sessions

logger = logging.getLogger("ai_lecture_app")
logging.basicConfig(level=logging.INFO)

SLIDE_RX = re.compile(r"(?:slide|page)\s*(?:no\.?|number|#)?\s*[:.-]?\s*(\d{1,3})", re.I)


def extract_slide_number(message: str) -> Optional[int]:
    
    if not message:
        return None

    txt = message.lower()

    m = SLIDE_RX.search(txt)
    if m:
        try:
            n = int(m.group(1))
            return n if 1 <= n <= 999 else None
        except ValueError:
            return None

    
    fallback_pattern = re.compile(r"(?:slide|page).*?(\d{1,3})", re.I)
    m = fallback_pattern.search(txt)
    if m:
        try:
            n = int(m.group(1))
            return n if 1 <= n <= 999 else None
        except ValueError:
            return None

    return None


def pick_relevant_slides(question: str, slides: list[dict], k: int = 3) -> list[dict]:
    
    q = question or ""
    q_words = set(re.findall(r"\b\w+\b", q.lower()))
    scored: list[tuple[int, dict]] = []
    for s in slides:
        blob = " ".join(
            [
                str(s.get("title", "")),
                " ".join(s.get("bullets", []) or []),
                str(s.get("text", "")),
            ]
        ).lower()
        words = set(re.findall(r"\b\w+\b", blob))
        score = len(q_words & words)
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for score, s in scored[:k] if score > 0]


app = FastAPI(title="AI Lecture Chat Summarizer")


FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=False,  
    allow_methods=["*"],
    allow_headers=["*"],
)


auth_scheme = HTTPBearer(auto_error=False)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.on_event("startup")
def on_startup():
    
    Base.metadata.create_all(bind=engine)


@app.get("/")
async def serve_home():
    index_path = os.path.join(frontend_path, "index.html")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


def _resolve_user(credentials: Optional[HTTPAuthorizationCredentials], db: Session, *, required: bool):
    if not credentials:
        if required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    return _resolve_user(credentials, db, required=True)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    return _resolve_user(credentials, db, required=False)



@app.post("/api/auth/register", response_model=UserOut)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/auth/login", response_model=TokenResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": user.email, "uid": str(user.id)})
    return TokenResponse(access_token=token)


@app.post("/api/auth/logout")
def logout_user():
    
    return {"detail": "Logged out"}


@app.get("/api/auth/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user




@app.get("/api/courses", response_model=list[CourseOut])
def list_courses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Course)
        .filter(Course.owner_id == current_user.id)
        .order_by(Course.created_at.desc())
        .all()
    )


@app.post("/api/courses", response_model=CourseOut)
def create_course(
    payload: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = Course(owner_id=current_user.id, name=payload.name, subject=payload.subject)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course



@app.post("/api/summaries", response_model=SummaryOut)
def save_summary(
    payload: SummaryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = (
        db.query(Course)
        .filter(Course.id == payload.course_id, Course.owner_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    summary_text = payload.summary_text
    if not summary_text or not summary_text.strip():
        sess = get_session(payload.session_id) if payload.session_id else None
        summary_text = (sess or {}).get("summary", "")

    summary_text = (summary_text or "").strip()
    if not summary_text:
        raise HTTPException(status_code=400, detail="Missing summary text")

    summary = Summary(
        user_id=current_user.id,
        course_id=payload.course_id,
        session_id=payload.session_id,
        source_filename=payload.source_filename,
        title=payload.title,
        summary_text=summary_text,
        slides_payload=payload.slides_payload,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


@app.get("/api/summaries", response_model=list[SummaryOut])
def list_summaries(
    course_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Summary).filter(Summary.user_id == current_user.id)
    if course_id:
        query = query.filter(Summary.course_id == course_id)
    return query.order_by(Summary.created_at.desc()).all()




@app.post("/api/extract")
async def extract_endpoint(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Please upload a .pptx file")

    # Optional auth: if provided and valid, bind session to user
    current_user: Optional[User] = None
    if credentials:
        try:
            payload = decode_access_token(credentials.credentials)
            email = payload.get("sub")
            if email:
                current_user = db.query(User).filter(User.email == email).first()
        except ValueError:
            current_user = None

    slides = extract_text_by_slide(file.file)

    slides_payload = [
        {
            "page": s.get("page"),
            "title": s.get("title"),
            "text": s.get("text"),
            "bullets": [],
        }
        for s in slides
    ]

    sid = create_session(
        " ".join((s.get("text") or "") for s in slides),
        "",
        slides_payload,
        user_id=current_user.id if current_user else None,
    )

    return {
        "session_id": sid,
        "slides": [
            {"page": s.get("page"), "title": s.get("title"), "text": s.get("text")}
            for s in slides
        ],
    }


@app.post("/api/summarize/slide")
async def summarize_one(
    session_id: str = Form(...),
    page: int = Form(...),
    title: str = Form(""),
    text: str = Form(...),
):
    try:
        bullets = summarize_slide(text, ratio=0.65, max_bullets=10)

        sess = get_session(session_id)
        if sess is not None:
            for sl in sess.setdefault("slides", []):
                if sl.get("page") == page:
                    sl["bullets"] = bullets
                    break

            section = f"🧾 **Slide {page}: {title}**\n" + "\n".join(f"• {b}" for b in bullets)
            sess["summary"] = (sess.get("summary", "") + ("\n\n" if sess.get("summary") else "") + section)

        return {"page": page, "title": title, "bullets": bullets}
    except Exception as e:
        import traceback
        with open(r"C:\Users\AORUS\ai_lecture_summarizer\error_absolute.log", "a", encoding="utf-8") as f:
            f.write(f"Error on page {page}:\n")
            f.write(traceback.format_exc())
            f.write("\n\n")
        raise




@app.post("/api/chat")
async def chat_endpoint(
    message: str = Form(...),
    session_id: Optional[str] = Form(default=None),
    course_id: Optional[int] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    
    if course_id and not current_user:
        raise HTTPException(status_code=401, detail="Login required to save summaries")

    
    if file and file.filename:
        """if not file.filename.lower().endswith(".pptx"):
            raise HTTPException(status_code=400, detail="Please upload a .pptx file")"""

        slides_raw = extract_text_by_slide(file.file)
        slides_payload: list[dict] = []

        for s in slides_raw:
            title = (s.get("title") or "").strip()
            txt = (s.get("text") or "").strip()

            if not txt or len(txt.split()) < 12:
                bullets = [title] if title else ["(No readable text)"]
            else:
                bullets = summarize_slide(txt, ratio=0.65, max_bullets=10)

            slides_payload.append({"page": s.get("page"), "title": title, "text": txt, "bullets": bullets})

        final_summary = "\n\n".join(
            f"🧾 **Slide {sl['page']}: {sl['title']}**\n" + "\n".join(f"• {b}" for b in sl["bullets"])
            for sl in slides_payload
        ).strip()

        if not final_summary:
            final_summary = "No readable text extracted from the presentation."

        new_session_id = create_session(
            " ".join((s.get("text") or "") for s in slides_raw),
            final_summary,
            slides_payload,
            user_id=current_user.id if current_user else None,
        )

        saved_summary_id = None
        if current_user and course_id:
            course = (
                db.query(Course)
                .filter(Course.id == course_id, Course.owner_id == current_user.id)
                .first()
            )
            if not course:
                raise HTTPException(status_code=404, detail="Course not found")

            summary = Summary(
                user_id=current_user.id,
                course_id=course_id,
                session_id=new_session_id,
                source_filename=file.filename,
                title=slides_payload[0]["title"] if slides_payload else None,
                summary_text=final_summary,
                slides_payload=slides_payload,
            )
            db.add(summary)
            db.commit()
            db.refresh(summary)
            saved_summary_id = summary.id

        return {
            "response": "✅ Presentation summarized! Ask me about any slide.",
            "slides": slides_payload,
            "summary": final_summary,
            "session_id": new_session_id,
            "saved_summary_id": saved_summary_id,
        }

    
    if not session_id:
        raise HTTPException(status_code=400, detail="Session not found. Upload a PPTX first.")

    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Invalid session ID")

    
    sess_user_id = sess.get("user_id")
    if sess_user_id is not None and (not current_user or current_user.id != sess_user_id):
        raise HTTPException(status_code=403, detail="You do not have access to this session")

    msg = (message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message")

    lowered = msg.lower()

    #
    if lowered.startswith("generate assignment"):
        lecture_text = (sess.get("summary") or sess.get("pptx_text") or "").strip()
        if not lecture_text:
            ans = "⚠️ I don't have any lecture content yet. Upload and summarize a deck first."
        else:
            try:
                assignment = generate_assignment_from_lecture(lecture_text)
                ans = f"📘 Assignment generated:\n\n{assignment}"
            except Exception:
                logger.exception("Assignment generation failed")
                ans = "⚠️ Assignment generation failed. Check OPENAI_API_KEY and server logs."

        sess.setdefault("chat_history", []).append({"user": msg, "ai": ans})
        return {"response": ans, "session_id": session_id}

    if lowered.startswith("generate quiz"):
        lecture_text = (sess.get("summary") or sess.get("pptx_text") or "").strip()
        if not lecture_text:
            ans = "⚠️ I don't have any lecture content yet. Upload and summarize a deck first."
        else:
            try:
                quiz = generate_quiz_from_lecture(lecture_text)
                ans = f"📝 Quiz generated:\n\n{quiz}"
            except Exception:
                logger.exception("Quiz generation failed")
                ans = "⚠️ Quiz generation failed. Check OPENAI_API_KEY and server logs."

        sess.setdefault("chat_history", []).append({"user": msg, "ai": ans})
        return {"response": ans, "session_id": session_id}

    slides = sess.get("slides", []) or []

    
    slide_num = extract_slide_number(msg)
    if slide_num:
        hit = next((s for s in slides if s.get("page") == slide_num), None)
        if not hit:
            response = f"⚠️ Slide {slide_num} not found. This deck has {len(slides)} slides."
            sess.setdefault("chat_history", []).append({"user": msg, "ai": response})
            return {"response": response, "session_id": session_id}

        title = (hit.get("title") or "").strip()
        content = (hit.get("text") or "").strip()
        bullets = hit.get("bullets") or []

        if not content or len(content.split()) < 10:
            if bullets:
                combined_content = f"{title}\n\n" + "\n".join(bullets)
                slide_context = f"Title: {title}\n\nContent: {combined_content}"
            elif not content:
                response = f"📑 **Slide {hit.get('page')}: {title}**\n\n(This slide seems to be empty or contains only images.)"
                sess.setdefault("chat_history", []).append({"user": msg, "ai": response})
                return {"response": response, "session_id": session_id}
            else:
                slide_context = f"Title: {title}\n\nContent: {title}\n{content}"
        else:
            slide_context = f"Title: {title}\n\nContent: {content}"

        explanation_prompt = (
            "Provide a detailed explanation of this slide. Explain what it teaches, what the key concepts mean, "
            "and how they relate to each other. Be thorough and detailed. Use only the slide context."
        )

        try:
            explanation = explain_slide(slide_context, explanation_prompt)
        except Exception:
            logger.exception("Slide explanation failed")
            explanation = "⚠️ I couldn't generate an explanation right now. Please try again."

        response = f"📑 **Slide {hit.get('page')}: {title}**\n\n{explanation}"
        sess.setdefault("chat_history", []).append({"user": msg, "ai": response})
        return {"response": response, "session_id": session_id}

    # General Q&A: prefer relevant slides, else use summary, else use joined slide text
    pages_used: list[int] = []
    context = ""

    top = pick_relevant_slides(msg, slides, k=3)
    if top:
        pages_used = [s.get("page") for s in top if isinstance(s.get("page"), int)]
        context = "\n\n".join(
            f"Slide {s.get('page')}: {s.get('title', '')}\n" + "\n".join(s.get("bullets") or []) + f"\n{s.get('text', '')}"
            for s in top
        )
    else:
        summary_text = (sess.get("summary") or "").strip()
        if summary_text:
            context = summary_text
            pages_used = []
        else:
            context = "\n\n".join(
                f"Slide {s.get('page')}: {s.get('title', '')}\n{s.get('text', '')}"
                for s in slides
            )
            pages_used = [s.get("page") for s in slides if isinstance(s.get("page"), int)]

    context = (context or "")[:6000]

    try:
        answer = answer_question(context, msg)
    except Exception:
        logger.exception("QA failed")
        answer = "⚠️ I couldn't answer that right now. Please try again."

    sess.setdefault("chat_history", []).append({"user": msg, "ai": answer})
    return {"response": answer, "session_id": session_id, "used_slides": pages_used}



class SessionText(BaseModel):
    session_text: str


@app.post("/api/assignments/{course_id}")
def create_assignment(
    course_id: int,
    body: SessionText,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.owner_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lecture_text = (body.session_text or "").strip()
    if not lecture_text:
        raise HTTPException(status_code=400, detail="Empty lecture text")

    try:
        content = generate_assignment_from_lecture(lecture_text)
    except Exception:
        logger.exception("Assignment generation failed")
        raise HTTPException(status_code=502, detail="Assignment generation failed")

    assignment = Assignment(
        course_id=course_id,
        user_id=current_user.id,
        title="Assignment from lecture",
        content=content,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return {"id": assignment.id, "title": assignment.title, "content": assignment.content}


@app.post("/api/quizzes/{course_id}")
def create_quiz(
    course_id: int,
    body: SessionText,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.owner_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lecture_text = (body.session_text or "").strip()
    if not lecture_text:
        raise HTTPException(status_code=400, detail="Empty lecture text")

    try:
        content = generate_quiz_from_lecture(lecture_text)
    except Exception:
        logger.exception("Quiz generation failed")
        raise HTTPException(status_code=502, detail="Quiz generation failed")

    quiz = Quiz(
        course_id=course_id,
        user_id=current_user.id,
        title="Quiz from lecture",
        content=content,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return {"id": quiz.id, "title": quiz.title, "content": quiz.content}


@app.get("/api/courses/{course_id}/assignments", response_model=list[AssignmentOut])
def list_assignments(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.owner_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return (
        db.query(Assignment)
        .filter(Assignment.course_id == course_id, Assignment.user_id == current_user.id)
        .order_by(Assignment.created_at.desc())
        .all()
    )


@app.get("/api/courses/{course_id}/quizzes", response_model=list[QuizOut])
def list_quizzes(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = (
        db.query(Course)
        .filter(Course.id == course_id, Course.owner_id == current_user.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return (
        db.query(Quiz)
        .filter(Quiz.course_id == course_id, Quiz.user_id == current_user.id)
        .order_by(Quiz.created_at.desc())
        .all()
    )




@app.get("/api/debug/session/{session_id}")
async def debug_session(
    session_id: str,
):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    return {
        "pptx_text_preview": (sess.get("pptx_text") or "")[:1000],
        "summary": sess.get("summary"),
        "slides_count": len(sess.get("slides", [])),
        "slides": sess.get("slides", []),
        "chat_history": sess.get("chat_history", []),
    }


@app.get("/api/debug/sessions")
async def debug_sessions_list(current_user: User = Depends(get_current_user)):
    # Do not expose this without auth.
    return {"sessions": list(sessions.keys())}
