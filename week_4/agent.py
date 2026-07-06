import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv

# Import Session & Memory utilities (carried over from Week 3)
from sessions import create_session, load_session, save_session, build_system_prompt

# Import Week 4 Tools
from tools.exec import run_command
from tools.files import read_file, write_file, edit_file, list_files
from tools.plan import add_todos, get_todos, mark_todo
from tools.search import grep, list_definitions as search_list_files

# Load environment variables securely
load_dotenv()

# Assuming your TOOLS array schema is centrally defined in a schemas file or aggregated here.
from tools.exec import TOOLS as etools
from tools.files import TOOLS as ftools
from tools.plan import TOOLS as ptools
from tools.search import TOOLS as setools

TOOLS=etools+ftools+ptools+setools




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
            # Inject AGENTS.md procedural memory at startup
            system_prompt = build_system_prompt()
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
                # NEW WEEK 4 TASK VERIFICATION BOUNDARY
                # Do not let the agent declare victory if tasks remain incomplete.
                todos = get_todos()
                unverified_tasks = [task for task in todos if task.get("status") != "verified"]
                
                reply = message.content or ""
                self.messages.append({"role": "assistant", "content": reply})
                
                if unverified_tasks:
                    # Force the model to continue looping until the plan is genuinely verified
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
    """The Terminal Body: Adds human-facing text rendering over the base Agent."""
    
    def _emit(self, event: str, **data) -> None:
        """Intercepts internal hooks to print updates to the terminal."""
        if event == "tool_start":
            # Print tool executions securely to standard error
            sys.stderr.write(f"\n[Agent] Executing tool: {data['name']}...\n")
        elif event == "verification_warning":
            sys.stderr.write(f"\n[System Loop] Agent attempted to exit early. Forcing verification...\n")

    def run(self) -> None:
        """Drives the perpetual interactive terminal chat loop."""
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
    # Checks sys.argv to automatically determine execution mode
    if len(sys.argv) > 1:
        # Run Once Mode: python agent.py "why is test_auth.py failing — fix it"
        prompt = " ".join(sys.argv[1:])
        agent = REPLAgent()
        print(agent.run_once(prompt))
    else:
        # Interactive Terminal Mode: python agent.py
        agent = REPLAgent()
        agent.run()