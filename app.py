import asyncio
import json
import os
from typing import List, Dict, Tuple, Optional
import httpx

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Header, Footer, Input, Select, Button, Label, Checkbox, DataTable, ProgressBar, Static
from textual.binding import Binding
from textual.message import Message

from checker import APIKeyChecker, detect_provider, PROVIDER_MODELS

HISTORY_FILE = "keys_history.json"

def get_clipboard_text() -> str:
    """Reads text from Windows or fallback system clipboard."""
    try:
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        CF_UNICODETEXT = 13
        
        if user32.OpenClipboard(None):
            try:
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if handle:
                    ptr = kernel32.GlobalLock(handle)
                    if ptr:
                        try:
                            text = ctypes.wstring_at(ptr)
                            return text
                        finally:
                            kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
    except Exception:
        pass

    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        return text
    except Exception:
        pass

    return ""

def load_keys_history() -> List[Dict[str, str]]:
    """Loads keys from local JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_key_to_history(provider: str, key: str):
    """Saves a key to the history file if it does not already exist."""
    history = load_keys_history()
    
    # Check if duplicate
    for entry in history:
        if entry.get("key") == key:
            return
            
    # Mask key for alias
    alias = mask_key(provider, key)
    
    history.append({
        "provider": provider,
        "key": key,
        "alias": alias
    })
    
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass

def mask_key(provider: str, key: str) -> str:
    """Masks a key for safe UI display."""
    if key.startswith("mock-"):
        return f"{provider} (Mock Key)"
    if len(key) <= 10:
        return f"{provider} ({key}...)"
    return f"{provider} ({key[:8]}...{key[-4:]})"


class ModelCheckApp(App):
    TITLE = "★ WHAT MODEL DOES MY API KEY SUPPORT ★"
    CSS = """
    Screen {
        background: #0f141c;
        color: #e2e8f0;
    }

    Header {
        background: #1a2333;
        color: #58a6ff;
        text-align: center;
        height: 3;
        border-bottom: double #30363d;
        content-align: center middle;
        text-style: bold reverse;
    }

    Footer {
        background: #131924;
        color: #8b949e;
    }

    .main-grid {
        grid-size: 2;
        grid-columns: 1fr 2fr;
        padding: 1 1;
        grid-gutter: 1 2;
    }

    .control-panel {
        background: #161b22;
        border: round #30363d;
        padding: 1 2;
        height: 100%;
    }

    .display-panel {
        background: #161b22;
        border: round #30363d;
        padding: 1 2;
        height: 100%;
    }

    .panel-title {
        text-style: bold;
        color: #58a6ff;
        margin-bottom: 1;
        border-bottom: solid #30363d;
        padding-bottom: 1;
    }

    Label {
        color: #8b949e;
        margin-top: 1;
        text-style: bold;
    }

    Input {
        background: #0d1117;
        color: #c9d1d9;
        border: solid #30363d;
        margin-bottom: 1;
    }
    Input:focus {
        border: double #58a6ff;
    }

    Select {
        background: #0d1117;
        color: #c9d1d9;
        border: solid #30363d;
        margin-bottom: 1;
    }
    Select:focus {
        border: double #58a6ff;
    }

    Checkbox {
        margin-top: 1;
        margin-bottom: 1;
        color: #c9d1d9;
    }

    Button {
        background: #21262d;
        color: #58a6ff;
        border: solid #30363d;
        margin-top: 1;
        text-style: bold;
        width: 100%;
    }
    Button:hover {
        background: #30363d;
    }
    #btn-test {
        background: #238636;
        color: #ffffff;
        border: solid #2ea043;
    }
    #btn-test:hover {
        background: #2ea043;
    }

    .status-badge {
        background: #21262d;
        border: round #30363d;
        padding: 1 2;
        margin-bottom: 1;
    }

    .progress-bar-container {
        margin-top: 1;
        margin-bottom: 1;
    }

    DataTable {
        background: #0d1117;
        border: solid #30363d;
        height: 100%;
        margin-top: 1;
    }

    .warning-text {
        color: #f0883e;
        text-style: bold;
    }

    .error-text {
        color: #f85149;
        text-style: bold;
    }

    .success-text {
        color: #56d364;
        text-style: bold;
    }

    .info-text {
        color: #79c0ff;
        text-style: bold;
    }

    #key-input-container {
        height: auto;
        margin-bottom: 1;
    }

    #key-input {
        width: 4fr;
        margin-bottom: 0;
    }

    #btn-clipboard-paste {
        width: 1fr;
        margin-top: 0;
        background: #21262d;
        color: #58a6ff;
        border: solid #30363d;
        height: 3;
        text-style: bold;
    }
    #btn-clipboard-paste:hover {
        background: #30363d;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+t", "test_key", "Test Key", show=True),
        Binding("ctrl+r", "reset", "Reset UI", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.saved_keys: List[Dict[str, str]] = []
        self.testing_in_progress = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Grid(classes="main-grid"):
            # Left Panel: Controls
            with Vertical(classes="control-panel"):
                yield Label("⚙️ MAIN CONTROLS", classes="panel-title")
                
                yield Label("Saved Key History")
                self.history_select = Select(
                    options=[],
                    prompt="Select a saved key...",
                    id="history-select"
                )
                yield self.history_select
                
                yield Label("API Key")
                with Horizontal(id="key-input-container"):
                    self.key_input = Input(
                        placeholder="Paste your API key here (Press Enter to Test)",
                        id="key-input"
                    )
                    yield self.key_input
                    yield Button("Paste", id="btn-clipboard-paste")
                
                with Horizontal():
                    self.mask_toggle = Checkbox("Hide Key characters", value=False, id="mask-toggle")
                    yield self.mask_toggle
                    self.save_toggle = Checkbox("Save Key to History", value=True, id="save-toggle")
                    yield self.save_toggle
                
                yield Label("Provider Selection")
                self.provider_select = Select(
                    options=[
                        ("Auto-Detect", "Auto-Detect"),
                        ("Gemini", "Gemini"),
                        ("OpenAI", "OpenAI"),
                        ("Anthropic", "Anthropic"),
                        ("OpenRouter", "OpenRouter"),
                        ("Groq", "Groq"),
                        ("DeepSeek", "DeepSeek")
                    ],
                    value="Auto-Detect",
                    id="provider-select"
                )
                yield self.provider_select

                yield Button("Test API Key", id="btn-test")
                yield Button("Clear / Reset", id="btn-clear")
                
            # Right Panel: Display and Results
            with Vertical(classes="display-panel"):
                yield Label("📊 DIAGNOSTICS & RESULTS", classes="panel-title")
                
                # Dynamic Info Panel
                with Vertical(classes="status-badge", id="info-panel"):
                    yield Label("Provider: Not Checked", id="lbl-detected-provider")
                    yield Label("Key Status: Waiting for input", id="lbl-key-status")
                    yield Label("Active Models: 0", id="lbl-active-models-count")
                
                # Progress Bar
                with Vertical(classes="progress-bar-container", id="progress-container"):
                    self.progress_label = Label("Testing progress: Idle")
                    yield self.progress_label
                    self.progress_bar = ProgressBar(total=100, show_eta=False, show_percentage=True, id="progress-bar")
                    yield self.progress_bar
                    
                # Results Table
                self.results_table = DataTable(id="results-table")
                yield self.results_table

        yield Footer()

    def on_mount(self) -> None:
        """Initialize UI elements after loading screen."""
        self.results_table.add_columns("Model Name", "Status", "Code", "Latency (ms)", "Details / API Error Messages")
        self.results_table.zebra_stripes = True
        self.refresh_history()

    def refresh_history(self) -> None:
        """Loads keys from file and updates history select dropdown."""
        self.saved_keys = load_keys_history()
        options = [(entry["alias"], entry["key"]) for entry in self.saved_keys]
        self.history_select.set_options(options)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handles password masking toggle."""
        if event.checkbox.id == "mask-toggle":
            self.key_input.password = event.checkbox.value

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handles selecting a key from history."""
        if event.select.id == "history-select" and event.value is not None:
            # Set the full key value into input
            self.key_input.value = event.value
            # Pre-detect the provider for the user
            detected, status_msg = detect_provider(event.value)
            if detected != "Unknown" and detected != "Unsupported":
                self.provider_select.value = detected
            else:
                self.provider_select.value = "Auto-Detect"

    def on_input_changed(self, event: Input.Changed) -> None:
        """Performs auto-detection on-the-fly as user types/pastes."""
        if event.input.id == "key-input" and not self.testing_in_progress:
            val = event.value.strip()
            if val:
                detected, status_msg = detect_provider(val)
                lbl_prov = self.query_one("#lbl-detected-provider", Label)
                lbl_status = self.query_one("#lbl-key-status", Label)
                
                if detected != "Unknown":
                    lbl_prov.update(f"Provider (Detected): [bold]{detected}[/bold]")
                    lbl_status.update(f"Format Info: [cyan]{status_msg}[/cyan]")
                    if detected in PROVIDER_MODELS:
                        self.provider_select.value = detected
                else:
                    lbl_prov.update("Provider: Unknown (Please select manually)")
                    lbl_status.update("[yellow]Cannot identify format automatically.[/yellow]")
            else:
                self.query_one("#lbl-detected-provider", Label).update("Provider: Not Checked")
                self.query_one("#lbl-key-status", Label).update("Key Status: Waiting for input")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Runs testing when Enter is pressed in Key Input."""
        if event.input.id == "key-input":
            await self.action_test_key()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handles buttons."""
        if event.button.id == "btn-test":
            await self.action_test_key()
        elif event.button.id == "btn-clear":
            self.action_reset()
        elif event.button.id == "btn-clipboard-paste":
            text = get_clipboard_text()
            if text:
                self.key_input.value = text.strip()
                self.notify("Key pasted from clipboard!", severity="info", timeout=2)
            else:
                self.notify("Clipboard is empty or inaccessible.", severity="warning", timeout=2)

    # --- Actions ---
    def action_reset(self) -> None:
        """Resets the UI states."""
        if self.testing_in_progress:
            return
        self.key_input.value = ""
        self.provider_select.value = "Auto-Detect"
        self.history_select.value = None
        self.query_one("#lbl-detected-provider", Label).update("Provider: Not Checked")
        self.query_one("#lbl-key-status", Label).update("Key Status: Waiting for input")
        self.query_one("#lbl-active-models-count", Label).update("Active Models: 0")
        self.progress_label.update("Testing progress: Idle")
        self.progress_bar.progress = 0
        self.results_table.clear()

    async def action_test_key(self) -> None:
        """Validates and tests the API key against all models."""
        if self.testing_in_progress:
            return
            
        key_val = self.key_input.value.strip()
        if not key_val:
            self.query_one("#lbl-key-status", Label).update("[red]Error: API Key input is empty![/red]")
            return

        self.testing_in_progress = True
        self.results_table.clear()
        
        # Determine provider
        provider = self.provider_select.value
        if provider == "Auto-Detect":
            detected, status_msg = detect_provider(key_val)
            if detected in ["Unknown", "Unsupported"]:
                self.query_one("#lbl-key-status", Label).update("[red]Could not auto-detect provider. Please choose a provider manually.[/red]")
                self.testing_in_progress = False
                return
            provider = detected

        self.query_one("#lbl-detected-provider", Label).update(f"Testing Provider: [bold]{provider}[/bold]")
        self.query_one("#lbl-key-status", Label).update("Pre-validating key...")
        
        checker = APIKeyChecker(provider, key_val)
        
        # 1. Early Validation Check
        is_valid, validation_msg = await checker.check_key_validity_early()
        if not is_valid:
            self.query_one("#lbl-key-status", Label).update(f"[red]Failed Pre-validation: {validation_msg}[/red]")
            self.testing_in_progress = False
            return
            
        self.query_one("#lbl-key-status", Label).update(f"[green]Key Validated. Loading models...[/green]")
        
        # Save key to history if checked and valid
        if self.save_toggle.value and not key_val.startswith("mock-"):
            save_key_to_history(provider, key_val)
            self.refresh_history()
            
        # 2. Get Models to test
        models = await checker.get_available_models()
        if not models:
            self.query_one("#lbl-key-status", Label).update("[red]No models found to test for this provider.[/red]")
            self.testing_in_progress = False
            return
            
        self.progress_bar.total = len(models)
        self.progress_bar.progress = 0
        self.progress_label.update(f"Testing 0/{len(models)} models...")

        active_count = 0
        
        # 3. Test models concurrently in small batches (to prevent hitting limits just from checks)
        batch_size = 3
        sem = asyncio.Semaphore(batch_size)
        
        async def sem_check(mod, client):
            async with sem:
                return await checker.check_single_model(mod, client)
                
        # We use a single httpx AsyncClient for connection reuse
        async with httpx.AsyncClient(timeout=12.0) as client:
            tasks = [sem_check(model, client) for model in models]
            
            # Run concurrently and update TUI as each finishes
            for future in asyncio.as_completed(tasks):
                result = await future
                
                # Check status styling
                status_style = "white"
                if result.status == "Active":
                    status_style = "[green]Active[/green]"
                    active_count += 1
                elif result.status == "Quota Exhausted":
                    status_style = "[orange3]Quota Exhausted[/orange3]"
                elif "Restricted" in result.status:
                    status_style = "[yellow]Restricted (Free)[/yellow]"
                elif "Unsupported" in result.status:
                    status_style = "[bright_black]Unsupported[/bright_black]"
                else:
                    status_style = "[red]Error[/red]"

                code_str = str(result.status_code) if result.status_code else "N/A"
                latency_str = f"{result.latency_ms:.1f}" if result.latency_ms > 0 else "N/A"
                
                # Add row to table
                self.results_table.add_row(
                    result.model_name,
                    status_style,
                    code_str,
                    latency_str,
                    result.error_message
                )
                
                # Update progress bar
                self.progress_bar.progress += 1
                curr = int(self.progress_bar.progress)
                self.progress_label.update(f"Testing {curr}/{len(models)} models ({result.model_name})...")
                self.query_one("#lbl-active-models-count", Label).update(f"Active Models: {active_count}")

        self.progress_label.update(f"[green]Completed testing all {len(models)} models![/green]")
        self.query_one("#lbl-key-status", Label).update(f"[green]Verification Finished. {active_count} active models.[/green]")
        self.testing_in_progress = False


if __name__ == "__main__":
    app = ModelCheckApp()
    app.run()
