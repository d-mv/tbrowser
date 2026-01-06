from textual.app import App, ComposeResult, on
from textual.widgets import Header, Footer, Input, Markdown, LoadingIndicator
from src.ui.content_view import BrowserContent
from src.engine import fetch_and_parse

class TBrowser(App):
    """A simple Terminal-based Browser."""
    
    CSS = """
    Input {
        dock: top;
        margin: 1 0;
        border: solid gray;
    }
    Input:focus {
        border: double white;
    }
    #content_view {
        padding: 1 2;
    }
    .browser-image {
        width: 100%;
        content-align: center middle;
        margin: 1 0;
    }
    .image-placeholder {
        color: gray;
        text-align: center;
        padding: 1;
        border: dashed gray;
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("b", "go_back", "Back"),
        ("f", "go_forward", "Forward"),
        ("u", "focus_url", "Focus URL"),
        ("r", "toggle_readability", "Toggle Reader Mode"),
        ("i", "toggle_images", "Toggle Images"),
    ]

    history: list[str] = []
    history_index: int = -1
    is_readability_on: bool = False
    show_images: bool = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Input(placeholder="Enter URL (e.g. google.com)", id="address_bar")
        
        # New Custom Widget
        yield BrowserContent(id="content_view")
        
        yield Footer()

    async def on_mount(self):
        # Initial Welcome Message
        view = self.query_one("#content_view", BrowserContent)
        await view.load_segments([
            {"type": "text", "content": "# Welcome to tbrowser!\n\nType a URL to start."}  # Corrected newline escape
        ])

    async def perform_navigation(self, url: str) -> None:
        """Shared logic for navigating to a new URL (modifies history)."""
        if not url:
            return

        # 1. Truncate forward history
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
        
        # 2. Add to history
        self.history.append(url)
        self.history_index += 1
        
        # 3. Load
        await self.load_url(url)

    async def load_url(self, url: str) -> None:
        """Helper to fetch and render a URL."""
        content_view = self.query_one("#content_view", BrowserContent)
        address_bar = self.query_one("#address_bar", Input)
        
        # Update UI
        address_bar.value = url
        self.title = f"tbrowser - {url}"
        
        # Show Loading Indicator
        # We manually clear and mount indicator
        await content_view.remove_children()
        await content_view.mount(LoadingIndicator())
        
        # Fetch Segments
        # Passing self.show_images to fetch_and_parse would be ideal if we wanted to save bandwidth
        # but current engine design fetches everything.
        segments = await fetch_and_parse(url, readability_mode=self.is_readability_on)
        
        # Render (this will clear the loading indicator)
        await content_view.load_segments(segments, show_images=self.show_images)

    @on(Input.Submitted, "#address_bar")
    async def navigate(self, event: Input.Submitted) -> None:
        await self.perform_navigation(event.value)

    @on(Markdown.LinkClicked)
    async def handle_link_click(self, event: Markdown.LinkClicked) -> None:
        url = event.href
        if not url.startswith(("http://", "https://")):
             self.notify(f"Link type not supported: {url}", severity="warning")
             return
        await self.perform_navigation(url)

    def action_focus_url(self) -> None:
        self.query_one("#address_bar").focus()

    def action_toggle_readability(self) -> None:
        self.is_readability_on = not self.is_readability_on
        state = "ON" if self.is_readability_on else "OFF"
        self.notify(f"Reader Mode {state}")
        if self.history_index >= 0:
            url = self.history[self.history_index]
            self.run_worker(self.load_url(url))

    def action_toggle_images(self) -> None:
        self.show_images = not self.show_images
        state = "ON" if self.show_images else "OFF"
        self.notify(f"Images {state}")
        if self.history_index >= 0:
            url = self.history[self.history_index]
            self.run_worker(self.load_url(url))

    async def action_go_back(self) -> None:
        if self.history_index > 0:
            self.history_index -= 1
            url = self.history[self.history_index]
            await self.load_url(url)
        else:
            self.notify("No history.", severity="warning")

    async def action_go_forward(self) -> None:
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            url = self.history[self.history_index]
            await self.load_url(url)
        else:
            self.notify("No history.", severity="warning")

if __name__ == "__main__":
    app = TBrowser()
    app.run()