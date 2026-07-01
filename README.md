# What model does my API key support (wmd-my-API-ks)

An interactive, premium Terminal User Interface (TUI) application built in Python using **Textual** to check exactly which LLM models your API keys support, distinguish between free-tier restrictions and true quota exhaustion, and keep a secure history of your keys.

Designed specifically for beginners and developers to quickly resolve "wrong model" errors and identify plan limitations before integrating keys into applications.

For a complete breakdown of the code and instructions on how to test it, see the [Project Walkthrough](walkthrough.md).

---

## Features

- 🔍 **Auto-Detection**: Instantly identifies the API provider based on key prefix and length:
  - **Gemini**: Legacy keys starting with `AIzaSy` and new AI Studio format starting with `AQ.`.
  - **OpenAI**: Legacy keys (`sk-` with 51 chars) and new project keys (`sk-proj-...` with ~156 chars).
  - **Anthropic**: Keys starting with `sk-ant-`.
  - **Groq**: Keys starting with `gsk_`.
  - **OpenRouter**: Keys starting with `sk-or-`.
  - **DeepSeek**: OpenAI-compatible format starting with `sk-` (35 chars).
  - **Tavily / Others**: Flags search utility keys (like `tvly-`) as unsupported LLM keys.
- ⚙️ **Robust Error Categorization**:
  - **Active (Supported)**: Model responds successfully.
  - **Quota Exhausted**: Key is valid but has insufficient credit or rate limit exhausted.
  - **Restricted (Free Tier)**: Identifies models requiring billing enabled or region upgrades.
  - **Unsupported/Inactive**: Model is deprecated or key has no permissions.
- 🚦 **Dynamic Status Tag**: High-visibility status badge (`STATUS: IDLE`, `STATUS: TESTING`, `STATUS: COMPLETE`) changes color (gray, yellow, green) to clearly display current operations.
- 📝 **Details Viewer Panel**: Long error messages are kept clean. Selecting or highlighting any tested model row dynamically displays its full raw API response/error in a dedicated scrollable panel at the bottom right.
- 📋 **Copy & Export Functionality**:
  - **Copy Active List** (`Ctrl + C`): Extracts and copies only successfully active models into a clean bulleted list (perfect to paste into coding agent instructions).
  - **Export Report** (`Ctrl + E`): Exports a clean Markdown table of your full verification results to `wmd_results.md` (which is pre-ignored in `.gitignore`).
- ⚡ **Concurrent Testing**: Utilizes asynchronous batch checking (`httpx`) to test multiple models in seconds without triggering rate limits.
- 🔒 **Secure Local History**: Saves key history locally to `keys_history.json` (ignored by Git). Keys are masked in dropdown selections (e.g. `AQ.Ab-xxxx...xxxx`) to prevent screen leaks.
- 🧪 **Mock Testing Mode**: Includes a built-in mock engine to explore all states without using real/paid API keys.

---

## How to Run (Windows)

The application provides easy launcher scripts for Windows. Double-click the file in Explorer or run from your terminal:

### From standard Command Prompt (cmd.exe):
```cmd
run.bat
```
*(Note: Do not try to run `run.ps1` directly in Command Prompt, as Windows will open it in Notepad by default. Use `run.bat` instead.)*

### From PowerShell:
```powershell
.\run.ps1
```

### ⚡ Fast Startup & Desktop Shortcut
- **First Run**: The script will automatically verify Python, set up a local virtual environment (`.venv`), install dependencies, and **automatically create a "Model Checker" shortcut on your Desktop**.
- **Subsequent Runs**: Double-clicking `run.bat` (or running `.\run.ps1`) bypasses all environment checks and launches the TUI instantly (under 100ms).
- **Desktop Launch**: You can simply double-click the **Model Checker** shortcut icon on your Windows Desktop to open and use the TUI application directly!

---

## Testing with Mock Mode

If you don't have API keys ready or want to test the UI features, you can type one of the following mock keys in the API key input:

- `mock-gemini-free`: Simulates a Gemini Free-tier key (active for Flash, billing restricted for Pro).
- `mock-openai-quota`: Simulates an OpenAI key with exhausted quota / no balance.
- `mock-invalid-key`: Simulates an invalid/expired key (fails pre-validation).
- `mock-gemini-all-active`: Simulates a fully active paid tier key.

---

## Key Bindings in App

- `Ctrl + T`: Trigger verification check.
- `Ctrl + R`: Reset input fields and clear the results table.
- `Ctrl + Q` / `Esc`: Exit the application.
