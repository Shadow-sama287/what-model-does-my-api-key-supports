import asyncio
import json
import os
import time
from typing import List, Dict, Tuple, Optional, Any
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
        
        CF_TEXT = 1
        CF_UNICODETEXT = 13
        
        if user32.OpenClipboard(None):
            try:
                # Try Unicode text first
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if handle:
                    ptr = kernel32.GlobalLock(handle)
                    if ptr:
                        try:
                            return ctypes.wstring_at(ptr)
                        finally:
                            kernel32.GlobalUnlock(handle)
                
                # Try standard ASCII text fallback
                handle = user32.GetClipboardData(CF_TEXT)
                if handle:
                    ptr = kernel32.GlobalLock(handle)
                    if ptr:
                        try:
                            return ctypes.string_at(ptr).decode("ansi", errors="ignore")
                        finally:
                            kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
    except Exception:
        pass

    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            creationflags=0x08000000 # CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return ""

def set_clipboard_text(text: str) -> bool:
    """Writes text to Windows or fallback system clipboard."""
    try:
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        
        text_utf16 = text.encode("utf-16le") + b"\x00\x00"
        
        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_utf16))
                if h_mem:
                    ptr = kernel32.GlobalLock(h_mem)
                    if ptr:
                        try:
                            ctypes.memmove(ptr, text_utf16, len(text_utf16))
                        finally:
                            kernel32.GlobalUnlock(h_mem)
                        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                        return True
            finally:
                user32.CloseClipboard()
    except Exception:
        pass

    try:
        import subprocess
        p = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard"],
            stdin=subprocess.PIPE,
            text=True,
            creationflags=0x08000000 # CREATE_NO_WINDOW
        )
        p.communicate(input=text)
        if p.returncode == 0:
            return True
    except Exception:
        pass

    return False

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
    TITLE = "=== WHAT MODEL DOES MY API KEY SUPPORT ==="
    show_command_palette = False
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
        text-style: bold;
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
        padding: 0 2;
        height: 100%;
        overflow: hidden;
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

    #info-panel {
        height: auto;
        margin-bottom: 1;
        background: #161b22;
        border: none;
        padding: 0;
    }

    .info-row {
        height: 1;
        margin-bottom: 0;
    }

    .info-row Label {
        width: 1fr;
    }

    #progress-container {
        height: 1;
        margin-top: 0;
        margin-bottom: 0;
    }

    #progress-container Label {
        width: 35;
        text-style: bold;
    }

    #progress-bar {
        width: 1fr;
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

    #lbl-execution-status {
        text-style: bold;
        color: #8b949e;
        margin-bottom: 1;
    }

    #results-table {
        height: 1fr;
        margin-top: 0;
        margin-bottom: 0;
    }

    #details-viewer-container {
        height: 9;
        background: #0d1117;
        border: round #30363d;
        padding: 0 1;
        margin-bottom: 0;
    }

    #details-viewer-title {
        text-style: bold;
        color: #58a6ff;
        margin-bottom: 0;
        border-bottom: solid #30363d;
        padding-bottom: 0;
    }

    #details-viewer {
        color: #c9d1d9;
        overflow: auto scroll;
        height: 5;
    }

    #action-buttons-container {
        height: auto;
        margin-top: 1;
        margin-bottom: 0;
    }

    #btn-copy-active {
        width: 1fr;
        background: #21262d;
        color: #58a6ff;
        border: solid #30363d;
        height: 3;
        margin: 0 1 0 0;
        text-style: bold;
    }
    #btn-copy-active:hover {
        background: #30363d;
    }

    #btn-export-markdown {
        width: 1fr;
        background: #21262d;
        color: #58a6ff;
        border: solid #30363d;
        height: 3;
        margin: 0;
        text-style: bold;
    }
    #btn-export-markdown:hover {
        background: #30363d;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+t", "test_key", "Test Key", show=True),
        Binding("ctrl+r", "reset", "Reset UI", show=True),
        Binding("ctrl+c", "copy_active", "Copy Active", show=True),
        Binding("ctrl+e", "export_markdown", "Export MD", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.saved_keys: List[Dict[str, str]] = []
        self.testing_in_progress = False
        self.check_results: Dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Grid(classes="main-grid"):
            # Left Panel: Controls
            with Vertical(classes="control-panel"):
                yield Label("[ MAIN CONTROLS ]", classes="panel-title")
                
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
                yield Label("[ DIAGNOSTICS & RESULTS ]", classes="panel-title")
                
                # Results Table
                self.results_table = DataTable(id="results-table")
                yield self.results_table

                # Progress Bar
                with Horizontal(id="progress-container"):
                    self.progress_label = Label("Testing progress: Idle")
                    yield self.progress_label
                    self.progress_bar = ProgressBar(total=100, show_eta=False, show_percentage=True, id="progress-bar")
                    yield self.progress_bar

                # Dynamic Info Panel
                with Vertical(id="info-panel"):
                    with Horizontal(classes="info-row"):
                        self.status_indicator = Label("STATUS: [bold #8b949e]IDLE[/bold #8b949e]", id="lbl-execution-status")
                        yield self.status_indicator
                        yield Label("Active Models: 0", id="lbl-active-models-count")
                    with Horizontal(classes="info-row"):
                        yield Label("Provider: Not Checked", id="lbl-detected-provider")
                        yield Label("Key Status: Waiting for input", id="lbl-key-status")
                
                # Details Panel
                with Vertical(id="details-viewer-container"):
                    yield Label("[ SELECTED MODEL ERROR/DETAILS ]", id="details-viewer-title")
                    self.details_viewer = Static("Highlight or select a model row above to view full details.", id="details-viewer")
                    yield self.details_viewer

                # Copy/Export Buttons
                with Horizontal(id="action-buttons-container"):
                    yield Button("Copy Active List", id="btn-copy-active")
                    yield Button("Export Report", id="btn-export-markdown")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize UI elements after loading screen."""
        self.results_table.add_columns("Model Name", "Status", "Code", "Latency (ms)", "Details / API Error Messages")
        self.results_table.zebra_stripes = True
        self.results_table.cursor_type = "row"
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
        if event.select.id == "history-select" and isinstance(event.value, str):
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
        elif event.button.id == "btn-copy-active":
            self.action_copy_active()
        elif event.button.id == "btn-export-markdown":
            self.action_export_markdown()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Dynamically displays details of the currently highlighted row."""
        self.update_details_from_row(event.row_key)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handles row selection/click."""
        self.update_details_from_row(event.row_key)

    def update_details_from_row(self, row_key) -> None:
        try:
            if hasattr(row_key, "value"):
                model_name = str(row_key.value)
            else:
                model_name = str(row_key)
                
            if model_name in self.check_results:
                res = self.check_results[model_name]
                status_text = res.status
                code_str = str(res.status_code) if res.status_code else "N/A"
                latency_str = f"{res.latency_ms:.1f} ms" if res.latency_ms > 0 else "N/A"
                error_msg = res.error_message or "No error details available."
                
                details_content = (
                    f"[bold cyan]Model:[/bold cyan] {res.model_name}\n"
                    f"[bold cyan]Status:[/bold cyan] {status_text} (Code: {code_str})\n"
                    f"[bold cyan]Latency:[/bold cyan] {latency_str}\n"
                    f"[bold cyan]Full API Message/Details:[/bold cyan]\n"
                    f"{error_msg}"
                )
                self.details_viewer.update(details_content)
        except Exception as e:
            self.details_viewer.update(f"Error loading row details: {str(e)}")

    # --- Actions ---
    def action_copy_active(self) -> None:
        """Action handler to copy active models."""
        active_models = [m.model_name for m in self.check_results.values() if m.status == "Active"]
        if not active_models:
            self.notify("No active models to copy.", severity="warning", timeout=2)
            return
        
        bullet_list = "\n".join(f"- {name}" for name in active_models)
        clipboard_content = f"My API key supports the following active models:\n{bullet_list}"
        
        if set_clipboard_text(clipboard_content):
            self.notify(f"Copied {len(active_models)} active models to clipboard!", severity="info", timeout=2)
        else:
            self.notify("Failed to copy to clipboard.", severity="error", timeout=2)

    def action_export_markdown(self) -> None:
        """Action handler to export report to markdown."""
        if not self.check_results:
            self.notify("No results to export. Run a test first.", severity="warning", timeout=2)
            return
        
        try:
            markdown_lines = [
                "# API Key Support Report",
                "",
                f"- **Provider**: {self.provider_select.value}",
                f"- **Tested At**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "| Model Name | Status | Status Code | Latency | Details / API Error |",
                "|---|---|---|---|---|",
            ]
            for res in self.check_results.values():
                code_str = str(res.status_code) if res.status_code else "N/A"
                latency_str = f"{res.latency_ms:.1f}ms" if res.latency_ms > 0 else "N/A"
                err_cleaned = (res.error_message or "Successfully responded").replace("|", "\\|").replace("\n", " ")
                markdown_lines.append(
                    f"| {res.model_name} | {res.status} | {code_str} | {latency_str} | {err_cleaned} |"
                )
            
            report_content = "\n".join(markdown_lines)
            
            with open("wmd_results.md", "w") as f:
                f.write(report_content)
            
            self.notify("Results exported to wmd_results.md!", severity="info", timeout=3)
        except Exception as e:
            self.notify(f"Export failed: {str(e)}", severity="error", timeout=3)

    def action_reset(self) -> None:
        """Resets the UI states."""
        if self.testing_in_progress:
            return
        self.key_input.value = ""
        self.provider_select.value = "Auto-Detect"
        self.history_select.clear()
        self.query_one("#lbl-detected-provider", Label).update("Provider: Not Checked")
        self.query_one("#lbl-key-status", Label).update("Key Status: Waiting for input")
        self.query_one("#lbl-active-models-count", Label).update("Active Models: 0")
        self.status_indicator.update("STATUS: [bold #8b949e]IDLE[/bold #8b949e]")
        self.progress_label.update("Testing progress: Idle")
        self.progress_bar.progress = 0
        self.results_table.clear()
        self.check_results = {}
        self.details_viewer.update("Highlight or select a model row above to view full details.")

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
        self.check_results = {}
        self.details_viewer.update("Testing models...")
        
        # Set status to TESTING
        self.status_indicator.update("STATUS: [bold #f0883e]TESTING...[/bold #f0883e]")
        
        # Determine provider
        provider = self.provider_select.value
        if provider == "Auto-Detect":
            detected, status_msg = detect_provider(key_val)
            if detected in ["Unknown", "Unsupported"]:
                self.query_one("#lbl-key-status", Label).update("[red]Could not auto-detect provider. Please choose a provider manually.[/red]")
                self.status_indicator.update("STATUS: [bold #56d364]COMPLETE[/bold #56d364]")
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
            self.status_indicator.update("STATUS: [bold #56d364]COMPLETE[/bold #56d364]")
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
            self.status_indicator.update("STATUS: [bold #56d364]COMPLETE[/bold #56d364]")
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
                
                # Store full result
                self.check_results[result.model_name] = result
                
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
                
                # Truncate detail message for clean table layout
                short_err = result.error_message or "Successfully responded"
                if len(short_err) > 35:
                    short_err = short_err[:32] + "..."
                
                # Add row to table (with specific key matching the model name)
                self.results_table.add_row(
                    result.model_name,
                    status_style,
                    code_str,
                    latency_str,
                    short_err,
                    key=result.model_name
                )
                
                # Update progress bar
                self.progress_bar.progress += 1
                curr = int(self.progress_bar.progress)
                self.progress_label.update(f"Testing {curr}/{len(models)} models ({result.model_name})...")
                self.query_one("#lbl-active-models-count", Label).update(f"Active Models: {active_count}")

        self.progress_label.update(f"[green]Completed testing all {len(models)} models![/green]")
        self.query_one("#lbl-key-status", Label).update(f"[green]Verification Finished. {active_count} active models.[/green]")
        
        # Set status to COMPLETE
        self.status_indicator.update("STATUS: [bold #56d364]COMPLETE[/bold #56d364]")
        
        self.testing_in_progress = False
        
        # Select first row by default to trigger details update
        if models:
            try:
                self.results_table.move_cursor(row=0)
                self.update_details_from_row(models[0])
            except Exception:
                pass


if __name__ == "__main__":
    app = ModelCheckApp()
    app.run()
