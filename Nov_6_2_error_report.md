# LoreMasterBot review — 6 November 2026

LoreMasterBot is a local campfire chat that answers from Blizzard's structured Game Data and refuses to invent biographies. That boundary is implemented with real care: every Blizzard HTTP call has a 10-second timeout, blank name searches never leave the process, tool arguments that are not JSON objects are stored as strings and skipped, and a multi-tool turn is one assistant message plus one result per call. The regression suite locks a lot of that. The failures that remain sit in the chat loop's reply filter and in failure handling around tokens, caches, and model responses: a normal sentence can be replaced with "the records are silent," an auth or index failure can be remembered as "no such entity," and several bad provider or token payloads kill the process with a traceback.

No code was changed.

Baseline, before any probe: `python -m pytest -q` could not start (`python: command not found`, exit 127). The same suite with the interpreter on this machine, `python3 -m pytest -q` (Python 3.12.3), finished **188 passed**, 0 failed, in 3.51s. Nothing was failing before the probes, so there is no finding #0. Commit under review: `42fc2c3` on `main`.

## Critical

- **A normal reply that starts with "Let me", "I will", or "Since the" is thrown away, and the user is told the records are silent.**
- `src/bot.py`, `run`, the `REASONING_PREFIXES` block.
- The mechanism: after the model returns, `run` keeps any non-empty string, including a whitespace-only string. It then tests `response.lower().startswith(...)` against prefixes that include `let me`, `i will`, `since the`, `first,`, `to answer`, `i should`, and `i'm going to`. On a match it replaces the entire string with "I'm afraid the ancient scrolls are silent on that specific detail, friend..." and stores that sentence in history. The tool result from the same turn is left in history, so the lookup succeeded and the spoken answer still says it did not.
- Reproduction: with Blizzard auth and the model client mocked, `run()` was driven by scripted `input`. For user `hi` (a phrase in `CONVERSATIONAL_PHRASES`, so `tool_choice="none"`), the model returned `Let me welcome you to the campfire, friend.` Printed line:

  `Loremaster: I'm afraid the ancient scrolls are silent on that specific detail, friend. What other tale from Azeroth would you like to hear?`

  The words "campfire" did not appear anywhere in the printed output. The same replacement happened for a final answer after `search_playable_race` returned `Playable race data received: {'id': 1, 'name': 'Human', 'faction': 'Alliance'}` and the model said `I will share only the official record: Humans are an Alliance playable race.` The tool row stayed in history; the printed reply and the stored assistant message were the silence line. `Since the fire is warm, welcome, friend.` was replaced the same way. Control: `The records say Humans are of the Alliance.` was printed unchanged.
- Consequence: a greeting or a grounded lore answer is shown as a miss. The next turn's history records the miss, not the sentence the model wrote.
- Suggested fix direction: drop only a leading scratch clause when the remainder is empty, and keep any answer that already contains the tool data.

## Important

- **A Blizzard 401 is reported as "no official data," and the same dead access token is sent again until it expires.**
- `src/api/blizzard.py`, `ensure_valid_token`, `_get_entity_data`, `search_blizzard`; `src/tools/handlers.py`, `handle_lookup_item` and `_search_and_fetch`.
- The mechanism: the cached token is refreshed only when it is missing or within 60 seconds of `token_expiry`. A 401 raises from `raise_for_status`, the fetcher prints the HTTP error and returns `None`, and nothing clears `blizzard_token`. The handler then builds the `NO OFFICIAL DATA FOUND` string. The next tool call goes through `ensure_valid_token`, which still considers the token fresh, and sends `Authorization: Bearer <same token>`.
- Reproduction: `blizzard_token` was set to `TOKEN_DEADBEEF` with expiry 3600 seconds ahead, and `requests.get` returned HTTP 401. `ensure_valid_token()` returned `TOKEN_DEADBEEF` on both calls. Both item fetches sent `Bearer TOKEN_DEADBEEF` and returned `None`. `data_cache` stayed empty. Calling the real handler:

  `Error getting item data: 401 Client Error: Unauthorized for url: https://us.api.blizzard.com/data/wow/item/19019`

  `TOOL RESULT: NO OFFICIAL DATA FOUND for item ID '19019' ... You MUST tell the user that this exact entity could not be found in official records.`

  The error text did not contain the bearer token.
- Consequence: the model is ordered to tell the player the entity is absent. Every later lookup in that process repeats the 401 until the clock reaches the refresh window.
- Suggested fix direction: on 401, drop the cached token, fetch a new one once, and return an auth-failure string instead of `NO OFFICIAL DATA FOUND`.

- **One failed static-index fetch is cached as "no such name" for the rest of the process.**
- `src/api/blizzard.py`, `lookup_static_ids`.
- The mechanism: the cache key is `("index-lookup", entity_type, normalized_term)`. On a miss the code loads the index, matches names, and stores the id list even when `get_index_data` returned `None` because the HTTP call failed. `_match_index_ids(None, ...)` returns `[]`, and that empty list is stored. The next call hits `if cache_key in search_cache` and returns `[]` without a request. Playable race, class, specialization, profession, item set, journal expansion, creature family, and quest-group lookups all go through this function. `search_blizzard` does not do this: a failed name search is not written to `search_cache`.
- Reproduction: the first `GET` of `/playable-race/index` returned HTTP 500 and the second would have returned Human (id 1). `lookup_static_ids("Human", "playable-race", "tok")` returned `[]` the first time (1 network call) and `[]` the second time (still 1 network call). `search_cache[("index-lookup", "playable-race", "human")]` was `[]`. Contrast, same probe: `get_item_data(19019)` after a 500 then a 200 issued 2 requests and returned Thunderfury; `search_blizzard("Fireball", "spell")` after a connection error then a hit issued 2 requests and returned id 7.
- Consequence: a blip while loading the race, class, profession, or similar index makes that name look missing until the process restarts, and the tool result is the official not-found text.
- Suggested fix direction: write `search_cache` only after the index document has loaded.

- **A token response with a null or non-numeric `expires_in` kills the process at startup.**
- `src/bot.py`, `_authenticate_blizzard`; `src/api/blizzard.py`, `get_access_token` and `ensure_valid_token`.
- The mechanism: `json_data.get("expires_in", 3600)` supplies 3600 only when the key is absent. A present `null` or a string such as `"3600"` is returned as-is. Both callers then evaluate `time.time() + expires_in`. That `TypeError` is outside the retry `try` in `get_access_token` and outside the tool-handler `try` in `run`. A missing key, a non-200 status, a JSON list, and a JSON decode error are handled: three attempts, then `(None, None)`, and the global token stays unset.
- Reproduction: a 200 body `{"access_token": "NEWTOKEN", "expires_in": null}` made `get_access_token()` return `("NEWTOKEN", None)`. `ensure_valid_token()` raised `TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'`. Adding `"3600"` raised `TypeError: unsupported operand type(s) for +: 'float' and 'str'`. A body with no `expires_in` key returned `("NEWTOKEN", 3600)`. Driving `run()` with `get_access_token` patched to return `("NEWTOKEN", None)` printed `Authenticating with Blizzard...` and then crashed:

  `File "/workspace/src/bot.py", line 342, in _authenticate_blizzard`

  `blizzard_api.token_expiry = time.time() + expires_in`

  `TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'`

  The welcome lines are printed after that call, so they never appeared. A 500 from the token endpoint, a JSON list body, and a JSON decode error each returned `(None, None)` after 3 attempts and left `blizzard_token` unset.
- Consequence: the bot exits with a traceback instead of the "could not authenticate" line it already uses when the token is missing.
- Suggested fix direction: accept `expires_in` only when it is a positive number, and treat every other token body as a failed login that returns `(None, None)`.

- **In the minute before a token expires, a failed refresh disables lookups while the current token is still valid.**
- `src/api/blizzard.py`, `ensure_valid_token`.
- The mechanism: the refresh condition is `time.time() >= token_expiry - 60`. On a failed refresh (`token` falsy) the function prints the failure and `return None`. It does not return the `blizzard_token` it already holds. Handlers treat `None` as "API unavailable." The stored token is left in place, so the next call, still inside the window, repeats the full 3-attempt refresh.
- Reproduction: with the clock frozen, `blizzard_token` was `STILL_VALID` and `token_expiry` was 30 seconds ahead. `get_access_token` raised `ConnectionError`. `ensure_valid_token()` returned `None` after 3 posts and 2 `time.sleep` calls (the source sleeps 2 seconds). The global token was still `STILL_VALID`. A token already 5 seconds past expiry also returned `None` and was not reused. A healthy token with `expires_in` 3600 was fetched once and reused on the next call (1 post total).
- Consequence: a short outage of the token endpoint, during a window where Game Data calls would still succeed, makes every tool result say the API is unavailable, and each tool call pays for three token attempts.
- Suggested fix direction: if refresh fails and `time.time()` is still before `token_expiry`, return the current token.

- **An empty model response, a provider exception, or a tool call without a function object ends the process with a traceback.**
- `src/bot.py`, `run` and the tool-call loop.
- The mechanism: `run` has no `try` around `client.chat.completions.create` or `chat_completion.choices[0]`. `parse_tool_calls` assumes `content` is a string when it is truthy. Inside the tool loop, `tool_call.function.name` and `function_name in TOOL_HANDLERS` sit outside the handler `try`. The handler `try` does catch a handler exception and a bad JSON argument; those paths are locked by `test_tool_argument_variants_handling`, `test_malformed_tool_call_alongside_valid_tool_call`, `test_non_dict_json_arguments_produce_safe_error_without_crash`, and `test_tool_handler_exception_isolated_in_multi_call`.
- Reproduction: scripted `run()` with a mocked client.
  - `choices=[]` raised `IndexError: list index out of range` at `src/bot.py` line 409. Output did not contain `Goodbye`.
  - `choices[0].message is None` raised `AttributeError: 'NoneType' object has no attribute 'tool_calls'`.
  - `content=[{"type": "text", "text": "hi"}]` raised `TypeError: expected string or bytes-like object, got 'list'` inside `parse_tool_calls`.
  - `create` raising `RuntimeError("connection reset by ollama")` left history as `[{"role": "user", "content": "Thunderfury"}]` and exited with that traceback.
  - A tool call whose `name` was a list raised `TypeError: unhashable type: 'list'` at `if function_name in TOOL_HANDLERS`.
  - A tool call object with no `.function` raised `AttributeError: 'Bare' object has no attribute 'function'`.
  - Controls that stayed in the loop: content `""` and content `None` both printed `Loremaster: (no response)`. An unknown name `summon_archimonde` stored `Unknown tool: summon_archimonde` and still printed the final model line `I checked.`
- Consequence: one bad completion closes the chat. The player sees a Python traceback and does not get the goodbye line.
- Suggested fix direction: catch provider and parse failures around both model calls, append a short assistant error the history can trim, and keep reading input.

- **A name with leading or trailing spaces skips the exact-name check and stores the first hit under the trimmed key.**
- `src/api/blizzard.py`, `search_blizzard` and `_pick_search_id`.
- The mechanism: the September 24 change strips the term for the empty check and the cache key, which is what keeps padded famous items and blank strings off the network (`test_blank_search_term_does_not_call_blizzard`, `test_famous_item_fallback_is_case_insensitive`). The request param and the exact-name compare still use the original string. `_pick_search_id` compares `name.lower() == search_term.lower()` and otherwise returns `results[0]["data"]["id"]`. That id is saved under the stripped key, so a later unpadded search is a cache hit.
- Reproduction: `search_blizzard("  Fireball  ", "spell", "tok")` sent `name.en_US` as `  Fireball  ` (spaces intact). The mock results were id 111 `Fireball of Doom`, then id 222 `Fireball`. The function returned 111 and stored `search_cache[("spell", "fireball")] = 111`. `search_blizzard("Fireball", "spell", "tok")` returned 111 and did not send a second request. Internal spaces, apostrophes, and non-ASCII were encoded rather than breaking the URL: `Young+Nightsaber`, `Mimiron%27s+Head`, `Lich+King%E2%80%99s+Fall`, `Caf%C3%A9`. Blank and whitespace-only terms produced no URL.
- Consequence: a padded tool argument can pin the wrong entity id to the real name for the rest of the process. A later exact "Fireball" question is answered from Fireball of Doom.
- Suggested fix direction: strip the term once and use that string for the query parameter, the exact-name compare, and the cache key.

- **Pretty-printed tool JSON in message content is not executed, and the player is shown the JSON.**
- `src/bot.py`, `parse_tool_calls`.
- The mechanism: when `tool_calls` is empty, the fallback is `re.findall(r"\[.*?\]", content)`. The dot does not cross newlines, and a non-greedy match stops at the first `]`, including one inside a string. A single-line array works; `test_fallback_multiple_tool_calls_in_content` and `test_fallback_tool_calls_receive_valid_uuid_ids` lock that shape. If parsing finds nothing, `run` treats `content` as the spoken reply.
- Reproduction: `parse_tool_calls` on a pretty-printed array for `search_creature` / `Young Nightsaber` returned `[]` and left the JSON in `content`. The same call on `[{"name": "search_item_by_name", "arguments": {"search_term": "Item [Thunderfury]"}}]` returned `[]`. The single-line version of the creature call returned one tool call and cleared the JSON from `content`. Driving `run()` with the pretty-printed text as the first completion printed:

  `Loremaster: Here is the call:`

  followed by the JSON array. Handler invocations: 0. No exception.
- Consequence: a local model that emits indented tool JSON gets no Blizzard lookup, and the campfire reply is the raw tool call.
- Suggested fix direction: decode fallback tool calls with `json.JSONDecoder`, which already allows whitespace, instead of a single-line bracket search.

- **With `HTTP_PROXY` set, the default Ollama chat and a custom HTTP API key are sent to that proxy.**
- `src/bot.py`, `create_llm_client`; the OpenAI client it builds. Blizzard calls use `requests` the same way, with `trust_env` left on.
- The mechanism: neither client disables environment proxies. The default base URL is `http://localhost:11434/v1`. An HTTP request through an HTTP proxy is a forwarded request, so the proxy sees the URL, the `Authorization` header, and the JSON body. Blizzard's URLs are `https://`. Those become `CONNECT`, and the client id and secret stay inside TLS.
- Reproduction: a local proxy recorded requests while `HTTP_PROXY` and `HTTPS_PROXY` pointed at it and `NO_PROXY` was empty.
  - `requests.post("https://oauth.battle.net/token", auth=(client_id, secret))` produced one `CONNECT oauth.battle.net:443`. The client id and the secret were absent from the proxy log.
  - `OpenAI(base_url="http://llm.example.test/v1", api_key="LLMKEY_SUPERSECRET")` produced `POST http://llm.example.test/v1/chat/completions` with header `Authorization: Bearer LLMKEY_SUPERSECRET` and body `{"model":"m","messages":[{"role":"user","content":"hello lore"}]}`. The SDK error string did not contain the key.
  - `OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")` was forwarded to the same proxy as `POST http://localhost:11434/v1/chat/completions`.
  - A real `requests.Response.raise_for_status()` for a 401 whose prepared request carried Basic auth printed `401 Client Error: Unauthorized for url: https://oauth.battle.net/token` and did not contain the secret. `get_access_token` prints that same `str(exception)`.
- Consequence: a developer machine that exports `HTTP_PROXY` sends campfire prompts, and any custom HTTP `LLM_API_KEY`, to the proxy host. Blizzard client secrets were not visible on the proxy connection.
- Suggested fix direction: build the model client with environment proxies disabled for localhost, and keep the bearer token off any proxy the process did not configure on purpose.

## Minor

- **One model message can run an unlimited number of tool calls, and a second-round tool request with no text becomes "(no response)."**
- `src/bot.py`, `run`.
- The mechanism: the loop is not a `while tool_calls` loop. The first completion's tool calls are all executed, then a second completion is requested without `tools`. There is no cap and no de-duplication. If that second message has `content is None`, the empty-reply guard stores `(no response)` and does not run the new tool calls.
- Reproduction: 25 `lookup_item` calls in one completion ran the handler 25 times, stored 25 tool messages, and called `create` twice. No exception. A second completion that itself contained only a tool call called `create` twice, ran the handler once, and printed `Loremaster: (no response)`. A second completion that had both text and tool calls also stopped at 2 `create` calls, so the model cannot keep requesting tools forever.
- Consequence: a completion with a large tool list stalls the turn for one Blizzard round-trip each (up to 10 seconds each). A follow-up that is only another tool call is shown as `(no response)`.
- Suggested fix direction: cap and de-duplicate tool calls per turn, and if the follow-up message has tool calls and no text, say the lookup did not finish instead of `(no response)`.

- **A whitespace-only model reply is printed as a blank line and never closes a history turn.**
- `src/bot.py`, `run` and `trim_history`.
- The mechanism: `if not response` replaces `None` and `""` with `(no response)`. A string of spaces is truthy, so it is printed and appended. `trim_history` strips assistant text before deciding a turn has ended, which is the September 24 fix and is what stops a blank line from orphaning a later tool result. A final reply that is only whitespace therefore never ends a turn, and later user messages stay inside it until some later assistant text is non-blank.
- Reproduction: a completion whose content was `"   \n"` printed `Loremaster:    ` and stored `{"role": "assistant", "content": "   \n"}`. Three tool turns whose final assistant text was `"   "`, followed by one real answer, passed through `trim_history(..., max_turns=1)` as a single merged turn: all four user messages, all four tool results, and no orphan `tool` row (every `tool_call_id` still had a preceding assistant `tool_calls` entry). Empty content and `None` content printed `Loremaster: (no response)`.
- Consequence: the player sees a blank campfire line. While replies stay blank, the "~7 turns" cap does not drop those turns.
- Suggested fix direction: if `response.strip()` is empty, store and print `(no response)` so the turn can close; leave the strip check inside `trim_history` in place.

- **`quit` with surrounding spaces is sent to the model.**
- `src/bot.py`, `run`.
- The mechanism: the exit check is `user_prompt.lower() == "quit"`. `input` does not strip. `is_conversational_prompt` does strip, but `quit` is not one of its phrases, so the line is stored and sent with `tool_choice="required"`. `quit`, `QUIT`, and `Quit` match.
- Reproduction: a child process with auth and the model mocked, stdin ` quit\nquit\n`, printed `Loremaster: model-was-called`, then `Goodbye!`, and the model was called once (exit 0). Stdin `quit \nquit\n` did the same. Stdin `quit\n`, `QUIT\n`, and `Quit\n` each exited 0 with zero model calls and `Goodbye`.
- Consequence: ` quit` or `quit ` starts a lore turn instead of leaving.
- Suggested fix direction: compare `user_prompt.strip().lower()` with `quit`, the same normalization already used for greetings.

- **Ctrl-D and Ctrl-C leave a traceback instead of the goodbye line.**
- `src/bot.py`, `run`, the `input("You: ")` call and the first `client.chat.completions.create` call.
- The mechanism: `EOFError` and `KeyboardInterrupt` are not caught. `KeyboardInterrupt` is a `BaseException`, so the handler `except Exception` does not swallow it either. The spinner's `finally` only wraps the tool-execution section, which starts after the first model call returns.
- Reproduction: a child process whose stdin was closed at the prompt exited 1 with `EOFError: EOF when reading a line` at `src/bot.py` line 382, and stdout had no `Goodbye`. SIGINT at that prompt exited with code -2 and `KeyboardInterrupt` in the same `input` frame. SIGINT while `create` was blocked (after the line `Tell me about Thunderfury`) returned in 0.07 seconds with `KeyboardInterrupt` at `src/bot.py` line 402, and no goodbye. A 200,000-character line then `quit` exited 0, called the model once, and printed goodbye.
- Consequence: closing the terminal or pressing Ctrl-C prints a stack trace. An empty line does not crash; it is submitted as a normal turn and the following `quit` still exits.
- Suggested fix direction: catch `EOFError` and `KeyboardInterrupt` at the input and model calls and print the existing goodbye line.

- **The first model call can block for the SDK's 600-second read timeout, and that call shows no spinner.**
- `src/bot.py`, `create_llm_client` and the first `chat.completions.create` in `run`.
- The mechanism: the client is constructed with no `timeout`, so the installed OpenAI SDK default applies (`Timeout(connect=5.0, read=600, write=600, pool=600)`, openai 3.46.0). The `create` call in `run` passes `messages`, `model`, `tool_choice`, and `tools` only. `Spinner` starts after that call returns, and only when there are tool calls. Blizzard calls are separate and do time out; see Checked and clean.
- Reproduction: a client built the same way printed `Timeout(connect=5.0, read=600, write=600, pool=600)`. A `run()` whose `create` slept and was interrupted showed the kwargs `['messages', 'model', 'tool_choice', 'tools']`.
- Consequence: a stalled Ollama or custom endpoint freezes the prompt with no spinner for up to 10 minutes. Ctrl-C still interrupts it, with the traceback in the finding above.
- Suggested fix direction: pass a timeout of a few tens of seconds on both `create` calls and start the spinner before the first one.

- **Tool results sent back to the model include the whole Blizzard document, with no size cap.**
- `src/tools/handlers.py`, `_format_payloads`, `_search_and_fetch`, and `handle_search_profession`.
- The mechanism: a successful fetch is interpolated with an f-string. Profession lookup also embeds a matching skill-tier document. Nothing truncates the string. Handler exceptions do not put a traceback in that string; the loop stores `Error executing tool: <name>` (`test_tool_handler_exception_isolated_in_multi_call`). The stdout line is `Error executing tool {name}: {exception}`, which is the exception message, not a stack.
- Reproduction: `handle_search_profession({"search_term": "Blacksmithing"}, "tok")` against a mock profession document whose recipe list was 50 copies of a 1,000-character string returned a tool result of 100,540 characters containing that blob.
- Consequence: one large profession, journal, or item payload is copied into history and into the next model request in full.
- Suggested fix direction: cap the serialized tool result and keep the name, id, and a short field list when the document is larger than that cap.

- **A blank `BLIZZARD_CLIENT_ID` already in the environment hides the value in `.env`.**
- `src/config.py`, the `load_dotenv()` call and `CLIENT_ID = os.getenv("BLIZZARD_CLIENT_ID")`.
- The mechanism: `load_dotenv()` does not override variables that are already set, and an empty string counts as set. `_env_text` then strips it to empty. Ollama fills a missing `LLM_MODEL` with `llama3.1:8b`, but the Blizzard id has no such fallback, so startup takes the missing-credentials exit.
- Reproduction: a temporary `.env` containing `BLIZZARD_CLIENT_ID=fromfile` was loaded by a fresh `import src.config` in a process whose environment already had `BLIZZARD_CLIENT_ID=""`. Result: `CLIENT_ID=` empty, while `BLIZZARD_CLIENT_SECRET=fromfile` from the file was visible. The same import accepted a UTF-8 BOM, `export ` lines, CRLF, spaces around `=`, quoted values (`"abc"`, `'def'`, `"ollama"`), and an inline `# comment` on an unquoted value (the comment was stripped). A quoted value kept an internal `#`. Duplicate `LLM_PROVIDER` lines kept the last one (`gemini`). python-dotenv 1.2.4.
- Consequence: a shell that exports an empty Blizzard id makes the bot say the `.env` file is missing the id that is written in it.
- Suggested fix direction: treat a blank environment value as unset before reading `.env`, or call `load_dotenv` with an override only for blank values.

- **The regression test for a blank assistant reply still passes if the September 24 trim change is reverted.**
- `tests/test_bot_regressions.py`, `test_blank_assistant_reply_does_not_split_chat_session`.
- The mechanism: the test history is user/answer, then user `Thunderfury`, assistant `"   "`, a tool row, and a final assistant sentence, trimmed with `max_turns=1`. The slice starts at the last kept turn's user message and runs to the end of the list. Ending the turn at the whitespace assistant still starts that turn at `Thunderfury`, so the tool row stays in the slice. The assertions pass either way. A different history does change: with `max_turns=2`, turns `u1/a1`, `u2` plus a whitespace assistant, `u3/a3`. The current trim keeps `u1`. The pre-fix predicate (any truthy assistant content ends the turn) drops `u1`.
- Reproduction: both the current `trim_history` and a copy of the pre-fix predicate satisfied the test's three assertions on the committed history, and the two trimmed lists were equal. On the three-turn history above they differed: current output started at `u1`; pre-fix output started at `u2`.
- Consequence: reverting the strip in `trim_history` does not fail this test. Run-shaped histories probed separately did not produce an orphan tool row; that behavior is in Checked and clean.
- Suggested fix direction: assert a history where the pre-fix predicate drops an earlier user message and the stripped predicate keeps it.

## Simplify

No unreferenced function turned up. Every `def` under `src/` occurs again in `src/`, `tests/`, or `main.py`. The thin handler wrappers are the dispatch table `TOOL_HANDLERS` points at. Nothing unused to delete.

## Leave alone

- **Answers stay inside Blizzard's structured Game Data, including the refusal to write biographies.** `SYSTEM_PROMPT`, the creature-tool description, and `test_system_prompt_forbids_biography_from_memory` / `test_search_creature_is_not_a_lore_biography_tool` are the product. A fixer should not "fill in" Arthas from model memory.
- **Ollama is the default, with a dummy API key.** `LLM_PROVIDER` defaults to `ollama`, the model default is `llama3.1:8b`, and `OLLAMA_API_KEY` is the literal `ollama` because the client constructor rejects an empty key. Missing Gemini or custom settings exit only when that provider is selected (`test_missing_gemini_key_fails_only_when_gemini_selected`, `test_ollama_does_not_require_gemini_or_custom_keys`).
- **`tool_choice="required"` on lore lines and `"none"` on the exact greeting list.** Short names such as Invincible stay on the tool path (`test_short_wow_prompts_classified_as_not_conversational`). Widening the greeting list would bring back memory answers.
- **One tool round per user line.** The second model call omits `tools` so the spoken reply is supposed to come from the rows just fetched. The missing cap, and the `(no response)` fallback when that second message is tool-calls only, are the bugs above. Turning this into an open-ended tool loop is a different design.
- **Permanent in-process cache for successful static documents, and the 60-second WoW Token TTL.** `data_cache` has no expiry because item and creature documents are static; the token price is the exception and is covered by `test_wow_token_cache_hit_before_ttl_expiration` and `test_wow_token_clock_skew_backwards_refetches`. Caching a *failed* index lookup is the separate bug above. Region, locale, and namespace are fixed to `us` / `en_US` / `static-us`, so they do not collide; there is no second region in the client.
- **Refreshing a token 60 seconds early when the refresh succeeds.** That part is sound. Only the failure branch, which discards a token that has not expired yet, needs to change.
- **The famous-item id map.** Case-insensitive, padded names resolve without a request (`test_famous_item_fallback_is_case_insensitive`). It is a deliberate workaround for search misses, not dead data.
- **`trim_history` refusing to end a turn on whitespace.** That is the September 24 orphan fix. Keep it. The bug to fix is `run` storing a whitespace final reply in the first place.
- **US-only Game Data URLs and the in-character system prompt.** Both are product choices. The prompt text is what stops the model from padding sparse tool results.

## Checked and clean

- **Baseline suite.** `python3 -m pytest -q`: 188 passed, 0 failed, 3.51s. `python -m pytest -q` is what CI and the README run; on this machine `python` is not installed (exit 127), and `python3` is 3.12.3. CI (`.github/workflows/ci.yml`) installs Python 3.11 and runs `python -m pytest -q` after `pip install -r requirements-dev.txt`. README's test command matches CI. Bare `pytest -q` from a PATH that contains the pytest script fails collection with `ModuleNotFoundError: No module named 'src'` in all five test modules. `BUILD-LOG.md` already records that, and the README's `python -m pytest -q` is the command that works. Model name `llama3.1:8b` matches `DEFAULT_OLLAMA_MODEL`, `.env.example`, and the README. No test function under `tests/` lacks an `assert` (AST walk). `evals/cases.json` has five cases; `search_mount_by_name`, `search_item_by_name`, `search_journal_encounter`, `search_playable_race`, and `none` all match the current schema. Schema names and `TOOL_HANDLERS` are the same set with no duplicates (`test_new_and_existing_tool_names_are_registered` agrees).
- **September 24 blank-search fix, every entry point.** `search_blizzard` rejects `""`, `"   "`, `"\t\n"`, `None`, and a non-string (`test_blank_search_term_does_not_call_blizzard`). `lookup_static_ids` rejects `""` and `None` (`test_empty_search_term_does_not_hit_network`). A direct call of every handler in `TOOL_HANDLERS` with `{}`, `""`, `"   "`, `None`, and a non-string `search_term` made no Game Data request, except `get_wow_token_price`, which ignores arguments and fetches the price on purpose. New handlers also return not-found for non-dict args (`test_handlers_malformed_or_empty_arguments`).
- **History trimming on the shapes `run` actually writes.** Eight full multi-tool turns plus a trailing user / assistant-tool-call / tool row, trimmed to 7 turns, kept that unfinished tool group, started on a user message, and had no tool row whose id was missing from a preceding assistant `tool_calls`. Whitespace final replies merged turns and still did not orphan tool ids. Multiple tool calls in one turn stay one assistant message (`test_multiple_tool_calls_stored_in_single_assistant_message`). Fallback ids are `call_` plus 32 hex digits (`test_fallback_tool_calls_receive_valid_uuid_ids`).
- **Malformed tool arguments and unknown tool names that are strings.** Invalid JSON, `None`, a JSON list, and a JSON number become `Error parsing tool arguments.` and the turn finishes (tests named above). `summon_archimonde` becomes `Unknown tool: summon_archimonde` and the final reply is still printed.
- **Empty model content.** `""` and `None` with no tool calls print `Loremaster: (no response)` and the loop continues.
- **Blizzard timeouts, retries, and error caching.** Every `requests.get` / `requests.post` in `src/api/blizzard.py` passes `timeout=BLIZZARD_API_TIMEOUT` (10). A socket that accepted and never answered made `get_item_data` return `None` in 10.0 seconds. A persistent HTTP 500 on spell search, item fetch, and the WoW Token price stopped after 3 GETs total, one each, with no further loop. OAuth 500, a JSON list body, and a JSON decode error each stop after 3 attempts and do not store a token (`test_oauth_timeout_retries_and_fails_safely` locks the timeout retry). A failed item fetch is not cached: 500 then 200 took two requests. A failed `search_blizzard` is not cached either. An already-expired token is not returned when refresh fails. A good token is reused before the 60-second window (one OAuth post for two lookups).
- **Item id handling from the chat path.** Non-numeric `item_id` never calls the API (`test_lookup_item_rejects_non_numeric_item_name`). Int `19019` and str `"19019"` share a cache entry (`test_get_item_data_cache_hit_between_int_and_string_id`).
- **Provider startup.** Missing Gemini key, missing custom URL/key/model, and an unknown provider exit 1 with a message and no traceback (`test_missing_gemini_key_run_exits_before_blizzard`, `test_unknown_provider_subprocess_exits_cleanly`, `test_gemini_startup_subprocess_exits_cleanly_without_key`). Missing Blizzard credentials do the same (`test_missing_credentials_empty_env_exits_cleanly`). Importing `src.bot` does not authenticate (`test_importing_bot_does_not_exit_or_authenticate_when_credentials_missing`).
- **Secrets in error text.** `raise_for_status` on a 401 whose request used HTTP Basic auth stringifies to the URL only. The token-refresh printer emitted that line and not the client secret. The 401 item-fetch printer emitted the item URL and not the bearer token. Tool results for a handler crash are the fixed string `Error executing tool: <name>`, not a traceback.
- **`.env` shapes that load correctly.** BOM, `export`, CRLF, blank lines, spaces around `=`, quotes, and unquoted inline comments all reached `src.config` with the expected values. Quoted `#` stayed inside the value. The last duplicate key wins, which is the parser's normal rule.
- **Directory proof for things that are present.** Repo root contains `main.py`, `README.md`, `BUILD-LOG.md`, `.env.example`, `requirements.txt`, `requirements-dev.txt`, `src/` (`bot.py`, `config.py`, `api/blizzard.py`, `tools/schemas.py`, `tools/handlers.py`), `tests/` (five test modules plus `conftest.py`), `evals/cases.json`, and `.github/workflows/ci.yml`. No `pytest.ini` or `pyproject.toml`. There is no `.env` in the tree (`.gitignore` lists it). No claim in this report depends on a file that was not listed here or opened.
