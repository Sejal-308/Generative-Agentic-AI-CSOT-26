import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv


from sessions import create_session, load_session, save_session, build_system_prompt


from tools.exec import run_command
from tools.files import read_file, write_file, edit_file, list_files
from tools.plan import add_todos, get_todos, mark_todo
from tools.search import grep, list_definitions as search_list_files

load_dotenv()


from tools.exec import TOOLS as etools
from tools.files import TOOLS as ftools
from tools.plan import TOOLS as ptools
from tools.search import TOOLS as setools

TOOLS = etools + ftools + ptools + setools

TOOL_REGISTRY = {
    "run_command": run_command,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_files": list_files,
    "add_todos": add_todos,
    "get_todos": get_todos,
    "mark_todo": mark_todo,
    "grep": grep
}

class Agent:
    """The Base Brain: Manages state, API calls, tool dispatching, and the verification loop."""
    def __init__(self, workspace=".", session_id=None):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY")
        )
        self.model = "openrouter/free"
        self.workspace = workspace
        
        # Initialize or restore persistent session history
        self.session_id = session_id or create_session()
        session_data = load_session(self.session_id)
        
        if session_data and "messages" in session_data:
            self.messages = session_data["messages"]
        else:
            # Generate the default baseline system prompt
            system_prompt = build_system_prompt()
            
            agents_md_path = os.path.join(self.workspace, "AGENTS.md")
            if os.path.exists(agents_md_path):
                try:
                    with open(agents_md_path, "r", encoding="utf-8") as f:
                        agents_content = f.read()
                    # Append standing instructions explicitly to the system prompt
                    system_prompt += f"\n\n### Project-Specific Instructions (AGENTS.md):\n{agents_content}"
                except Exception as e:
                    sys.stderr.write(f"[Warning] Failed to read AGENTS.md: {e}\n")
            # --- END WEEK 4 AGENTS.md LOADING LOGIC ---

            self.messages = [{"role": "system", "content": system_prompt}]

    def dispatch(self, tool_call) -> str:
        """Matches tool requests to Python functions and returns JSON string results."""
        name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse arguments."})

        if name not in TOOL_REGISTRY:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            result = TOOL_REGISTRY[name](**arguments)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _emit(self, event: str, **data) -> None:
        """Blank hook for subclasses to override and display status."""
        pass

    def _run_loop(self) -> str:
        """The core ReAct loop with the new verification exit condition."""
        MAX_ITERATIONS = 20
        
        for _ in range(MAX_ITERATIONS):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=TOOLS
            )
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "tool_calls":
                self.messages.append(message)
                for tool_call in message.tool_calls:
                    self._emit("tool_start", name=tool_call.function.name)
                    
                    result_json = self.dispatch(tool_call)
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_json
                    })
            
            elif finish_reason == "stop":
                
                todos = get_todos()
                unverified_tasks = []
                for task in todos:
                    # Safe extraction checking if task is a dictionary or raw string
                    if isinstance(task, dict):
                        status = task.get("status", "pending")
                        description = task.get("description", task.get("name", "Unknown Task"))
                    else:
                        status = "pending"
                        description = str(task)
                    
                    # Track unverified items properly so the verification block activates
                    if status != "verified":
                        unverified_tasks.append(description)
                
                reply = message.content or ""
                self.messages.append({"role": "assistant", "content": reply})
                
                if unverified_tasks:
                    warning_msg = (
                        "Wait, your task list is not complete. The following tasks are not verified: "
                        f"{json.dumps(unverified_tasks)}. You must run tests to verify your fix and use mark_todo before finishing."
                    )
                    self._emit("verification_warning", content=warning_msg)
                    self.messages.append({"role": "user", "content": warning_msg})
                else:
                    return reply

        return f"Error: Agent stopped after {MAX_ITERATIONS} iterations without completing verification."

    def chat(self, user_message: str) -> str:
        """Entry point for a conversation step. Commits state to disk."""
        self.messages.append({"role": "user", "content": user_message})
        final_answer = self._run_loop()
        save_session(self.session_id, self.messages)
        return final_answer

    def run_once(self, prompt: str) -> str:
        """Wrapper method for a single-shot execution."""
        return self.chat(prompt)


class REPLAgent(Agent):
    
    def _emit(self, event: str, **data) -> None:
        
        if event == "tool_start":
            sys.stderr.write(f"\n[Agent] Executing tool: {data['name']}...\n")
        elif event == "verification_warning":
            sys.stderr.write(f"\n[System Loop] Agent attempted to exit early. Forcing verification...\n")

    def run(self) -> None:
       
        print(f"Code Scout Online. Session ID: {self.session_id}")
        print("Type '/quit' to exit.")
        
        while True:
            try:
                user_input = input("\n> ")
                if user_input.lower() in ['/quit', 'exit']:
                    break
                if not user_input.strip():
                    continue
                
                response = self.chat(user_input)
                print(f"\n[Agent] {response}")
            except (KeyboardInterrupt, EOFError):
                break


if __name__ == "__main__":
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        agent = REPLAgent()
        print(agent.run_once(prompt))
    else:
        agent = REPLAgent()
        agent.run()