"""Regression tests for lean multi-provider LLM configuration.

These tests cover provider selection, client construction, and clean startup
failures. They must not contact Ollama, Gemini, any cloud model, or Blizzard.
"""

import json
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import src.bot
import src.config as app_config
from src.bot import ToolCall, create_llm_client, run
from src.config import (
    DEFAULT_OLLAMA_BASE_URL,
    GEMINI_OPENAI_BASE_URL,
    OLLAMA_API_KEY,
    llm_provider_error,
)


@pytest.fixture(autouse=True)
def reset_state_and_block_network(monkeypatch):
    """Isolate each test and keep the chat loop off the network."""
    src.bot.history.clear()
    monkeypatch.setattr("src.bot.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.bot.get_access_token", lambda: ("mock_token", 3600))
    monkeypatch.setattr("src.api.blizzard.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.bot.Spinner", MagicMock(return_value=MagicMock()))
    yield
    src.bot.history.clear()


def _set_provider(
    monkeypatch,
    provider,
    model="llama3.1:8b",
    base_url=DEFAULT_OLLAMA_BASE_URL,
    llm_api_key="",
    gemini_api_key="",
):
    """Point src.config at one provider without reloading the module."""
    monkeypatch.setattr(app_config, "LLM_PROVIDER", provider)
    monkeypatch.setattr(app_config, "LLM_MODEL", model)
    monkeypatch.setattr(app_config, "LLM_BASE_URL", base_url)
    monkeypatch.setattr(app_config, "LLM_API_KEY", llm_api_key)
    monkeypatch.setattr(app_config, "GEMINI_API_KEY", gemini_api_key)


def _client_base_url(client):
    return str(client.base_url).rstrip("/")


def _run_startup_in_subprocess(extra_env, unset=()):
    """Start run() in a new process so dotenv cannot see this repo's `.env`."""
    with tempfile.TemporaryDirectory() as temp_dir:
        env = {k: v for k, v in os.environ.items() if k not in unset}
        env.update(extra_env)
        env["PYTHONPATH"] = os.getcwd()
        return subprocess.run(
            [sys.executable, "-c", "from src.bot import run; run()"],
            env=env,
            cwd=temp_dir,
            capture_output=True,
            text=True,
        )


def test_ollama_client_uses_local_base_url_and_dummy_key(monkeypatch):
    """Ollama builds an OpenAI client aimed at the local Ollama URL."""
    _set_provider(monkeypatch, "ollama", base_url="http://localhost:11434/v1")

    client = create_llm_client()

    assert _client_base_url(client) == "http://localhost:11434/v1"
    assert client.api_key == OLLAMA_API_KEY


def test_gemini_client_uses_google_openai_url_and_gemini_key(monkeypatch):
    """Gemini uses Google's OpenAI-compatible URL and GEMINI_API_KEY."""
    _set_provider(
        monkeypatch,
        "gemini",
        model="gemini-user-model",
        gemini_api_key="test-gemini-key",
    )

    client = create_llm_client()

    assert _client_base_url(client) == GEMINI_OPENAI_BASE_URL.rstrip("/")
    assert client.api_key == "test-gemini-key"


def test_custom_client_uses_configured_url_and_key(monkeypatch):
    """Custom uses the user-supplied OpenAI-compatible URL and LLM_API_KEY."""
    _set_provider(
        monkeypatch,
        "custom",
        model="my-hosted-model",
        base_url="https://llm.example.test/v1",
        llm_api_key="test-custom-key",
    )

    client = create_llm_client()

    assert _client_base_url(client) == "https://llm.example.test/v1"
    assert client.api_key == "test-custom-key"


def test_missing_gemini_key_fails_only_when_gemini_selected(monkeypatch):
    """GEMINI_API_KEY is required for Gemini and ignored for Ollama."""
    _set_provider(monkeypatch, "gemini", model="gemini-user-model", gemini_api_key="")
    error = llm_provider_error()
    assert error is not None
    assert "GEMINI_API_KEY" in error
    assert "missing" in error.lower()

    _set_provider(monkeypatch, "ollama", gemini_api_key="")
    assert llm_provider_error() is None


def test_missing_custom_config_fails_only_when_custom_selected(monkeypatch):
    """Custom URL/key/model are required only when custom is the active provider."""
    _set_provider(
        monkeypatch,
        "custom",
        model="",
        base_url="",
        llm_api_key="",
    )
    error = llm_provider_error()
    assert error is not None
    assert "Custom provider is selected" in error

    _set_provider(monkeypatch, "custom", model="hosted", base_url="", llm_api_key="k")
    assert "LLM_BASE_URL" in llm_provider_error()

    _set_provider(
        monkeypatch,
        "custom",
        model="hosted",
        base_url="https://llm.example.test/v1",
        llm_api_key="",
    )
    assert "LLM_API_KEY" in llm_provider_error()

    _set_provider(
        monkeypatch,
        "custom",
        model="",
        base_url="https://llm.example.test/v1",
        llm_api_key="k",
    )
    assert "LLM_MODEL" in llm_provider_error()

    _set_provider(monkeypatch, "ollama", model="llama3.1:8b", base_url="", llm_api_key="")
    assert llm_provider_error() is None


def test_ollama_does_not_require_gemini_or_custom_keys(monkeypatch):
    """Ollama startup validation passes with no GEMINI_API_KEY or LLM_API_KEY."""
    _set_provider(monkeypatch, "ollama", gemini_api_key="", llm_api_key="")
    assert llm_provider_error() is None

    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Farewell.", tool_calls=None))]
    )
    monkeypatch.setattr(src.bot.client.chat.completions, "create", MagicMock(return_value=mock_response))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["quit"]))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))

    run()

    output = "\n".join(printed)
    assert "GEMINI_API_KEY" not in output
    assert "LLM_API_KEY" not in output
    assert "AI provider: Ollama /" in output


def test_unknown_provider_fails_cleanly(monkeypatch):
    """An unknown LLM_PROVIDER exits with valid choices and no traceback."""
    _set_provider(monkeypatch, "chatgpt")
    error = llm_provider_error()
    assert "Unknown LLM_PROVIDER 'chatgpt'" in error
    assert "ollama" in error
    assert "gemini" in error
    assert "custom" in error

    printed = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))
    blizzard_auth = MagicMock()
    monkeypatch.setattr("src.bot._authenticate_blizzard", blizzard_auth)

    with pytest.raises(SystemExit) as exc:
        run()

    assert exc.value.code == 1
    assert blizzard_auth.call_count == 0
    assert "Unknown LLM_PROVIDER 'chatgpt'" in "\n".join(printed)


def test_llm_model_used_on_initial_and_final_model_calls(monkeypatch):
    """The configured LLM_MODEL is the only model name sent on both chat calls."""
    configured_model = "configured-test-model"
    monkeypatch.setattr(src.bot, "LLM_MODEL", configured_model)

    tool_call = ToolCall(
        id="call_model_aaaaaaaaaaaaaaaaaaaaaaaa",
        name="lookup_item",
        arguments='{"item_id": "19019"}',
    )
    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Thunderfury lore.", tool_calls=None))]
    )
    mock_create = MagicMock(side_effect=[first_resp, second_resp])
    monkeypatch.setattr(src.bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Thunderfury", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(src.bot.TOOL_HANDLERS, "lookup_item", MagicMock(return_value="Thunderfury: 19019"))

    run()

    assert mock_create.call_count == 2
    assert mock_create.call_args_list[0].kwargs["model"] == configured_model
    assert mock_create.call_args_list[1].kwargs["model"] == configured_model


def test_missing_gemini_key_run_exits_before_blizzard(monkeypatch):
    """run() prints a short Gemini warning and never authenticates Blizzard."""
    _set_provider(monkeypatch, "gemini", model="gemini-user-model", gemini_api_key="")
    printed = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))
    blizzard_auth = MagicMock()
    monkeypatch.setattr("src.bot._authenticate_blizzard", blizzard_auth)

    with pytest.raises(SystemExit) as exc:
        run()

    output = "\n".join(printed)
    assert exc.value.code == 1
    assert blizzard_auth.call_count == 0
    assert "GEMINI_API_KEY" in output
    assert "test-gemini-key" not in output
    assert "Traceback" not in output


def test_missing_custom_config_run_exits_before_blizzard(monkeypatch):
    """run() prints a short custom-provider warning and never authenticates Blizzard."""
    _set_provider(monkeypatch, "custom", model="hosted", base_url="", llm_api_key="")
    printed = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)))
    blizzard_auth = MagicMock()
    monkeypatch.setattr("src.bot._authenticate_blizzard", blizzard_auth)

    with pytest.raises(SystemExit) as exc:
        run()

    output = "\n".join(printed)
    assert exc.value.code == 1
    assert blizzard_auth.call_count == 0
    assert "LLM_BASE_URL" in output
    assert "test-custom-key" not in output


def test_gemini_startup_subprocess_exits_cleanly_without_key():
    """A fresh process with Gemini and no key exits 1 and prints no traceback."""
    result = _run_startup_in_subprocess(
        {
            "LLM_PROVIDER": "gemini",
            "LLM_MODEL": "gemini-user-model",
            "GEMINI_API_KEY": "",
            "BLIZZARD_CLIENT_ID": "mock_client_id",
            "BLIZZARD_CLIENT_SECRET": "mock_client_secret",
        },
        unset=("GEMINI_API_KEY",),
    )

    assert result.returncode == 1
    assert "GEMINI_API_KEY" in result.stdout
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout


def test_unknown_provider_subprocess_exits_cleanly():
    """A fresh process with an unknown provider exits 1 and lists valid choices."""
    result = _run_startup_in_subprocess(
        {
            "LLM_PROVIDER": "not-a-provider",
            "BLIZZARD_CLIENT_ID": "mock_client_id",
            "BLIZZARD_CLIENT_SECRET": "mock_client_secret",
        }
    )

    assert result.returncode == 1
    assert "Unknown LLM_PROVIDER 'not-a-provider'" in result.stdout
    assert "ollama, gemini, custom" in result.stdout
    assert "Traceback" not in result.stderr


def test_importing_with_gemini_and_no_key_does_not_network_or_exit():
    """Importing modules must not require GEMINI_API_KEY or contact any API."""
    env = {
        **os.environ,
        "LLM_PROVIDER": "gemini",
        "LLM_MODEL": "gemini-user-model",
        "GEMINI_API_KEY": "",
        "BLIZZARD_CLIENT_ID": "",
        "BLIZZARD_CLIENT_SECRET": "",
    }
    env.pop("GEMINI_API_KEY", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import src.api.blizzard as blizzard;"
                "blizzard.get_access_token = lambda: (_ for _ in ()).throw(RuntimeError('blizzard'));"
                "import src.config, src.bot"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_config_import_does_not_require_unused_provider_keys():
    """Default Ollama config import stays valid without Gemini or custom keys."""
    env = {k: v for k, v in os.environ.items() if k not in {"GEMINI_API_KEY", "LLM_API_KEY", "LLM_PROVIDER"}}
    env["PYTHONPATH"] = os.getcwd()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import src.config as c;"
                "assert c.LLM_PROVIDER == 'ollama';"
                "assert c.LLM_MODEL == 'llama3.1:8b';"
                "assert c.llm_provider_error() is None;"
                "print('ok')"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_history_after_tool_call_stays_serializable_with_configured_model(monkeypatch):
    """Provider wiring must not change tool-call history shape or JSON safety."""
    monkeypatch.setattr(src.bot, "LLM_MODEL", "history-test-model")
    call_id = "call_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    tool_call = ToolCall(id=call_id, name="lookup_item", arguments='{"item_id": "19019"}')
    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Kept in the archives.", tool_calls=None))]
    )
    monkeypatch.setattr(
        src.bot.client.chat.completions,
        "create",
        MagicMock(side_effect=[first_resp, second_resp]),
    )
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["item 19019", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(src.bot.TOOL_HANDLERS, "lookup_item", MagicMock(return_value="Thunderfury"))

    run()

    assert json.dumps(src.bot.history)
    assistant = next(h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    tool_entry = next(h for h in src.bot.history if h.get("role") == "tool")
    assert tool_entry["tool_call_id"] == assistant["tool_calls"][0]["id"] == call_id
