import os
import sys
import json
import asyncio
import re
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
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

def load_mcp_config(path="config.json"):
    """Read config.json and substitute ${ENV_VAR} references from the environment."""
    raw = open(path).read()
    
    def substitute(match):
        var = match.group(1)
        value = os.environ.get(var)
        if value is None:
            raise RuntimeError(f"config.json references ${{{var}}}, but it isn't set in your .env")
        return value

    resolved = re.sub(r"\$\{([A-Z0-9_]+)\}", substitute, raw)
    return json.loads(resolved)["mcpServers"]

def load_skills(skills_dir="skills"):
    """Scans the skills folder and extracts metadata from SKILL.md files."""
    skills_registry = {}
    if not os.path.exists(skills_dir):
        return skills_registry

    # Loop through subfolders inside the skills directory
    for folder in os.listdir(skills_dir):
        folder_path = os.path.join(skills_dir, folder)
        if os.path.isdir(folder_path):
            skill_file = os.path.join(folder_path, "SKILL.md")
            if os.path.exists(skill_file):
                content = open(skill_file, "r").read()
                
                # Simple extraction of the frontmatter description between '---'
                if content.startswith("---"):
                    parts = content.split("---")
                    frontmatter = parts[1]
                    body = parts[2]
                    
                    # Parse out the name and description lines
                    lines = [line.strip() for line in frontmatter.strip().split("\n")]
                    name = next(l.split(":")[1].strip() for l in lines if l.startswith("name:"))
                    desc = next(l.split(":")[1].strip() for l in lines if l.startswith("description:"))
                    
                    # Store both the description (for the LLM prompt) and the body instructions
                    skills_registry[name] = {"description": desc, "instructions": body}
                    
    return skills_registry

class MCPManager:
    """Connects to every server in the config and exposes their tools as one flat list."""
    def __init__(self):
        self.stack = AsyncExitStack()
        self.openai_tools = []        # Merged tool schemas for your LLM
        self.tool_to_session = {}     # Maps tool name -> the session that owns it

    async def connect_all(self, servers: dict):
        for name, cfg in servers.items():
            # streamablehttp_client yields three values (read, write, and session-id callback)
            read, write, _ = await self.stack.enter_async_context(
                streamablehttp_client(cfg["url"], headers=cfg.get("headers"))
            )
            session = await self.stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            
            tools = await session.list_tools()
            for tool in tools.tools:
                # Store the session so the loop knows who executes this tool
                self.tool_to_session[tool.name] = session
                self.openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                })
            print(f"Connected '{name}': {len(tools.tools)} tools loaded.")

    async def call_tool(self, name: str, args: dict) -> str:
        result = await self.tool_to_session[name].call_tool(name, args)
        return result.content[0].text if result.content else ""

    async def aclose(self):
        await self.stack.aclose()

class Agent:
    """The Week 5 Base Brain: Manages state, API calls, tool dispatching (Local & MCP), and plain-English skills."""
    def __init__(self, workspace=".", session_id=None, mcp_manager=None):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY")
        )
        self.model = "openrouter/free"
        self.workspace = workspace
        self.mcp_manager = mcp_manager # Store reference to our MCP server manager
        
        # Initialize or restore persistent session history
        self.session_id = session_id or create_session()
        session_data = load_session(self.session_id)
        
        if session_data and "messages" in session_data:
            self.messages = session_data["messages"]
        else:
            # Generate the default baseline system prompt
            system_prompt = build_system_prompt()
            
            # --- WEEK 4 AGENTS.md LOADING LOGIC ---
            agents_md_path = os.path.join(self.workspace, "AGENTS.md")
            if os.path.exists(agents_md_path):
                try:
                    with open(agents_md_path, "r", encoding="utf-8") as f:
                        agents_content = f.read()
                    system_prompt += f"\n\n### Project-Specific Instructions (AGENTS.md):\n{agents_content}"
                except Exception as e:
                    sys.stderr.write(f"[Warning] Failed to read AGENTS.md: {e}\n")

            # --- NEW WEEK 5 DYNAMIC SKILLS LOADING LOGIC ---
            skills = load_skills(os.path.join(self.workspace, "skills"))
            if skills:
                skills_summary = "\n".join([f"- {name}: {info['description']}" for name, info in skills.items()])
                skills_instructions = "\n\n".join([f"### Skill Instructions [{name}]:\n{info['instructions']}" for name, info in skills.items()])
                
                system_prompt += f"\n\n### Available Workflows & Skills:\n{skills_summary}\n\nIf the user requests a workflow matching one of these skills, execute its structural blueprint rules below sequentially:\n{skills_instructions}"

            self.messages = [{"role": "system", "content": system_prompt}]

    async def dispatch(self, tool_call) -> str:
        """Dual-router: Matches tool requests to either MCP servers or local python functions."""
        name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return json.dumps({"error": "Failed to parse arguments."})

        # 1. Route to MCP server first if it exists there
        if self.mcp_manager and name in self.mcp_manager.tool_to_session:
            try:
                # Call streaming tool natively using async await protocol standard
                result_str = await self.mcp_manager.call_tool(name, arguments)
                return result_str
            except Exception as e:
                return json.dumps({"error": f"MCP execution error on {name}: {str(e)}"})

        # 2. Otherwise fall back to local tools registry (Week 4 tools folder)
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

    async def _run_loop(self) -> str:
        """The core ReAct loop modified to run asynchronously with unified tools listing."""
        MAX_ITERATIONS = 20
        
        # Build master unified tool layout schema list
        combined_tools = list(TOOLS) if 'TOOLS' in globals() else []
        if self.mcp_manager:
            combined_tools.extend(self.mcp_manager.openai_tools)
        
        for _ in range(MAX_ITERATIONS):
            # Keep standard sync client completion call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=combined_tools if combined_tools else None
            )
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "tool_calls":
                self.messages.append(message)
                for tool_call in message.tool_calls:
                    self._emit("tool_start", name=tool_call.function.name)
                    
                    # Core modification: await the dynamic dual dispatch layout resolution
                    result_json = await self.dispatch(tool_call)
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_json
                    })
            
            elif finish_reason == "stop":
                todos = get_todos()
                unverified_tasks = []
                for task in todos:
                    if isinstance(task, dict):
                        status = task.get("status", "pending")
                        description = task.get("description", task.get("name", "Unknown Task"))
                    else:
                        status = "pending"
                        description = str(task)
                    
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

    async def chat(self, user_message: str) -> str:
        """Entry point for a conversation step. Commits state to disk."""
        self.messages.append({"role": "user", "content": user_message})
        final_answer = await self._run_loop()
        save_session(self.session_id, self.messages)
        return final_answer

    async def run_once(self, prompt: str) -> str:
        """Wrapper method for a single-shot execution."""
        return await self.chat(prompt)


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


async def main():
    # 1. Initialize and connect the MCP Manager
    mcp_manager = MCPManager()
    try:
        config = load_mcp_config("config.json")
        await mcp_manager.connect_all(config)
    except Exception as e:
        sys.stderr.write(f"[Warning] MCP Connection skipped or failed: {e}\n")
        mcp_manager = None

    # 2. Parse arguments and instantiate your agent
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        # Pass the active mcp_manager into your agent constructor
        agent = REPLAgent(mcp_manager=mcp_manager)
        
        # Await the asynchronous single-shot run
        result = await agent.run_once(prompt)
        print(result)
    else:
        agent = REPLAgent(mcp_manager=mcp_manager)
        
        # If your REPLAgent has an interactive .run() loop, 
        # ensure it is async-compatible, or call your async .chat() loop:
        if asyncio.iscoroutinefunction(agent.run):
            await agent.run()
        else:
            # Fallback standard async REPL loop right here
            print("🚀 Interactive Agent REPL Session Started. Type 'exit' to quit.")
            while True:
                try:
                    user_input = input("\nYou: ")
                    if user_input.lower() in ["exit", "quit"]:
                        break
                    response = await agent.chat(user_input)
                    print(f"\nAgent:\n{response}")
                except (KeyboardInterrupt, EOFError):
                    break

    # 3. Clean up network sessions cleanly on shutdown
    if mcp_manager:
        await mcp_manager.aclose()

if __name__ == "__main__":
    # Use asyncio.run to execute the top-level async main loop cleanly
    asyncio.run(main())