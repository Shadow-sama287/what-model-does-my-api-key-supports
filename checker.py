import asyncio
import re
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import httpx

@dataclass
class ModelCheckResult:
    model_name: str
    status: str  # "Active", "Quota Exhausted", "Restricted (Free Tier)", "Unsupported/Inactive", "Error"
    status_code: Optional[int]
    error_message: str = ""
    latency_ms: float = 0.0

# Curated lists of popular/current models for fallback testing
PROVIDER_MODELS = {
    "Gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite-preview-02-05",
        "gemini-2.0-pro-exp-02-05",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro"
    ],
    "OpenAI": [
        "gpt-4o-mini",
        "gpt-4o",
        "o1-mini",
        "o1",
        "o3-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo"
    ],
    "Anthropic": [
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-opus-latest",
        "claude-3-haiku-20240307"
    ],
    "OpenRouter": [
        "google/gemini-2.5-flash",
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-haiku",
        "meta-llama/llama-3.3-70b-instruct",
        "deepseek/deepseek-chat"
    ],
    "Groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
        "deepseek-r1-distill-llama-70b"
    ],
    "DeepSeek": [
        "deepseek-chat",
        "deepseek-reasoner"
    ]
}

def detect_provider(api_key: str) -> Tuple[str, str]:
    """
    Detect the provider based on key structure.
    Returns (provider_name, status_message).
    If unknown, returns ("Unknown", "No matching pattern").
    """
    key = api_key.strip()
    if not key:
        return "Unknown", "Empty API Key"

    if key.startswith("mock-"):
        # For mock testing
        for provider in PROVIDER_MODELS.keys():
            if provider.lower() in key.lower():
                return provider, f"Mock {provider} Key Detected"
        return "Gemini", "Mock Gemini Key Detected (Fallback)"

    if key.startswith("AIzaSy"):
        return "Gemini", "Google Gemini Key (Legacy Format)"
    if key.startswith("AQ."):
        return "Gemini", "Google Gemini Key (New Format)"
    
    if key.startswith("sk-ant-"):
        return "Anthropic", "Anthropic Claude Key"
    
    if key.startswith("gsk_"):
        return "Groq", "Groq Key"
        
    if key.startswith("sk-or-"):
        return "OpenRouter", "OpenRouter Key"

    if key.startswith("tvly-"):
        return "Unsupported", "Tavily Web Search Key (Not an LLM Key)"

    if key.startswith("sk-proj-"):
        return "OpenAI", "OpenAI Project Key"
    
    # Check sk- keys based on length
    if key.startswith("sk-"):
        if len(key) == 35:  # sk- + 32 characters
            return "DeepSeek", "DeepSeek Key (Length 35)"
        if len(key) == 51:  # sk- + 48 characters
            return "OpenAI", "OpenAI User Key (Legacy Length)"
        return "OpenAI-Compatible", "Generic OpenAI-Compatible Key"

    return "Unknown", "Unrecognized pattern. Please select the provider manually."

class APIKeyChecker:
    def __init__(self, provider: str, api_key: str, is_mock: bool = False):
        self.provider = provider
        self.api_key = api_key.strip()
        self.is_mock = is_mock or self.api_key.startswith("mock-")
        self.models_to_test = PROVIDER_MODELS.get(provider, [])
        if provider == "OpenAI-Compatible":
            # Default to OpenAI models if generic
            self.models_to_test = PROVIDER_MODELS["OpenAI"]

    async def get_available_models(self) -> List[str]:
        """
        Query the provider API to fetch the list of models registered for the key.
        Returns a list of model names. Falls back to curated list on error/no support.
        """
        if self.is_mock:
            return self.models_to_test

        models = list(self.models_to_test)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                if self.provider == "Gemini":
                    # Google Gemini models.list endpoint
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = [m["name"].split("/")[-1] for m in data.get("models", []) 
                                   if "generateContent" in m.get("supportedGenerationMethods", [])]
                        if fetched:
                            # Prioritize fetched but keep the order of our curated ones first
                            unique_models = []
                            for m in fetched:
                                if m not in unique_models:
                                    unique_models.append(m)
                            for m in models:
                                if m not in unique_models:
                                    unique_models.append(m)
                            return unique_models
                elif self.provider in ["OpenAI", "OpenAI-Compatible"]:
                    url = "https://api.openai.com/v1/models"
                    resp = await client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = [m["id"] for m in data.get("data", [])]
                        # Filter to text/chat models
                        chat_fetched = [m for m in fetched if any(x in m for x in ["gpt-", "o1-", "o3-", "text-davinci"])]
                        if chat_fetched:
                            return sorted(chat_fetched, key=lambda x: ("gpt-4" in x or "o1" in x or "o3" in x), reverse=True)
                elif self.provider == "Groq":
                    url = "https://api.groq.com/openai/v1/models"
                    resp = await client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = [m["id"] for m in data.get("data", [])]
                        if fetched:
                            return fetched
                elif self.provider == "DeepSeek":
                    url = "https://api.deepseek.com/models"
                    resp = await client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = [m["id"] for m in data.get("data", [])]
                        if fetched:
                            return fetched
            except Exception:
                pass # Fall back to default curated models list

        return models

    async def check_single_model(self, model: str, client: httpx.AsyncClient) -> ModelCheckResult:
        """
        Asynchronously checks support for a single model.
        """
        if self.is_mock:
            return await self._check_mock_model(model)

        start_time = time.time()
        try:
            if self.provider == "Gemini":
                # Google Gemini test generate request
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"parts": [{"text": "say ."}]}],
                    "generationConfig": {"maxOutputTokens": 1}
                }
                resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                latency = (time.time() - start_time) * 1000.0
                return self._parse_gemini_response(model, resp, latency)

            elif self.provider in ["OpenAI", "OpenAI-Compatible"]:
                url = "https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "."}],
                    "max_tokens": 1
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                resp = await client.post(url, json=payload, headers=headers)
                latency = (time.time() - start_time) * 1000.0
                return self._parse_openai_response(model, resp, latency)

            elif self.provider == "Anthropic":
                url = "https://api.anthropic.com/v1/messages"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "."}],
                    "max_tokens": 1
                }
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                resp = await client.post(url, json=payload, headers=headers)
                latency = (time.time() - start_time) * 1000.0
                return self._parse_anthropic_response(model, resp, latency)

            elif self.provider == "OpenRouter":
                # First check is auth/key. If we have done it, we run chat completions.
                url = "https://openrouter.ai/api/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "."}],
                    "max_tokens": 1
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                resp = await client.post(url, json=payload, headers=headers)
                latency = (time.time() - start_time) * 1000.0
                return self._parse_openrouter_response(model, resp, latency)

            elif self.provider == "Groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "."}],
                    "max_tokens": 1
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                resp = await client.post(url, json=payload, headers=headers)
                latency = (time.time() - start_time) * 1000.0
                return self._parse_openai_response(model, resp, latency)

            elif self.provider == "DeepSeek":
                url = "https://api.deepseek.com/chat/completions"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "."}],
                    "max_tokens": 1
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                resp = await client.post(url, json=payload, headers=headers)
                latency = (time.time() - start_time) * 1000.0
                return self._parse_openai_response(model, resp, latency)

        except httpx.RequestError as exc:
            latency = (time.time() - start_time) * 1000.0
            return ModelCheckResult(
                model_name=model,
                status="Error",
                status_code=None,
                error_message=f"Network Connection Failed: {str(exc)}",
                latency_ms=latency
            )

        return ModelCheckResult(model, "Unsupported/Inactive", 400, "Unknown state")

    async def check_key_validity_early(self) -> Tuple[bool, str]:
        """
        Quick check of key validity by doing a metadata query or a fast test check.
        Returns (is_valid, message).
        """
        if self.is_mock:
            if "invalid" in self.api_key.lower():
                return False, "API Key is invalid (Mock Mode)"
            return True, "Mock Key is valid"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                if self.provider == "Gemini":
                    # Fetch models list as a validation test
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return True, "API Key is valid."
                    elif resp.status_code in [400, 403]:
                        err_msg = ""
                        try:
                            err_msg = resp.json().get("error", {}).get("message", "")
                        except Exception:
                            pass
                        if "API key not valid" in err_msg or "INVALID_ARGUMENT" in err_msg or "invalid" in err_msg.lower():
                            return False, f"Invalid API Key: {err_msg or resp.text}"
                        return True, f"Key validated but list failed (Code {resp.status_code}). Proceeding to test individual models."

                elif self.provider in ["OpenAI", "OpenAI-Compatible", "DeepSeek", "Groq"]:
                    url = "https://api.openai.com/v1/models"
                    if self.provider == "DeepSeek":
                        url = "https://api.deepseek.com/models"
                    elif self.provider == "Groq":
                        url = "https://api.groq.com/openai/v1/models"
                        
                    resp = await client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
                    if resp.status_code == 200:
                        return True, "API Key is valid."
                    elif resp.status_code == 401:
                        return False, "Invalid API Key (Unauthorized)."
                    elif resp.status_code == 429:
                        return True, "Key is valid but rate-limited/exhausted. Proceeding to double-check models."

                elif self.provider == "Anthropic":
                    # Anthropic doesn't have a simple list models API, test the most basic model
                    model = "claude-3-5-haiku-latest"
                    res = await self.check_single_model(model, client)
                    if res.status == "Error" and "authentication" in res.error_message.lower():
                        return False, "Invalid API Key (Authentication Error)."
                    return True, "Proceeding to test models..."

                elif self.provider == "OpenRouter":
                    # OpenRouter key status endpoint
                    url = "https://openrouter.ai/api/v1/auth/key"
                    resp = await client.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
                    if resp.status_code == 200:
                        data = resp.json()
                        limit = data.get("data", {}).get("limit", "No Limit")
                        usage = data.get("data", {}).get("usage", 0)
                        return True, f"Valid OpenRouter Key. Limit: {limit}, Usage: {usage}"
                    elif resp.status_code == 401:
                        return False, "Invalid OpenRouter API Key."

            except Exception as e:
                return True, f"Pre-validation skipped due to error: {str(e)}. Testing models..."

        return True, "Proceeding with model checks..."

    # --- Response Parsers ---
    def _parse_gemini_response(self, model: str, resp: httpx.Response, latency: float) -> ModelCheckResult:
        if resp.status_code == 200:
            return ModelCheckResult(model, "Active", 200, "Successfully responded", latency)

        error_data = {}
        try:
            error_data = resp.json().get("error", {})
        except Exception:
            pass

        msg = error_data.get("message", resp.text)
        status = error_data.get("status", "")

        # Categorize
        if resp.status_code == 429 or status == "RESOURCE_EXHAUSTED" or "quota" in msg.lower():
            return ModelCheckResult(model, "Quota Exhausted", resp.status_code, "Rate limit reached or quota exhausted", latency)
        
        if resp.status_code == 403:
            # Check for location/billing/permission
            if "billing" in msg.lower() or "pay-as-you-go" in msg.lower():
                return ModelCheckResult(model, "Restricted (Free Tier)", resp.status_code, "Requires Billing Enabled (Paid Tier model)", latency)
            if "location" in msg.lower() or "not supported" in msg.lower():
                return ModelCheckResult(model, "Restricted (Free Tier)", resp.status_code, "Region not supported for this model", latency)
            return ModelCheckResult(model, "Restricted (Free Tier)", resp.status_code, f"Permission Denied: {msg}", latency)

        if resp.status_code == 404 or "not found" in msg.lower() or "method not found" in msg.lower():
            return ModelCheckResult(model, "Unsupported/Inactive", resp.status_code, "Model not found or deprecated for this key", latency)

        return ModelCheckResult(model, "Error", resp.status_code, msg, latency)

    def _parse_openai_response(self, model: str, resp: httpx.Response, latency: float) -> ModelCheckResult:
        if resp.status_code == 200:
            return ModelCheckResult(model, "Active", 200, "Successfully responded", latency)

        error_data = {}
        try:
            error_data = resp.json().get("error", {})
        except Exception:
            pass

        msg = error_data.get("message", resp.text)
        code = error_data.get("code", "")

        if resp.status_code == 429 or code == "insufficient_quota" or "quota" in msg.lower():
            return ModelCheckResult(model, "Quota Exhausted", resp.status_code, "Insufficient credits / quota exhausted", latency)
        
        if resp.status_code == 404 or "model_not_found" in code or "does not exist" in msg:
            return ModelCheckResult(model, "Unsupported/Inactive", resp.status_code, "Model not supported or access restricted", latency)

        if resp.status_code == 403:
            return ModelCheckResult(model, "Restricted (Free Tier)", resp.status_code, f"Restricted: {msg}", latency)

        return ModelCheckResult(model, "Error", resp.status_code, msg, latency)

    def _parse_anthropic_response(self, model: str, resp: httpx.Response, latency: float) -> ModelCheckResult:
        if resp.status_code in [200, 201]:
            return ModelCheckResult(model, "Active", resp.status_code, "Successfully responded", latency)

        error_data = {}
        try:
            error_data = resp.json().get("error", {})
        except Exception:
            pass

        msg = error_data.get("message", resp.text)
        err_type = error_data.get("type", "")

        if resp.status_code == 429 or err_type == "rate_limit_error" or "quota" in msg.lower() or "credit" in msg.lower():
            return ModelCheckResult(model, "Quota Exhausted", resp.status_code, "Rate limit exceeded or balance empty", latency)

        if resp.status_code == 403 or err_type == "permission_error":
            return ModelCheckResult(model, "Restricted (Free Tier)", resp.status_code, "Requires upgraded tier or billing", latency)

        if resp.status_code == 400 and "not found" in msg.lower():
            return ModelCheckResult(model, "Unsupported/Inactive", resp.status_code, "Model not found or unsupported", latency)

        return ModelCheckResult(model, "Error", resp.status_code, msg, latency)

    def _parse_openrouter_response(self, model: str, resp: httpx.Response, latency: float) -> ModelCheckResult:
        if resp.status_code == 200:
            # OpenRouter can return error payload inside 200 OK
            try:
                data = resp.json()
                if "error" in data:
                    err = data["error"]
                    msg = err.get("message", "")
                    code = err.get("code", 0)
                    if code == 429 or "credit" in msg.lower() or "balance" in msg.lower():
                        return ModelCheckResult(model, "Quota Exhausted", code, f"OpenRouter: {msg}", latency)
                    if code == 403:
                        return ModelCheckResult(model, "Restricted (Free Tier)", code, f"Restricted: {msg}", latency)
                    return ModelCheckResult(model, "Error", code, msg, latency)
            except Exception:
                pass
            return ModelCheckResult(model, "Active", 200, "Successfully responded", latency)

        error_data = {}
        try:
            error_data = resp.json().get("error", {})
        except Exception:
            pass

        msg = error_data.get("message", resp.text)

        if resp.status_code == 429 or "quota" in msg.lower() or "credit" in msg.lower() or "balance" in msg.lower():
            return ModelCheckResult(model, "Quota Exhausted", resp.status_code, "OpenRouter credit exhausted", latency)

        if resp.status_code == 403:
            return ModelCheckResult(model, "Restricted (Free Tier)", resp.status_code, f"Restricted: {msg}", latency)

        return ModelCheckResult(model, "Error", resp.status_code, msg, latency)

    # --- Mock Mode Tester ---
    async def _check_mock_model(self, model: str) -> ModelCheckResult:
        """
        Simulate check for models using fake delays and status codes.
        """
        await asyncio.sleep(0.3 + (time.time() % 0.4))  # simulated delay 300-700ms
        latency = (0.3 + (time.time() % 0.4)) * 1000.0

        key_lower = self.api_key.lower()

        # Mock Quota Exhausted Scenario
        if "quota" in key_lower:
            return ModelCheckResult(
                model_name=model,
                status="Quota Exhausted",
                status_code=429,
                error_message="RESOURCE_EXHAUSTED: Quota exceeded for model",
                latency_ms=latency
            )

        # Mock Restricted/Free Key Scenario
        if "free" in key_lower:
            if "1.0-pro" in model:
                return ModelCheckResult(
                    model_name=model,
                    status="Unsupported/Inactive",
                    status_code=404,
                    error_message="Model deprecated or no access.",
                    latency_ms=latency
                )
            elif "pro" in model or "opus" in model or "gpt-4o" == model or "claude-3-5-sonnet" in model:
                return ModelCheckResult(
                    model_name=model,
                    status="Restricted (Free Tier)",
                    status_code=403,
                    error_message="PERMISSION_DENIED: Billing has not been enabled on this project.",
                    latency_ms=latency
                )
            else:
                return ModelCheckResult(
                    model_name=model,
                    status="Active",
                    status_code=200,
                    error_message="Successfully responded",
                    latency_ms=latency
                )

        # General Mock Success
        return ModelCheckResult(
            model_name=model,
            status="Active",
            status_code=200,
            error_message="Successfully responded",
            latency_ms=latency
        )
