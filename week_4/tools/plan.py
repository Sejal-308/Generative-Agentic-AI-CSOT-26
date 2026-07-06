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
