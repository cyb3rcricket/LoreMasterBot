"""Tests for the 8bitcn-ui styled Gradio Search-to-Chat front-end (src/web.py)
and isolated per-session history handling in src.bot.process_user_turn.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import gradio as gr
import pytest

import src.bot as bot
import src.web as web


@pytest.fixture(autouse=True)
def isolate_bot_and_network(monkeypatch):
    """Prevent real LLM or Blizzard network calls during web UI tests."""
    bot.history.clear()
    monkeypatch.setattr("src.bot.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.bot.get_access_token", lambda: ("mock_token", 3600))
    monkeypatch.setattr("src.api.blizzard.ensure_valid_token", lambda: "mock_token")
    yield
    bot.history.clear()


def test_process_user_turn_isolates_session_history_from_global_history(monkeypatch):
    """Passing conversation_history to process_user_turn must not mutate src.bot.history."""
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Hail, traveler!", tool_calls=None))]
    )
    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(return_value=mock_response))

    session_history = []
    reply, updated_history = bot.process_user_turn("hello", conversation_history=session_history)

    assert reply == "Hail, traveler!"
    assert len(updated_history) == 2
    assert updated_history[0] == {"role": "user", "content": "hello"}
    assert updated_history[1] == {"role": "assistant", "content": "Hail, traveler!"}
    assert bot.history == []


def test_start_search_chat_transitions_from_search_to_chat_view(monkeypatch):
    """Submitting a search query must hide search_view, show chat_view, and append messages."""
    monkeypatch.setattr(
        web,
        "process_user_turn",
        lambda q, conversation_history=None, use_spinner=False: (
            f"Lore for {q}",
            list(conversation_history or [])
            + [{"role": "user", "content": q}, {"role": "assistant", "content": f"Lore for {q}"}],
        ),
    )

    search_vis, chat_vis, messages, llm_hist, cleared_search, cleared_chat = web.start_search_chat(
        "  Tell me about Invincible  ", [], []
    )

    assert search_vis["visible"] is False
    assert chat_vis["visible"] is True
    assert messages == [
        {"role": "user", "content": "Tell me about Invincible"},
        {"role": "assistant", "content": "Lore for Tell me about Invincible"},
    ]
    assert len(llm_hist) == 2
    assert cleared_search == ""
    assert cleared_chat == ""


def test_start_search_chat_ignores_blank_query(monkeypatch):
    """A blank search query must keep search_view visible and skip LLM calls."""
    mock_turn = MagicMock()
    monkeypatch.setattr(web, "process_user_turn", mock_turn)

    search_vis, chat_vis, messages, llm_hist, _, _ = web.start_search_chat("   ", [], [])

    assert not mock_turn.called
    assert search_vis["visible"] is True
    assert chat_vis["visible"] is False
    assert messages == []
    assert llm_hist == []


def test_start_random_lore_quest_selects_starter_query_and_opens_chat(monkeypatch):
    """Random Lore Quest must choose from STARTER_QUERIES and transition to chat view."""
    captured_queries = []

    def fake_turn(q, conversation_history=None, use_spinner=False):
        captured_queries.append(q)
        return "Random lore answer.", [{"role": "user", "content": q}, {"role": "assistant", "content": "Random lore answer."}]

    monkeypatch.setattr(web, "process_user_turn", fake_turn)

    search_vis, chat_vis, messages, llm_hist, _, _ = web.start_random_lore_quest([], [])

    assert len(captured_queries) == 1
    assert captured_queries[0] in web.STARTER_QUERIES
    assert search_vis["visible"] is False
    assert chat_vis["visible"] is True
    assert len(messages) == 2
    assert len(llm_hist) == 2


def test_send_chat_message_appends_followup_and_ignores_empty(monkeypatch):
    """Follow-up messages in the chat view append to the session; blank messages are ignored."""
    monkeypatch.setattr(
        web,
        "process_user_turn",
        lambda q, conversation_history=None, use_spinner=False: (
            "Follow-up lore reply.",
            list(conversation_history or [])
            + [{"role": "user", "content": q}, {"role": "assistant", "content": "Follow-up lore reply."}],
        ),
    )

    existing_msgs = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    existing_hist = list(existing_msgs)

    # Blank follow-up does nothing
    msgs_after_blank, hist_after_blank, cleared = web.send_chat_message("  ", existing_msgs, existing_hist)
    assert msgs_after_blank == existing_msgs
    assert hist_after_blank == existing_hist
    assert cleared == ""

    # Non-empty follow-up appends turn
    msgs_after, hist_after, cleared = web.send_chat_message("Who is Arthas?", existing_msgs, existing_hist)
    assert len(msgs_after) == 4
    assert msgs_after[-2] == {"role": "user", "content": "Who is Arthas?"}
    assert msgs_after[-1] == {"role": "assistant", "content": "Follow-up lore reply."}
    assert len(hist_after) == 4
    assert cleared == ""


def test_reset_to_search_restores_initial_search_view():
    """New Search button handler must restore search_view visibility and clear session state."""
    search_vis, chat_vis, messages, llm_hist, search_val, chat_val = web.reset_to_search()

    assert search_vis["visible"] is True
    assert chat_vis["visible"] is False
    assert messages == []
    assert llm_hist == []
    assert search_val == ""
    assert chat_val == ""


def test_create_web_app_builds_gradio_blocks_with_8bitcn_theme():
    """create_web_app must return a Gradio Blocks instance with 8bitcn-ui CSS and IME JS."""
    app = web.create_web_app()
    assert isinstance(app, gr.Blocks)
    assert "Press Start 2P" in web.EIGHTBIT_CAMPFIRE_CSS
    assert "isComposing" in web.EIGHTBIT_CLIENT_JS
    assert "229" in web.EIGHTBIT_CLIENT_JS


def test_launch_web_initializes_bot_and_launches_blocks(monkeypatch):
    """launch_web must run initialize_bot() before launching the Gradio server."""
    mock_init = MagicMock()
    mock_launch = MagicMock()
    fake_app = SimpleNamespace(launch=mock_launch)

    monkeypatch.setattr(web, "initialize_bot", mock_init)
    monkeypatch.setattr(web, "create_web_app", lambda: fake_app)

    web.launch_web(server_name="127.0.0.1", server_port=7865, share=False)

    assert mock_init.called
    assert mock_launch.called
    assert mock_launch.call_args.kwargs["server_port"] == 7865
