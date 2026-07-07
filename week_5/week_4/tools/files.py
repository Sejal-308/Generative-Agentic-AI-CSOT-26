
import os

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
