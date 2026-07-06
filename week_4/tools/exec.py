import os
import shlex
import subprocess

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
TIMEOUT_DEFAULT = 10
MAX_OUTPUT_CHARS = 8_000
READ_ONLY_PREFIXES = (
    "grep", "find", "ls", "cat", "head", "tail", "wc",
    "git log", "git diff", "git status", "git blame", "git show",
    "pytest", "python -m pytest", "ruff", "flake8", "mypy",
)
DESTRUCTIVE_PATTERNS = (
    "rm ", "mv ", ">", ">>", "git commit", "git push", "git checkout --",
    "pip install", "npm install", "curl ", "sudo ", "chmod ",
)


def paths_within_sandbox(command: str, workspace_root: str) -> bool:
    for token in shlex.split(command):
        if looks_like_a_path(token):
            abs_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, token))
            if not abs_path.startswith(WORKSPACE_ROOT):
                return False
    return True
    
    

def looks_like_a_path(token: str)->bool:
    if "/" in token or "\\" in token:
        return True
    if token.startswith("./") or token.startswith("../") or token == "." or token == "..":
        return True
    _, ext = os.path.splitext(token)
    if ext and not token.startswith('-'):
        return True
    return False

def classify_command(command: str) -> str:
    if not paths_within_sandbox(command, WORKSPACE_ROOT):
        return {"error": "blocked: command references a path outside the workspace"}
    if any(pattern in command for pattern in DESTRUCTIVE_PATTERNS):
        return "ask"
    if any(command.startswith(prefix) for prefix in READ_ONLY_PREFIXES):
        return "read-only"
    return "ask"

def run_command(command: str, cwd: str = WORKSPACE_ROOT, timeout: int = TIMEOUT_DEFAULT) -> dict:
    if not paths_within_sandbox(command, WORKSPACE_ROOT):
        return {"error": "blocked: command references a path outside the workspace"}
    classify=classify_command(command)

    if classify=="ask":
        print("WARNING: the agent wants to run a command that may write, delete, or install:")
        print("    " + command)
        approved = input("Allow this command? [y/N]: ").strip().lower() == "y"
        if not approved:
            return {"error": "blocked: user did not approve this command"}
    
    try:
        result= subprocess.run(command, shell=True, cwd=cwd,
                timeout=timeout, capture_output=True, text=True)
        stdout_raw = result.stdout or ""
        stderr_raw = result.stderr or ""
        exit_code = result.returncode
    except subprocess.TimeoutExpired as e:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds.",
            "exit_code": -1,
            "truncated": False
        }
    truncated = False
    if len(stdout_raw)>MAX_OUTPUT_CHARS:
        stdout_raw=stdout_raw[:MAX_OUTPUT_CHARS]+"\n"+"(Output truncated)"
        truncated=True
    if len(stderr_raw)>MAX_OUTPUT_CHARS:
        stderr_raw=stderr_raw[:MAX_OUTPUT_CHARS]+"\n"+"(error output truncated)"
        truncated=True
    return {
            "stdout": stdout_raw,
            "stderr": stderr_raw,
            "exit_code": exit_code,
            "truncated": truncated
        }
        


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the workspace and return its output. "
                "Use this to search (grep/find), inspect history (git log/diff), "
                "run tests, or make a change. Read-only commands run immediately. "
                "Anything that writes, deletes, or installs will pause and ask the "
                "human operator for approval — expect that pause, it's not a failure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"Seconds before the command is killed. Default {TIMEOUT_DEFAULT}.",
                    },
                },
                "required": ["command"],
            },
        },
    }
]


if __name__ == "__main__":
    print("Read-only command (should run immediately):")
    print(run_command("git log --oneline -5"))

    print("\nDestructive command (should pause and ask for approval):")
    print(run_command("rm -rf /tmp/does-not-exist-example"))
