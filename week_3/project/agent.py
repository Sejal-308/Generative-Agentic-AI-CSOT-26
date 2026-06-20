"""
Research Desk — Week 3 Project
===============================
Class hierarchy:
  Agent       — brain: chat(), _run_loop(), dispatch(), sessions
  REPLAgent   — terminal REPL + one-shot CLI
  TUIAgent    — Textual UI (in tui.py)
"""

import os
import sys
import json

import uuid


from datetime import datetime, timezone

from openai import OpenAI
from dotenv import load_dotenv

# --- Import our specialized tools ---
from tools.files import read_file, write_file, edit_file, list_files
from tools.web import search_web, read_page
from tools.papers import paper_search, read_paper

load_dotenv()

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
MAX_ITERATIONS = 10
SESSIONS_DIR = ".agent/sessions"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
MODEL = "deepseek/deepseek-v4-flash:free"


TOOLS = [
    
    {
        "type": "function", "function": {"name": "read_file", "description": "Read specific lines from a file.", 
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "read_lines": {"type": "integer"}}, "required": ["path"]}}
    },
    {
        "type": "function", "function": {"name": "write_file", "description": "Create or overwrite a file.", 
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}
    },
    {
        "type": "function", "function": {"name": "edit_file", "description": "Edit specific lines in a file (replace, delete, append).", 
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "operation": {"type": "string", "enum": ["replace", "delete", "append"]}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}, "content": {"type": "string"}}, "required": ["path", "operation", "start_line"]}}
    },
    {
        "type": "function", "function": {"name": "list_files", "description": "List files matching a pattern.", 
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}}}}
    },
    # Web Tools
    {
        "type": "function", "function": {"name": "search_web", "description": "Search the live internet via Serper.", 
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}
    },
    {
        "type": "function", "function": {"name": "read_page", "description": "Read the text of a webpage.", 
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}
    },
    # Paper Tools
    {
        "type": "function", "function": {"name": "paper_search", "description": "Search Hugging Face for academic papers.", 
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}
    },
    {
        "type": "function", "function": {"name": "read_paper", "description": "Read an academic paper by its ID.", 
        "parameters": {"type": "object", "properties": {"arxiv_id": {"type": "string"}}, "required": ["arxiv_id"]}}
    }
]

def build_system_prompt() -> str:
    base_prompt = "You are Research Desk, an elite AI research assistant with access to the web, academic papers, and the file system."
    if os.path.exists("AGENTS.md"):
        with open("AGENTS.md", "r") as f:
            return base_prompt + "\n\n# Project Rules\n" + f.read()
    return base_prompt


class Agent:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.messages = [{"role": "system", "content": build_system_prompt()}]
        
        
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        session_path = os.path.join(SESSIONS_DIR, f"{self.session_id}.json")
        if os.path.exists(session_path):
            with open(session_path, "r") as f:
                data = json.load(f)
                self.messages = data.get("messages", self.messages)

    def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        final_answer = self._run_loop()
        
        
        session_path = os.path.join(SESSIONS_DIR, f"{self.session_id}.json")
        with open(session_path, "w") as f:
            json.dump({
                "id": self.session_id, 
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "messages": self.messages
            }, f, indent=2)
            
        return final_answer

    def run_once(self, prompt: str) -> str:
        return self.chat(prompt)

    def _run_loop(self) -> str:
        for _ in range(MAX_ITERATIONS):
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.messages,
                tools=TOOLS
            )
            msg = response.choices[0].message
            
            if msg.finish_reason == "tool_calls":
                self.messages.append(msg)
                for tool_call in msg.tool_calls:
                    self._emit("tool_call", name=tool_call.function.name)
                    result_str = self.dispatch(tool_call)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str
                    })
            else:
                self.messages.append({"role": "assistant", "content": msg.content})
                return msg.content
                
        return f"[Agent stopped: MAX_ITERATIONS ({MAX_ITERATIONS}) reached]"

    def dispatch(self, tool_call) -> str:
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse arguments."})
            
        try:
            if name == "read_file": 
                result = read_file(**args)
            elif name == "write_file": 
                result = write_file(**args)
            elif name == "edit_file": 
                result = edit_file(**args)
            elif name == "list_files": 
                result = list_files(**args)
            elif name == "search_web": 
                result = search_web(**args)
            elif name == "read_page": 
                result = read_page(**args)
            elif name == "paper_search": 
                result = paper_search(**args)
            elif name == "read_paper": 
                result = read_paper(**args)
            else: 
                result = {"error": f"Unknown tool: {name}"}
        except Exception as e:
            result = {"error": str(e)}
            
        return json.dumps(result)

    def _emit(self, event: str, **data) -> None:
        pass



class REPLAgent(Agent):
    def run(self) -> None:
        print(f"Research Desk [{self.session_id}] — /quit to exit")
        while True:
            try:
                user_input = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_input or user_input in ("/quit", "/exit"):
                break
            print(self.chat(user_input))
            print()

    def _emit(self, event: str, **data) -> None:
        if event == "tool_call":
            print(f"  [tool] {data.get('name')}", file=sys.stderr)



def main():
    args = sys.argv[1:]
    session_id = None

    
    if "--session" in args:
        idx = args.index("--session")
        if idx + 1 < len(args):
            session_id = args[idx + 1]
            del args[idx:idx+2] 

    # 1. Textual TUI Mode
    if "--tui" in args:
        
        from tui import TUIAgent
        TUIAgent(session_id=session_id).run()
        
    
    elif args:
        agent = REPLAgent(session_id=session_id)
        print(agent.run_once(" ".join(args)))
        
    
    else:
        agent = REPLAgent(session_id=session_id)
        agent.run()

if __name__ == "__main__":
    main()