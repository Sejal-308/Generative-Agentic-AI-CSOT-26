import os
import requests
import trafilatura
import asyncio
import json
from mcp import ClientSession
from mcp.client.sse import sse_client
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, RichLog
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize Async client for non-blocking UI operations
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

MODEL = "deepseek/deepseek-v4-flash:free"
SERPER_API_KEY = os.environ["SERPER_API_KEY"]
MAX_HISTORY_TURNS = 20

LOCAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web for up-to-date information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search keywords."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "smart_fetch",
            "description": "Fetch the raw text content of a webpage URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The absolute URL to fetch."}
                },
                "required": ["url"]
            }
        }
    }
]

# --- Tool Implementations ---

def web_search(query: str, num_results: int = 5) -> str:
    """Search the web. Returns results as a formatted string."""
    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num_results},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("organic", []):
            results.append(f"Title: {item.get('title')}\nLink: {item.get('link')}\nSnippet: {item.get('snippet')}\n---")
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Error executing search: {str(e)}"

def web_fetch(url: str) -> str:
    """Fetch content of a URL."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
    response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
    response.raise_for_status()
    return trafilatura.extract(response.text, include_comments=False, include_tables=True) or ""

MAX_CHARS = 8000

def smart_fetch(url: str) -> str:
    from urllib.parse import urlparse
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    try:
        resp = requests.get(f"{base}/llms.txt", timeout=5)
        if resp.status_code == 200:
            return f"[llms.txt found]\n\n{resp.text}\n\n---\nOriginal URL: {url}"
    except Exception:
        pass
    
    content = web_fetch(url)
    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS] + "\n\n[...truncated]"
    return content

MCP_SERVER_URL = "https://mcp.alphaxiv.org/sse"   

def trim_history(messages: list[dict], max_turns: int) -> list[dict]:
    max_allowed_length = (max_turns * 2) + 1
    if len(messages) > max_allowed_length:
        system_prompt = [messages[0]]
        newest_messages = messages[-(max_turns * 2):] 
        return system_prompt + newest_messages
    return messages

# --- TUI Setup ---

class ChatApp(App):
    """A full-screen terminal chatbot with an active Agent Loop."""

    TITLE = "ResearchBot Agent TUI"
    CSS = """
    Screen { layout: vertical; }
    RichLog { height: 1fr; border: solid $primary; padding: 0 1; }
    Input { dock: bottom; height: 3; }
    """

    BINDINGS = [
        Binding("ctrl+l", "clear_display", "Clear display"),
        Binding("ctrl+k", "clear_history", "Clear history"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+b", "toggle_dark", "Toggle Dark Mode")  # Extra shortcut choice
    ]

    def __init__(self):
        super().__init__()
        self.messages: list[dict] = [
            {"role": "system", "content": "You are an advanced research assistant with web search and academic tool access."}
        ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="log", wrap=True, markup=True, highlight=True)
        yield Input(placeholder="Ask ResearchBot anything...")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[bold green]ResearchBot Active.[/bold green] Ctrl+Q to quit, Ctrl+L to clear layout.\n")
        self.query_one(Input).focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        event.input.clear()
        log = self.query_one("#log", RichLog)
        log.write(f"[bold cyan][You][/bold cyan]: {user_text}\n")
        
        self.messages.append({"role": "user", "content": user_text})
        self.messages = trim_history(self.messages, MAX_HISTORY_TURNS)
        
        # Run worker *without* thread=True because the entire internal process is native async
        self.run_worker(self._get_response())

    async def _get_response(self) -> None:
        log = self.query_one("#log", RichLog)
        
        try:
            # Step 1: Keep the MCP Context open for the duration of the entire Agent Loop
            async with sse_client(MCP_SERVER_URL) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Fetch and convert MCP tools
                    mcp_tools = await session.list_tools()
                    openai_tools = []
                    for tool in mcp_tools.tools:
                        openai_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema,
                            },
                        })
                    
                    # Combine local and server tools
                    all_tools = openai_tools + LOCAL_TOOLS

                    # Step 2: Begin the Agent Execution Loop
                    while True:
                        response = await client.chat.completions.create(
                            model=MODEL,
                            messages=self.messages,
                            tools=all_tools
                        )
                        
                        response_message = response.choices[0].message
                        
                        # Handle standard textual answer
                        if not response_message.tool_calls:
                            final_text = response_message.content or ""
                            self.messages.append({"role": "assistant", "content": final_text})
                            log.write(f"[bold blue]Agent[/bold blue]: {final_text}\n")
                            break
                        
                        # Step 3: Handle active tool requests
                        # Convert assistant message object to dict for history retention requirements
                        tool_call_msg = {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                                } for tc in response_message.tool_calls
                            ]
                        }
                        if response_message.content:
                            tool_call_msg["content"] = response_message.content
                            
                        self.messages.append(tool_call_msg)
                        
                        for tool_call in response_message.tool_calls:
                            name = tool_call.function.name
                            args = json.loads(tool_call.function.arguments)
                            
                            log.write(f"[dim yellow][Tool Action][/dim yellow]: Using '{name}'...")
                            
                            # Route to local tools
                            if name == "web_search":
                                result_str = web_search(args.get("query", ""))
                            elif name == "smart_fetch":
                                result_str = smart_fetch(args.get("url", ""))
                            # Route to external MCP Server tools
                            else:
                                try:
                                    mcp_result = await session.call_tool(name, args)
                                    # Extracted content text format handling from MCP response text schema
                                    result_str = "".join([content.text for content in mcp_result.content if hasattr(content, 'text')])
                                except Exception as mcp_err:
                                    result_str = f"MCP tool execution failed: {str(mcp_err)}"
                            
                            # Append completion results back to history context
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": name,
                                "content": result_str
                            })
                            
        except Exception as error:
            log.write(f"[bold red]System Error:[/bold red] {str(error)}\n")

    def action_clear_display(self) -> None:
        self.query_one("#log", RichLog).clear()

    def action_clear_history(self) -> None:
        self.messages = [{"role": "system", "content": "You are an advanced research assistant with web search and academic tool access."}]
        self.query_one("#log", RichLog).clear()
        self.query_one("#log", RichLog).write("[dim]History wiped clean.[/dim]\n")


if __name__ == "__main__":
   
    ChatApp().run()