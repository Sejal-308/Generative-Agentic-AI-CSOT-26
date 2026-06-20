"""
Build 2: Agent + REPLAgent
===========================
Agent = brain (loop, tools, sessions). REPLAgent = terminal UI.

Before running:
  mkdir -p notes

Tasks:
  1. Agent — chat(), run_once(), _run_loop(), dispatch(), _emit(), session I/O
  2. REPLAgent(Agent) — run() interactive loop
  3. resolve_path, read_file, write_file, list_files, edit_file
  4. main() — one-shot: python build2_agent_class.py "hello"

TUIAgent comes in the project (tui.py). No Textual imports here.
"""
import uuid
import os
import sys
import json
import glob as glob_module
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
MAX_ITERATIONS = 10
MAX_READ_CHARS = 12_000

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
MODEL = "deepseek/deepseek-v4-flash:free"


# --- File tools ---

def resolve_path(path: str) -> str:
    abs_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, path))
    if not abs_path.startswith(WORKSPACE_ROOT):
        raise ValueError(f"Security violation: path {abs_path} is outside workspace.")
    return abs_path
    


def read_file(path: str, start_line: int = 1, read_lines: int = 200) -> dict:
    try:
        safe_path = resolve_path(path)
        if not os.path.exists(safe_path):
            return {"error": f"File not found: {path}"}
            
        with open(safe_path, 'r') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        start_idx = max(0, start_line - 1)
        end_idx = min(start_idx + read_lines, total_lines)
        
        chunk = "".join(lines[start_idx:end_idx])
        has_more = end_idx < total_lines
        
        return {
            "content": chunk, 
            "start_line": start_line, 
            "end_line": end_idx, 
            "total_lines": total_lines, 
            "has_more": has_more
        }
    except Exception as e:
        return {"error": str(e)}
    


def write_file(path: str, content: str) -> dict:
    try:
        safe_path = resolve_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, 'w') as f:
            f.write(content)
        return {"success": True, "path": path, "bytes": len(content)}
    except Exception as e:
        return {"error": str(e)}
    


def edit_file(
    path: str,
    operation: str,
    start_line: int,
    end_line: int | None = None,
    content: str | None = None,
) -> dict:
    try:
        safe_path = resolve_path(path)
        if not os.path.exists(safe_path):
            return {"error": f"File not found: {path}"}
            
        with open(safe_path, 'r') as f:
            lines = f.readlines()
            
        start_idx = max(0, start_line - 1)
        end_idx = max(0, end_line if end_line is not None else start_line)
        
        new_lines = content.splitlines(True) if content else []
        # Ensure the last line has a line break
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'

        if operation == "replace":
            lines[start_idx:end_idx] = new_lines
        elif operation == "delete":
            del lines[start_idx:end_idx]
        elif operation in ["insert", "append"]:
            lines[start_idx:start_idx] = new_lines
        else:
            return {"error": f"Unknown operation: {operation}. Use replace, delete, or insert."}

        with open(safe_path, 'w') as f:
            f.writelines(lines)
            
        return {"success": True, "operation": operation, "affected_lines": f"{start_line}-{end_line}"}
    except Exception as e:
        return {"error": str(e)}
    


def list_files(path: str = ".", pattern: str = "*") -> dict:
    try:
        safe_path = resolve_path(path)
        search_pattern = os.path.join(safe_path, "**", pattern)
        files = glob_module.glob(search_pattern, recursive=True)
        # Strip the absolute path so the AI just sees relative paths
        relative_files = [os.path.relpath(f, WORKSPACE_ROOT) for f in files if os.path.isfile(f)]
        return {"files": relative_files}
    except Exception as e:
        return {"error": str(e)}
    pass


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read specific lines from a file. Use this to safely inspect large files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "description": "Line to start reading from (1-indexed)."},
                    "read_lines": {"type": "integer", "description": "Number of lines to read."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or completely overwrite an existing one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit specific lines in an existing file. Operations: replace, delete, insert.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "operation": {"type": "string", "enum": ["replace", "delete", "insert"]},
                    "start_line": {"type": "integer", "description": "Starting line number (1-indexed)."},
                    "end_line": {"type": "integer", "description": "Ending line number. Required for replace/delete."},
                    "content": {"type": "string", "description": "New content to insert/replace."}
                },
                "required": ["path", "operation", "start_line"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in a directory matching a pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search (default '.')"},
                    "pattern": {"type": "string", "description": "Glob pattern (default '*')"}
                }
            }
        }
    }
]


class Agent:
    """Core agent: loop, tools, sessions. No UI."""

    def __init__(self, workspace: str = ".", session_id: str | None = None):
        self.workspace = os.path.abspath(workspace)
        # TODO: session_id, load messages
        self.session_id = session_id or uuid.uuid4().hex[:8]
        
        
        self.messages = [
            {"role": "system", "content": build_system_prompt()}
        ]
        
        
        session_path = os.path.join(".agent/sessions", f"{self.session_id}.json")
        if os.path.exists(session_path):
            with open(session_path, "r") as f:
                data = json.load(f)
                self.messages = data.get("messages", self.messages)
        

    def chat(self, user_message: str) -> str:
        # TODO: append user msg, _run_loop(), save session, return answer
        self.messages.append({"role": "user", "content": user_message})
        
        
        final_answer = self._run_loop()
        
        
        os.makedirs(".agent/sessions", exist_ok=True)
        session_path = os.path.join(".agent/sessions", f"{self.session_id}.json")
        with open(session_path, "w") as f:
            json.dump({"id": self.session_id, "messages": self.messages}, f, indent=2)
            
        return final_answer
        

    def run_once(self, prompt: str) -> str:
        
        return self.chat(prompt)

    def _run_loop(self) -> str:
        # TODO: agent loop — call self.dispatch(), self._emit() on tool calls
        for _ in range(MAX_ITERATIONS):
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.messages,
                tools=TOOLS
            )
            
            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            
            if finish_reason == "tool_calls":
                
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
                
        return f"[Agent stopped: max iteration ({MAX_ITERATIONS}) reached]"
        

    def dispatch(self, tool_call) -> str:
        # TODO: route to file tools, return JSON string
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
            else:
                result = {"error": f"Unknown tool: {name}"}
        except Exception as e:
            result = {"error": str(e)}
            
        return json.dumps(result)
        

    def _emit(self, event: str, **data) -> None:
        """Override in REPLAgent/TUIAgent for tool logging."""
    
        pass


class REPLAgent(Agent):
    """Terminal REPL + one-shot CLI."""

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


def build_system_prompt() -> str:
    
    base_prompt = (
        "You are an elite AI research assistant. You have full access to the user's file system "
        "to read, write, and edit files."
    )
    if os.path.exists("AGENTS.md"):
        with open("AGENTS.md", "r") as f:
            return base_prompt + "\n\n# Project Rules\n" + f.read()
    return base_prompt


def main():
    agent = REPLAgent()
    if len(sys.argv) > 1:
        print(agent.run_once(" ".join(sys.argv[1:])))
        return
    agent.run()


if __name__ == "__main__":
    main()