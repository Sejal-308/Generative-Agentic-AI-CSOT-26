import ast
import os
import re

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
MAX_GREP_RESULTS = 50
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

def resolve_path(path: str) -> str | None:
    """Resolve `path` inside WORKSPACE_ROOT; return None if it escapes."""
    # TODO: implement (same idea as Week 3's resolve_path)
      # silence "unused parameter" until implemented
    abs_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, path))
    if not abs_path.startswith(WORKSPACE_ROOT):
        return None
    return abs_path

def grep(
    pattern: str,
    path: str = ".",
    case_sensitive: bool = False,
    max_results: int = MAX_GREP_RESULTS,
) -> dict:
    resolved_base = resolve_path(path)
    if not resolved_base or not os.path.exists(resolved_base):
        return {"matches": [], "truncated": False, "total_matches": 0}
    
    matches = []
    total_matches = 0

    flags = 0 if case_sensitive else re.IGNORECASE

    for root, dirs, files in os.walk(resolved_base):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, WORKSPACE_ROOT)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, start=1):
                        if re.search(pattern, line, flags=flags):
                            total_matches += 1
                            if len(matches) < max_results:
                                matches.append({
                                    "file": rel_path,
                                    "line": line_no,
                                    "text": line.strip()
                                })
            except (PermissionError, FileNotFoundError):
                continue

    
    return {
        "matches": matches,
        "truncated": total_matches > max_results,
        "total_matches": total_matches
    }

def list_definitions(path: str) -> dict:
    resolved_path = resolve_path(path)
    if not resolved_path or not os.path.exists(resolved_path) or os.path.isdir(resolved_path):
        return {"error": "Invalid or missing file path"}

   
    try:
        with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
            source_code = f.read()
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}

   
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {"error": "Invalid Python syntax"}

    definitions = []

   
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.append({
                "kind": "function",
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno
            })
            
        elif isinstance(node, ast.ClassDef):
            definitions.append({
                "kind": "class",
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno
            })
            
            
            for sub_node in node.body:
                if isinstance(sub_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    definitions.append({
                        "kind": "method",
                        "name": f"{node.name}.{sub_node.name}",
                        "line": sub_node.lineno,
                        "end_line": sub_node.end_lineno
                    })

    
    return {"definitions": definitions}
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": (
                "Search file contents for a pattern across the workspace. "
                "Use this before read_file when you don't already know which "
                "file you need."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text or regex to search for."},
                    "path": {"type": "string", "description": "Subdirectory to search, default workspace root."},
                    "case_sensitive": {"type": "boolean", "description": "Default false."},
                    "max_results": {
                        "type": "integer",
                        "description": f"Cap on matches returned. Default {MAX_GREP_RESULTS}.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_definitions",
            "description": (
                "List the functions and classes declared in a Python file, "
                "with line numbers, without reading the whole file. Use this "
                "right after grep to decide which match is worth reading in "
                "full with read_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to a Python file."},
                },
                "required": ["path"],
            },
        },
    },
]


if __name__ == "__main__":
    print("Searching for top-level function definitions ('def '):")
    result = grep("def ", max_results=10)
    print(result)

    if result and result.get("matches"):
        first_file = result["matches"][0]["file"]
        print(f"\nOutline of {first_file}:")
        print(list_definitions(first_file))
