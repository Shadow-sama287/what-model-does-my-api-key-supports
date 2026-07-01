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
- ⚡ **Concurrent Testing**: Utilizes asynchronous batch checking (`httpx`) to test multiple models in seconds without triggering rate limits.
- 🔒 **Secure Local History**: Saves key history locally to `keys_history.json` (explicitly ignored by Git so it never leaks to GitHub). Keys are masked in dropdown selections (e.g. `AQ.Ab-xxxx...xxxx`) to prevent shoulder surfing.
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

*Note: The script will automatically check for Python, set up a virtual environment (`.venv`), install all required dependencies from `requirements.txt`, and start the app.*

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
