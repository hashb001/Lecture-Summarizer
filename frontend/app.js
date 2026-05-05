const API_BASE = window.location.origin;

let sessionId = null;
let lectureText = "";
const TOKEN_KEY = "ai_lecture_token";
const CHATS_KEY = "ai_lecture_chats";

// Load chats from localStorage so they survive page refresh
let chats = [];
try { chats = JSON.parse(localStorage.getItem(CHATS_KEY) || "[]"); } catch (_) { chats = []; }

let currentChat = { id: Date.now(), title: "New Chat", messages: [] };


const messagesDiv = document.getElementById("messages");
const sendBtn = document.getElementById("sendBtn");
const userInput = document.getElementById("userInput");
const fileInput = document.getElementById("fileInput");
const chatHistory = document.getElementById("chatHistory");
const newChatBtn = document.getElementById("newChatBtn");

const progressBox = document.getElementById("progress");
const progressBar = document.getElementById("progress-bar");
const progressTxt = document.getElementById("progress-text");

const authStatus = document.getElementById("authStatus");
const authNameInput = document.getElementById("authName");
const authEmailInput = document.getElementById("authEmail");
const authPasswordInput = document.getElementById("authPassword");
const registerBtn = document.getElementById("registerBtn");
const loginBtn = document.getElementById("loginBtn");
const logoutBtn = document.getElementById("logoutBtn");

const coursePanel = document.getElementById("coursePanel");
const courseSelect = document.getElementById("courseSelect");
const courseNameInput = document.getElementById("courseName");
const courseSubjectInput = document.getElementById("courseSubject");
const createCourseBtn = document.getElementById("createCourseBtn");

const summaryList = document.getElementById("summaryList");
const summaryEmpty = document.getElementById("summaryEmpty");

const assignmentList = document.getElementById("assignmentList");
const assignmentEmpty = document.getElementById("assignmentEmpty");

const quizList = document.getElementById("quizList");
const quizEmpty = document.getElementById("quizEmpty");

const themeToggle = document.getElementById("themeToggle");


function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function setAuthBusy(isBusy) {
  registerBtn.disabled = isBusy;
  loginBtn.disabled = isBusy;
  logoutBtn.disabled = isBusy;
  authNameInput.disabled = isBusy;
  authEmailInput.disabled = isBusy;
  authPasswordInput.disabled = isBusy;
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) data = await res.json();
  else data = await res.text();

  if (!res.ok) {
    const msg = (data && data.detail) ? data.detail : (typeof data === "string" ? data : "Request failed");
    throw new Error(msg);
  }
  return data;
}

function setProgress(pct, text) {
  progressBox.classList.remove("hidden");
  progressTxt.textContent = text || "";
  if (!progressBar.querySelector(".bar")) {
    progressBar.innerHTML = `<div class="bar"></div>`;
  }
  progressBar.querySelector(".bar").style.width = `${pct}%`;
  if (pct >= 100) setTimeout(() => progressBox.classList.add("hidden"), 600);
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[m]));
}

function appendMessage(text, sender) {
  const msg = document.createElement("div");
  msg.className = `message ${sender}`;
  // keep it safe for user text; AI text may include simple formatting
  msg.innerHTML = sender === "user" ? escapeHtml(text) : text;
  messagesDiv.appendChild(msg);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function renderSlideCard(page, title, bullets) {
  const wrapper = document.createElement("div");
  wrapper.className = "slide-card";
  const h = document.createElement("div");
  h.className = "slide-title";
  h.innerHTML = `📑 <strong>Slide ${page}:</strong> ${escapeHtml(title || "")}`;
  const ul = document.createElement("ul");
  ul.className = "slide-bullets";
  (bullets || []).forEach((b) => {
    const li = document.createElement("li");
    li.textContent = b;
    ul.appendChild(li);
  });
  wrapper.appendChild(h);
  wrapper.appendChild(ul);
  messagesDiv.appendChild(wrapper);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function refreshChatList() {
  chatHistory.innerHTML = "";
  chats.forEach((c) => {
    const li = document.createElement("li");
    li.textContent = c.title || "Chat";
    li.onclick = () => {
      currentChat = c;
      messagesDiv.innerHTML = "";
      c.messages.forEach((m) => appendMessage(m.text, m.sender));
    };
    chatHistory.appendChild(li);
  });
}

function saveMessage(text, sender) {
  currentChat.messages.push({ text, sender });
  if (!chats.find((c) => c.id === currentChat.id)) chats.unshift(currentChat);
  // Keep only last 30 chats to avoid bloat
  if (chats.length > 30) chats = chats.slice(0, 30);
  try { localStorage.setItem(CHATS_KEY, JSON.stringify(chats)); } catch (_) { }
  refreshChatList();
}


function showAuthInputs() {
  authNameInput.classList.remove("hidden");
  authEmailInput.classList.remove("hidden");
  authPasswordInput.classList.remove("hidden");
  registerBtn.classList.remove("hidden");
  loginBtn.classList.remove("hidden");
}

function hideAuthInputs() {
  authNameInput.classList.add("hidden");
  authEmailInput.classList.add("hidden");
  authPasswordInput.classList.add("hidden");
  registerBtn.classList.add("hidden");
  loginBtn.classList.add("hidden");
}

function clearAuthInputs() {
  authNameInput.value = "";
  authEmailInput.value = "";
  authPasswordInput.value = "";
}

function setGuestUI() {
  authStatus.innerHTML = `<strong>Guest mode (sign in to save summaries)</strong>`;
  showAuthInputs();
  coursePanel.classList.add("hidden");
  logoutBtn.classList.add("hidden");
}

function setUserUI(user) {
  authStatus.innerHTML = `<strong>Signed in:</strong> ${escapeHtml(user.email)}${user.full_name ? ` <span class="muted">(${escapeHtml(user.full_name)})</span>` : ""}`;
  hideAuthInputs();
  clearAuthInputs();
  coursePanel.classList.remove("hidden");
  logoutBtn.classList.remove("hidden");
}

async function refreshMe() {
  const token = getToken();
  if (!token) {
    setGuestUI();
    return null;
  }
  try {
    const me = await apiFetch("/api/auth/me");
    setUserUI(me);
    return me;
  } catch (e) {
    // token invalid/expired
    setToken(null);
    setGuestUI();
    return null;
  }
}


async function loadCourses() {
  const me = await refreshMe();
  if (!me) return;

  const courses = await apiFetch("/api/courses");
  courseSelect.innerHTML = "";
  courses.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.name}${c.subject ? " — " + c.subject : ""}`;
    courseSelect.appendChild(opt);
  });

  await loadSummaries();
  await loadAssignments();
  await loadQuizzes();
}

async function loadSummaries() {
  const courseId = courseSelect.value;
  if (!courseId) return;

  const summaries = await apiFetch(`/api/summaries?course_id=${encodeURIComponent(courseId)}`);
  summaryList.innerHTML = "";
  if (!summaries.length) {
    summaryEmpty.classList.remove("hidden");
    return;
  }
  summaryEmpty.classList.add("hidden");

  summaries.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = `${s.title} (${new Date(s.created_at).toLocaleString()})`;
    li.onclick = () => {
      messagesDiv.innerHTML = "";
      appendMessage(`<strong>${escapeHtml(s.title)}</strong><br><br>${escapeHtml(s.summary_text || "")}`, "ai");
    };
    summaryList.appendChild(li);
  });
}

async function loadAssignments() {
  const courseId = courseSelect.value;
  if (!courseId) return;

  const items = await apiFetch(`/api/courses/${courseId}/assignments`);
  assignmentList.innerHTML = "";
  if (!items.length) {
    assignmentEmpty.classList.remove("hidden");
    return;
  }
  assignmentEmpty.classList.add("hidden");

  items.forEach((a) => {
    const li = document.createElement("li");
    li.textContent = `${a.title} (${new Date(a.created_at).toLocaleString()})`;
    li.onclick = () => {
      messagesDiv.innerHTML = "";
      const contentHtml = escapeHtml(a.content || "").replace(/\n/g, "<br>");
      appendMessage(`<strong>${escapeHtml(a.title)}</strong><br><br>${contentHtml}`, "ai");
    };
    assignmentList.appendChild(li);
  });
}

async function loadQuizzes() {
  const courseId = courseSelect.value;
  if (!courseId) return;

  const items = await apiFetch(`/api/courses/${courseId}/quizzes`);
  quizList.innerHTML = "";
  if (!items.length) {
    quizEmpty.classList.remove("hidden");
    return;
  }
  quizEmpty.classList.add("hidden");

  items.forEach((q) => {
    const li = document.createElement("li");
    li.textContent = `${q.title} (${new Date(q.created_at).toLocaleString()})`;
    li.onclick = () => {
      messagesDiv.innerHTML = "";
      const contentHtml = escapeHtml(q.content || "").replace(/\n/g, "<br>");
      appendMessage(`<strong>${escapeHtml(q.title)}</strong><br><br>${contentHtml}`, "ai");
    };
    quizList.appendChild(li);
  });
}


async function sendMessage() {
  const txt = userInput.value.trim();
  if (!txt) return;

  appendMessage(txt, "user");
  saveMessage(txt, "user");
  userInput.value = "";

  try {
    const formData = new FormData();
    formData.append("message", txt);
    if (sessionId) formData.append("session_id", sessionId);

    const res = await apiFetch("/api/chat", { method: "POST", body: formData });
    const reply = res.response || "No response";
    // Convert newlines to <br> so multi-line quiz/assignment content renders correctly
    const replyHtml = escapeHtml(reply).replace(/\n/g, "<br>");
    appendMessage(replyHtml, "ai");
    saveMessage(reply, "ai");

    if (res.session_id) sessionId = res.session_id;
  } catch (err) {
    const msg = `❌ ${err.message}`;
    appendMessage(escapeHtml(msg), "ai");
    saveMessage(msg, "ai");
  }
}


fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  try {
    setProgress(3, "Uploading & extracting slides…");

    const form1 = new FormData();
    form1.append("file", file);

    const d1 = await apiFetch("/api/extract", { method: "POST", body: form1 });

    sessionId = d1.session_id;
    const slides = d1.slides || [];
    lectureText = slides.map((s) => s.text || "").join("\n\n");

    messagesDiv.innerHTML = "";
    const total = slides.length || 1;

    for (let i = 0; i < slides.length; i++) {
      setProgress(Math.round(((i + 1) / total) * 100), `Summarizing slide ${i + 1}/${total}…`);

      const s = slides[i];
      const form2 = new FormData();
      form2.append("session_id", sessionId);
      form2.append("page", s.page);
      form2.append("title", s.title || "");
      form2.append("text", s.text || "");

      const d2 = await apiFetch("/api/summarize/slide", { method: "POST", body: form2 });
      renderSlideCard(d2.page, d2.title, d2.bullets || []);
    }

    setProgress(100, "Done");
    currentChat.title = file.name || "PPTX summary";

    // Save summary to the selected course (if logged in and course selected)
    const courseId = courseSelect ? courseSelect.value : null;
    if (courseId && getToken()) {
      try {
        await apiFetch("/api/summaries", {
          method: "POST",
          body: JSON.stringify({
            course_id: parseInt(courseId),
            session_id: sessionId,
            source_filename: file.name,
            title: file.name.replace(/\.pptx$/i, ""),
          }),
        });
        await loadSummaries();
      } catch (saveErr) {
        console.warn("Could not save summary to course:", saveErr.message);
      }
    }

    refreshChatList();
    fileInput.value = "";
  } catch (err) {
    renderSlideCard("-", "Error", [err.message]);
    fileInput.value = "";
  }
});

sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage();
});

newChatBtn.addEventListener("click", () => {
  currentChat = { id: Date.now(), title: "New Chat", messages: [] };
  sessionId = null;
  lectureText = "";
  messagesDiv.innerHTML = "";
  refreshChatList();
});

// Auth: register
registerBtn.addEventListener("click", async () => {
  setAuthBusy(true);
  try {
    const full_name = authNameInput.value.trim();
    const email = authEmailInput.value.trim();
    const password = authPasswordInput.value;

    if (!email || !password) throw new Error("Email and password are required.");

    await apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ full_name, email, password }),
    });

    const tok = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    setToken(tok.access_token);
    await loadCourses();
  } catch (e) {
    alert(e.message);
  } finally {
    setAuthBusy(false);
  }
});


loginBtn.addEventListener("click", async () => {
  setAuthBusy(true);
  try {
    const email = authEmailInput.value.trim();
    const password = authPasswordInput.value;

    if (!email || !password) throw new Error("Email and password are required.");

    const tok = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    setToken(tok.access_token);
    await loadCourses();
  } catch (e) {
    alert(e.message);
  } finally {
    setAuthBusy(false);
  }
});


logoutBtn.addEventListener("click", async () => {
  setAuthBusy(true);
  try {
    setToken(null);
    setGuestUI();


    courseSelect.innerHTML = "";
    summaryList.innerHTML = "";
    assignmentList.innerHTML = "";
    quizList.innerHTML = "";
    summaryEmpty.classList.remove("hidden");
    assignmentEmpty.classList.remove("hidden");
    quizEmpty.classList.remove("hidden");
  } finally {
    setAuthBusy(false);
  }
});


themeToggle.addEventListener("click", () => {
  document.body.classList.toggle("dark");
  themeToggle.textContent = document.body.classList.contains("dark") ? "Light" : "Dark";
});


createCourseBtn.addEventListener("click", async () => {
  try {
    const name = courseNameInput.value.trim();
    const subject = courseSubjectInput.value.trim();
    if (!name) throw new Error("Course name is required.");

    await apiFetch("/api/courses", {
      method: "POST",
      body: JSON.stringify({ name, subject }),
    });

    courseNameInput.value = "";
    courseSubjectInput.value = "";
    await loadCourses();
  } catch (e) {
    alert(e.message);
  }
});

courseSelect.addEventListener("change", async () => {
  await loadSummaries();
  await loadAssignments();
  await loadQuizzes();
});

// Init
refreshChatList();
refreshMe().then((me) => {
  if (me) loadCourses();
});