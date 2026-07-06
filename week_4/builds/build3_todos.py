"""
Build 3: Todo Tools
======================
A todo list the model maintains itself — what it's planning to do, what
it's actually done, and how it'll know each item really worked.

This build is intentionally less prescriptive than Builds 1 and 2. You
decide the exact shape of a todo and how the list is stored — in memory,
in a dict, in a JSON file under .agent/, however you like. The one hard
requirement, from Lesson 2: every todo needs a short title, a
description, and a verification method — some concrete, checkable way
to know the item is actually done ("run pytest tests/test_auth.py and
confirm exit code 0"), not just a status flag the model sets on its own
say-so.

Tasks (design these yourself — the signatures below are a starting
point, not a contract you have to match):
  1. add_todos(...)  — add one or more todos to the list
  2. get_todos(...)  — return the current list, however you choose to
     filter or shape it
  3. mark_todo(...)  — update a todo's status
  4. Once you've settled on a shape, write the TOOLS schema yourself
     and wire it into the agent loop's stop condition (Lesson 2) — the
     loop shouldn't consider itself done while a todo is incomplete.

Questions to resolve before you write code — there's no single right
answer, but you should be able to defend whatever you pick:
  - What does "status" need to express? pending/in_progress/completed
    is Lesson 2's minimum — is that enough once verification enters
    the picture, or do you need something like "blocked" too?
  - Should mark_todo require evidence (e.g. a command's exit code)
    before it'll accept "completed," and refuse otherwise? Lesson 2's
    "Completed Should Mean Verified, Not Just Claimed" argues yes —
    decide how strict to make that in code.
  - Where does the list live, and what survives a resumed session
    (Week 3)? A module-level list won't survive a process restart;
    is that good enough for this build, or do you need it on disk?
  - Should add_todos take one todo or a whole plan at once? (Lesson 2's
    todo_write always sends the full current list back — you don't
    have to copy that design, but know why it might matter.)

Run directly once you've implemented something real: add a couple of
todos, mark one in_progress, try to mark it completed without evidence
and see whether your own rules let that happen, then get_todos() and
confirm the list reflects what you'd expect.
"""
import json
import os
import uuid

TODO_FILE = os.path.join(".agent", "todos.json")
ALLOWED_STATUSES = {"pending", "in_progress", "blocked", "verified"}
# TODO: pick your own storage. A plain list/dict at module scope is fine
# to start; revisit once you decide whether todos need to survive a
# resumed session.
def storage():
    os.makedirs(os.path.dirname(TODO_FILE), exist_ok=True)
    if not os.path.exists(TODO_FILE):
        with open(TODO_FILE, "w") as f:
            json.dump([], f)
# implement the following: add_todos, get_todos, mark_todo

def read_todos():
    storage()
    try:
        with open(TODO_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []
    
def write_todos(todos):
    storage()
    with open(TODO_FILE, "w") as f:
        json.dump(todos, f, indent=2)

def add_todos(todos_list):
    for key in todos_list:
        if key not in ALLOWED_STATUSES: 
          return {"error": "Input must be a list of todo objects"}
        existing_todos = read_todos()
    added_items = []
    
    for item in todos_list:
        if not all(k in item for k in ("title", "description", "verification")):
            return {"error": "Each todo must contain title, description, and verification"}
            
        todo_id = uuid.uuid4().hex[:8]
        new_todo = {
            "id": todo_id,
            "title": str(item["title"]),
            "description": str(item["description"]),
            "verification": str(item["verification"]),
            "status": "pending"
        }
        existing_todos.append(new_todo)
        added_items.append(new_todo)
        
    write_todos(existing_todos)
    return {"added_todos": added_items}

def get_todos(status_filter=None):
    todos = read_todos()
    if status_filter:
        if status_filter not in ALLOWED_STATUSES:
            return {"error": f"Invalid status filter. Must be one of {list(ALLOWED_STATUSES)}"}
        todos = [t for t in todos if t["status"] == status_filter]
    return {"todos": todos}

def mark_todo(todo_id, status, exit_code=None):
    if status not in ALLOWED_STATUSES:
        return {"error": f"Invalid status. Must be one of {list(ALLOWED_STATUSES)}"}
        
    todos = read_todos()
    target_todo = None
    
    for t in todos:
        if t["id"] == todo_id:
            target_todo = t
            break
            
    if not target_todo:
        return {"error": f"Todo with ID {todo_id} not found"}
        
    if status == "verified":
        if exit_code is None or exit_code != 0:
            return {
                "error": "Rejected: Todo cannot be marked as verified unless validation exit_code is exactly 0",
                "current_status": target_todo["status"]
            }
            
    target_todo["status"] = status
    write_todos(todos)
    return {"success": f"Todo {todo_id} updated to {status}", "todo": target_todo}

def verify_all_todos_complete():
    todos = read_todos()
    if not todos:
        return True
    return all(t["status"] == "verified" for t in todos)

        

# TODO: once the functions above have a settled shape, write the TOOLS
# schema for add_todos / get_todos / mark_todo yourself. Lesson 6 has
# the guidance on what makes a tool description the model actually
# follows — apply it here instead of copying Lesson 2's example verbatim.
TOOLS = [{
        "name": "add_todos",
        "description": "Register an execution plan containing one or multiple high-level tasks or milestones.",
        "parameters": {
            "type": "object",
            "properties": {
                "todos_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "verification": {"type": "string"}
                        },
                        "required": ["title", "description", "verification"]
                    }
                }
            },
            "required": ["todos_list"]
        }
    },
    {
        "name": "get_todos",
        "description": "Retrieve the current strategic task list to check progress, filtered optionally by status.",
        "parameters": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "blocked", "verified"]
                }
            }
        }
    },
    {
        "name": "mark_todo",
        "description": "Update the operational execution state of an explicitly targeted todo item.",
        "parameters": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "blocked", "verified"]
                },
                "exit_code": {"type": "integer"}
            },
            "required": ["todo_id", "status"]
        }
    }]


if __name__ == "__main__":
    # TODO: exercise add_todos / get_todos / mark_todo once they're real,
    # including the case where you try to mark something completed
    # without evidence — does your code stop you, or let it through?
    if os.path.exists(TODO_FILE):
        os.remove(TODO_FILE)
        
    plan = [
        {
            "title": "Fix Database Timeout",
            "description": "Increase pool checkout limit to 30 seconds.",
            "verification": "pytest tests/test_db.py"
        }
    ]
    add = add_todos(plan)
    todo_id = add["added_todos"][0]["id"]
    
    mark_todo(todo_id, status="in_progress")
    
    no_code = mark_todo(todo_id, status="verified")
    print("Result (No exit_code):", no_code)
    
    bad_code = mark_todo(todo_id, status="verified", exit_code=1)
    print("Result (Exit code 1):",bad_code)
    
    success = mark_todo(todo_id, status="verified", exit_code=0)
    print("Result (Exit code 0):", success)
