# Gradio 8bitcn-ui Search-to-Chat front-end for LoreMasterBot.
#
# Presents a classic search engine landing page styled with the 8bitcn-ui
# design system ("Press Start 2P" pixel typography, stepped 8-bit borders,
# hard offset shadows, and a Dark Azeroth Campfire palette). Submitting a
# query transitions the view into an in-character RPG Quest Log chat.
import random
import gradio as gr

from src import config as app_config
from src.bot import initialize_bot, process_user_turn
from src.config import llm_provider_label

STARTER_QUERIES = (
    "Tell me about the mount Invincible",
    "Who is Professor Putricide?",
    "Tell me about Thunderfury",
    "Tell me the story of Karazhan",
    "What is the current WoW Token price?",
    "Tell me about the Human race",
)

# 8bitcn-ui inspired Dark Azeroth Campfire CSS theme.
# Uses "Press Start 2P" for headings/buttons/badges, "VT323" / monospace for
# readable multi-paragraph lore replies, 4px solid pixel borders, zero border
# radius, and stepped 4px hard offset shadows.
EIGHTBIT_CAMPFIRE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --eightbit-bg: #0d0b14;
    --eightbit-surface: #171326;
    --eightbit-surface-alt: #211b36;
    --eightbit-text: #f6ead4;
    --eightbit-muted: #c2b295;
    --eightbit-gold: #f59e0b;
    --eightbit-gold-bright: #fbbf24;
    --eightbit-ember: #ea580c;
    --eightbit-border: #000000;
    --eightbit-pixel-ring: #f59e0b;
    --font-pixel: 'Press Start 2P', monospace;
    --font-lore: 'JetBrains Mono', 'VT323', monospace;
}

body, .gradio-container {
    background-color: var(--eightbit-bg) !important;
    background-image:
        radial-gradient(circle at 50% 18%, rgba(245, 158, 11, 0.14) 0%, transparent 55%),
        linear-gradient(180deg, #0d0b14 0%, #120f1d 100%) !important;
    color: var(--eightbit-text) !important;
    font-family: var(--font-lore) !important;
    min-height: 100vh;
}

/* Remove rounded corners everywhere to enforce 8bitcn-ui stepped pixel geometry */
.gradio-container *,
.gradio-container input,
.gradio-container textarea,
.gradio-container button {
    border-radius: 0px !important;
}

/* Search landing hero layout */
#search-view-container {
    max-width: 780px;
    margin: 7vh auto 2rem auto;
    padding: 2.25rem 1.75rem;
    background: var(--eightbit-surface);
    border: 4px solid var(--eightbit-gold);
    box-shadow:
        0 0 0 4px var(--eightbit-border),
        8px 8px 0 4px var(--eightbit-border);
}

.eightbit-logo-box {
    text-align: center;
    margin-bottom: 1.5rem;
}

.eightbit-title {
    font-family: var(--font-pixel) !important;
    font-size: clamp(1.35rem, 3vw, 2.1rem);
    line-height: 1.45;
    color: var(--eightbit-gold-bright);
    text-shadow: 4px 4px 0px var(--eightbit-border);
    margin: 0 0 0.75rem 0;
    letter-spacing: 1px;
}

.eightbit-subtitle {
    font-family: var(--font-lore) !important;
    font-size: 1.05rem;
    color: var(--eightbit-muted);
    margin: 0 0 1rem 0;
}

.eightbit-badge-row {
    display: flex;
    justify-content: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-top: 0.5rem;
}

.eightbit-badge {
    display: inline-block;
    font-family: var(--font-pixel) !important;
    font-size: 0.65rem;
    line-height: 1.4;
    padding: 0.4rem 0.65rem;
    background: var(--eightbit-surface-alt);
    color: var(--eightbit-gold-bright);
    border: 2px solid var(--eightbit-gold);
    box-shadow: 3px 3px 0px 0px var(--eightbit-border);
    text-transform: uppercase;
}

/* Accessible labels and inputs */
#search-input-box label span,
#chat-input-box label span {
    font-family: var(--font-pixel) !important;
    font-size: 0.72rem !important;
    color: var(--eightbit-gold-bright) !important;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 0.35rem;
}

#search-input-box textarea,
#search-input-box input,
#chat-input-box textarea,
#chat-input-box input {
    font-family: var(--font-lore) !important;
    font-size: 1rem !important;
    line-height: 1.5 !important;
    min-height: 48px !important;
    padding: 0.75rem 1rem !important;
    background-color: #09070e !important;
    color: var(--eightbit-text) !important;
    border: 3px solid var(--eightbit-gold) !important;
    box-shadow: 4px 4px 0px 0px var(--eightbit-border) !important;
}

@media (pointer: coarse) {
    #search-input-box textarea,
    #search-input-box input,
    #chat-input-box textarea,
    #chat-input-box input,
    .eightbit-btn,
    .eightbit-chip-btn {
        min-height: 52px !important;
    }
}

/* High-contrast focus states per modern-web-guidance forms guidelines */
.gradio-container input:focus-visible,
.gradio-container textarea:focus-visible,
.gradio-container button:focus-visible {
    outline: 3px solid var(--eightbit-gold-bright) !important;
    outline-offset: 2px !important;
}

/* 8bitcn-ui pixel buttons */
.eightbit-btn {
    font-family: var(--font-pixel) !important;
    font-size: 0.75rem !important;
    line-height: 1.4 !important;
    min-height: 48px !important;
    padding: 0.75rem 1.1rem !important;
    border: 3px solid var(--eightbit-border) !important;
    box-shadow: 4px 4px 0px 0px var(--eightbit-border) !important;
    text-transform: uppercase;
    cursor: pointer;
    transition: transform 0.06s ease, box-shadow 0.06s ease !important;
}

.eightbit-btn-primary {
    background: var(--eightbit-gold) !important;
    color: #120d05 !important;
    border-color: var(--eightbit-gold-bright) !important;
}

.eightbit-btn-secondary {
    background: var(--eightbit-surface-alt) !important;
    color: var(--eightbit-text) !important;
    border-color: var(--eightbit-gold) !important;
}

.eightbit-btn:hover {
    filter: brightness(1.08);
}

.eightbit-btn:active {
    transform: translate(2px, 2px) !important;
    box-shadow: 2px 2px 0px 0px var(--eightbit-border) !important;
}

/* Starter query chips */
.eightbit-chips-heading {
    font-family: var(--font-pixel) !important;
    font-size: 0.68rem;
    color: var(--eightbit-muted);
    text-align: center;
    text-transform: uppercase;
    margin: 1.25rem 0 0.5rem 0;
}

.eightbit-chip-btn {
    font-family: var(--font-lore) !important;
    font-size: 0.92rem !important;
    min-height: 42px !important;
    background: #120e1e !important;
    color: var(--eightbit-text) !important;
    border: 2px solid #52436e !important;
    box-shadow: 3px 3px 0px 0px var(--eightbit-border) !important;
}

.eightbit-chip-btn:hover {
    border-color: var(--eightbit-gold) !important;
    color: var(--eightbit-gold-bright) !important;
}

/* Chat Quest Log view */
#chat-view-container {
    max-width: 920px;
    margin: 2vh auto;
    padding: 1.25rem;
    background: var(--eightbit-surface);
    border: 4px solid var(--eightbit-gold);
    box-shadow:
        0 0 0 4px var(--eightbit-border),
        8px 8px 0 4px var(--eightbit-border);
}

.eightbit-chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding-bottom: 0.75rem;
    border-bottom: 3px solid var(--eightbit-gold);
    margin-bottom: 0.75rem;
}

.eightbit-chat-header-title {
    font-family: var(--font-pixel) !important;
    font-size: 0.95rem;
    color: var(--eightbit-gold-bright);
    text-shadow: 2px 2px 0px var(--eightbit-border);
    margin: 0;
}

#eightbit-chatbot {
    background: #0b0912 !important;
    border: 3px solid var(--eightbit-gold) !important;
    box-shadow: inset 0 0 0 2px var(--eightbit-border) !important;
    font-family: var(--font-lore) !important;
    font-size: 1rem !important;
    line-height: 1.55 !important;
}
"""

# Client-side setup for search input attributes & IME-safe Enter handling
# per modern-web-guidance `forms` and `ime-safe-enter-submit` guides.
EIGHTBIT_CLIENT_JS = """
() => {
    const configureInputs = () => {
        const searchContainer = document.getElementById('search-input-box');
        if (searchContainer) {
            const searchField = searchContainer.querySelector('textarea, input');
            if (searchField && !searchField.dataset.eightbitConfigured) {
                searchField.setAttribute('autocorrect', 'off');
                searchField.setAttribute('autocapitalize', 'off');
                searchField.setAttribute('spellcheck', 'false');
                searchField.setAttribute('enterkeyhint', 'search');
                searchField.dataset.eightbitConfigured = 'true';
            }
        }

        const allFields = document.querySelectorAll('#search-input-box textarea, #search-input-box input, #chat-input-box textarea, #chat-input-box input');
        allFields.forEach((field) => {
            if (field.dataset.imeSafeBound) return;
            field.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                    if (event.isComposing || event.keyCode === 229) {
                        event.stopImmediatePropagation();
                        event.preventDefault();
                    }
                }
            }, true);
            field.dataset.imeSafeBound = 'true';
        });
    };

    configureInputs();
    const observer = new MutationObserver(() => configureInputs());
    observer.observe(document.body, { childList: true, subtree: true });
}
"""


def _provider_status_html():
    """Render an 8bitcn-ui style status badge showing the active AI provider and model."""
    provider = llm_provider_label()
    model = app_config.LLM_MODEL or "default"
    return (
        '<div class="eightbit-badge-row">'
        f'<span class="eightbit-badge">Realm: Azeroth Archives</span>'
        f'<span class="eightbit-badge">Oracle: {provider} / {model}</span>'
        "</div>"
    )


def start_search_chat(query, chat_messages, llm_history):
    """Handle submission from the search landing page and transition to chat view.

    If the query is blank, stays on the search landing page without calling the LLM.
    """
    cleaned_query = (query or "").strip()
    current_messages = list(chat_messages or [])
    current_llm_history = list(llm_history or [])

    if not cleaned_query:
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            current_messages,
            current_llm_history,
            "",
            "",
        )

    reply, updated_llm_history = process_user_turn(
        cleaned_query,
        conversation_history=current_llm_history,
        use_spinner=False,
    )
    current_messages.append({"role": "user", "content": cleaned_query})
    current_messages.append({"role": "assistant", "content": reply})

    return (
        gr.update(visible=False),
        gr.update(visible=True),
        current_messages,
        updated_llm_history,
        "",
        "",
    )


def start_random_lore_quest(chat_messages, llm_history):
    """Pick a random starter lore query and begin a chat session immediately."""
    chosen_query = random.choice(STARTER_QUERIES)
    return start_search_chat(chosen_query, chat_messages, llm_history)


def send_chat_message(user_message, chat_messages, llm_history):
    """Send a follow-up message inside the active chat view."""
    cleaned_message = (user_message or "").strip()
    current_messages = list(chat_messages or [])
    current_llm_history = list(llm_history or [])

    if not cleaned_message:
        return current_messages, current_llm_history, ""

    reply, updated_llm_history = process_user_turn(
        cleaned_message,
        conversation_history=current_llm_history,
        use_spinner=False,
    )
    current_messages.append({"role": "user", "content": cleaned_message})
    current_messages.append({"role": "assistant", "content": reply})

    return current_messages, updated_llm_history, ""


def reset_to_search():
    """Clear the current session conversation and return to the search landing view."""
    return (
        gr.update(visible=True),
        gr.update(visible=False),
        [],
        [],
        "",
        "",
    )


def create_web_app():
    """Construct and return the Gradio Blocks Search-to-Chat application.

    Does not contact Blizzard or any LLM at build time.
    """
    with gr.Blocks(title="LoreMaster Search — 8-Bit Azeroth Archive") as app:
        gr.HTML(f"<style>{EIGHTBIT_CAMPFIRE_CSS}</style>")

        chat_messages_state = gr.State([])
        llm_history_state = gr.State([])

        # ====================================================================
        # VIEW 1: Classic Search Engine Landing Page (8bitcn-ui styled)
        # ====================================================================
        with gr.Column(visible=True, elem_id="search-view-container") as search_view:
            gr.HTML(
                '<div class="eightbit-logo-box">'
                '<h1 class="eightbit-title">🔥 LOREMASTER SEARCH</h1>'
                '<p class="eightbit-subtitle">'
                "Search the official chronicles of Azeroth to begin your campfire chat"
                "</p>"
                f"{_provider_status_html()}"
                "</div>"
            )

            search_input = gr.Textbox(
                label="Search the Scrolls of Azeroth",
                placeholder="Ask about a mount, item, boss, quest, faction, or spell...",
                lines=1,
                max_lines=1,
                elem_id="search-input-box",
            )

            with gr.Row():
                search_btn = gr.Button(
                    "🔍 Search Azeroth",
                    variant="primary",
                    elem_classes=["eightbit-btn", "eightbit-btn-primary"],
                )
                lucky_btn = gr.Button(
                    "🎲 Random Lore Quest",
                    variant="secondary",
                    elem_classes=["eightbit-btn", "eightbit-btn-secondary"],
                )

            gr.HTML('<div class="eightbit-chips-heading">⚡ Popular Lore Searches</div>')

            chip_buttons = []
            for row_start in range(0, len(STARTER_QUERIES), 2):
                with gr.Row():
                    for sample_query in STARTER_QUERIES[row_start : row_start + 2]:
                        chip_btn = gr.Button(
                            sample_query,
                            elem_classes=["eightbit-chip-btn"],
                        )
                        chip_buttons.append((chip_btn, sample_query))

        # ====================================================================
        # VIEW 2: Full Chat Quest Log View (transitions in on search)
        # ====================================================================
        with gr.Column(visible=False, elem_id="chat-view-container") as chat_view:
            with gr.Row(elem_classes=["eightbit-chat-header"]):
                gr.HTML(
                    "<div>"
                    '<h2 class="eightbit-chat-header-title">🔥 LOREMASTER CAMPFIRE LOG</h2>'
                    f"{_provider_status_html()}"
                    "</div>"
                )
                new_search_btn = gr.Button(
                    "⬅ New Search",
                    elem_classes=["eightbit-btn", "eightbit-btn-secondary"],
                )

            chatbot = gr.Chatbot(
                label="Campfire Chronicle",
                height=460,
                elem_id="eightbit-chatbot",
                placeholder="The campfire crackles warmly. Ask a question to consult the ancient scrolls...",
            )

            with gr.Row():
                chat_input = gr.Textbox(
                    label="Continue Your Inquiry",
                    placeholder="Ask a follow-up question by the campfire...",
                    lines=1,
                    max_lines=3,
                    scale=4,
                    elem_id="chat-input-box",
                )
                send_btn = gr.Button(
                    "⚔️ Send",
                    variant="primary",
                    scale=1,
                    elem_classes=["eightbit-btn", "eightbit-btn-primary"],
                )

        # Wire search box Enter & Search button -> transition to chat view
        search_outputs = [
            search_view,
            chat_view,
            chatbot,
            llm_history_state,
            search_input,
            chat_input,
        ]

        search_input.submit(
            fn=start_search_chat,
            inputs=[search_input, chatbot, llm_history_state],
            outputs=search_outputs,
        )
        search_btn.click(
            fn=start_search_chat,
            inputs=[search_input, chatbot, llm_history_state],
            outputs=search_outputs,
        )
        lucky_btn.click(
            fn=start_random_lore_quest,
            inputs=[chatbot, llm_history_state],
            outputs=search_outputs,
        )

        # Wire starter query chips -> start chat directly with that query
        for chip_btn, sample_query in chip_buttons:
            chip_btn.click(
                fn=lambda msgs, hist, q=sample_query: start_search_chat(q, msgs, hist),
                inputs=[chatbot, llm_history_state],
                outputs=search_outputs,
            )

        # Wire follow-up chat input & Send button
        chat_outputs = [chatbot, llm_history_state, chat_input]
        chat_input.submit(
            fn=send_chat_message,
            inputs=[chat_input, chatbot, llm_history_state],
            outputs=chat_outputs,
        )
        send_btn.click(
            fn=send_chat_message,
            inputs=[chat_input, chatbot, llm_history_state],
            outputs=chat_outputs,
        )

        # Wire New Search button -> reset state and return to search landing view
        new_search_btn.click(
            fn=reset_to_search,
            inputs=[],
            outputs=search_outputs,
        )

        app.load(fn=None, js=EIGHTBIT_CLIENT_JS)

    return app


def launch_web(server_name="127.0.0.1", server_port=7860, share=False):
    """Validate credentials, authenticate with Blizzard, and launch the Gradio UI."""
    initialize_bot()
    app = create_web_app()
    app.launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        css=EIGHTBIT_CAMPFIRE_CSS,
    )


if __name__ == "__main__":
    launch_web()
