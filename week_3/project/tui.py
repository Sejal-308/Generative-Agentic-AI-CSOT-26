"""
TUIAgent — full-screen Textual UI inheriting from Agent.
"""

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Input, RichLog
from textual.binding import Binding
from textual import work


from agent import Agent

class ResearchDeskApp(App):
    """The Textual User Interface for the Research Desk."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    #main_container {
        height: 1fr;
    }
    #chat_log {
        width: 2fr;
        height: 1fr;
        border: solid green;
    }
    #tool_log {
        width: 1fr;
        height: 1fr;
        border: solid yellow;
        display: none;
    }
    #tool_log.show {
        display: block;
    }
    Input {
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "focus_input", "Focus Input"),
        Binding("ctrl+k", "toggle_tools", "Toggle Tool Log"),
    ]

    def __init__(self, agent: "TUIAgent"):
        super().__init__()
        self.agent = agent

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main_container"):
            yield RichLog(id="chat_log", highlight=True, markup=True)
            yield RichLog(id="tool_log", highlight=True, markup=True)
        yield Input(placeholder="Ask your research assistant...", id="user_input")
        yield Footer()

    def on_mount(self) -> None:
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.write(f"[bold green]Research Desk Initialized[/] (Session: {self.agent.session_id})")
        chat_log.write("Type a query to begin...")
        self.query_one("#user_input", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        
        input_widget = self.query_one("#user_input", Input)
        input_widget.value = ""
        input_widget.disabled = True

        
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.write(f"\n[bold blue]You:[/] {user_text}")

        
        self.run_chat_worker(user_text)

    @work(thread=True)
    def run_chat_worker(self, user_text: str) -> None:
        """Runs the AI logic in the background so the UI doesn't freeze."""
        
        response = self.agent.chat(user_text)
        
        
        self.call_from_thread(self.update_chat_log, response)

    def update_chat_log(self, response: str) -> None:
        """Runs on the main thread to update the UI with the AI's final answer."""
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.write(f"\n[bold purple]Agent:[/] {response}")
        
        input_widget = self.query_one("#user_input", Input)
        input_widget.disabled = False
        input_widget.focus()

    def log_tool(self, tool_name: str) -> None:
        """Writes to the hidden tool log panel."""
        tool_log = self.query_one("#tool_log", RichLog)
        tool_log.write(f"🔧 [yellow]Calling tool:[/] {tool_name}")

    def action_focus_input(self) -> None:
        self.query_one("#user_input", Input).focus()

    def action_toggle_tools(self) -> None:
        tool_log = self.query_one("#tool_log", RichLog)
        if tool_log.has_class("show"):
            tool_log.remove_class("show")
        else:
            tool_log.add_class("show")


class TUIAgent(Agent):
    """
    Inherits the Brain (Agent), but adds a 'mouth' so it can talk to the Textual UI.
    """
    def __init__(self, session_id: str | None = None):
        super().__init__(session_id=session_id)
        self.app = None

    def _emit(self, event: str, **data) -> None:
        """Overrides the silent 'pass' from the base Agent."""
        if event == "tool_call" and self.app:
            
            self.app.call_from_thread(self.app.log_tool, data.get("name"))

    def run(self):
        """Launches the Textual UI and passes itself (the brain) to it."""
        self.app = ResearchDeskApp(agent=self)
        self.app.run()