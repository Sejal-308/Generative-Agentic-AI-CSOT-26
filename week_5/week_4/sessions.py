import json
import os
import uuid
from datetime import datetime, timezone

SESSIONS_DIR = ".agent/sessions"
AGENTS_PATHS = ("AGENTS.md", ".agent/AGENTS.md")

BASE_PROMPT = "You are a coding agent, who can read, summarize, modify and create files."

def ensure_session_dir():
    if not os.path.exists(SESSIONS_DIR):
        os.makedirs(SESSIONS_DIR, exist_ok=True)

def create_session():
    ensure_session_dir()
    session_id = str(uuid.uuid4())[:8]
    file_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"messages": []}, f)
    return session_id

def save_session(session_id: str, messages: list, title: str = "Untitled") -> None:
    ensure_session_dir()
    session_data = {
        "id": session_id,
        "title": title,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": messages
    }
    file_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

def load_session(session_id):
    ensure_session_dir()
    file_path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def list_sessions() -> list[dict]:
    ensure_session_dir()
    sessions = []
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith(".json"):
            file_path = os.path.join(SESSIONS_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "id": data.get("id") or filename.replace(".json", ""),
                        "title": data.get("title", "Untitled"),
                        "updated_at": data.get("updated_at", "")
                    })
            except Exception:
                continue
    sessions.sort(key=lambda x: x["updated_at"], reverse=True)
    return sessions

def build_system_prompt() -> str:
    prompt = BASE_PROMPT
    for path in AGENTS_PATHS:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                rules = f.read()
                prompt += f"\n\n# Project Rules\n{rules}"
            break  
    return prompt

if __name__ == "__main__":
    sid = create_session()
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": "What is a surface code?"},
        {"role": "assistant", "content": "A surface code is a type of quantum error correcting code."},
    ]
    save_session(sid, messages, title="Quantum error correction")
    print(f"Saved session: {sid}")
    print(f"All sessions: {list_sessions()}")
    print(f"Loaded: {load_session(sid).get('title', 'Untitled')}")