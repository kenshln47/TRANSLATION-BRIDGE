"""
Translation Bridge — AI Translation Engine
"""

import logging
import time

import httpx
from openai import OpenAI, BadRequestError

from .constants import (
    OPENROUTER_BASE_URL, OPENROUTER_MODEL,
    SYSTEM_PROMPT, GAME_PRESETS, TONE_PRESETS,
    SOURCE_LANGUAGES, TARGET_LANGUAGES, build_system_prompt,
)

logger = logging.getLogger(__name__)


class Translator:
    """Handles API communication with OpenRouter for translation."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.model = OPENROUTER_MODEL
        self.client = None
        self._http = None
        # Some models "think" before answering by default, adding seconds of
        # latency, so we ask OpenRouter to turn reasoning off. If a provider
        # rejects the param (400), this flips to False and we retry without it.
        # Instance-level and reset on model switch, so one provider's quirk
        # can't permanently disable the optimization process-wide.
        self._reasoning_ok = True
        if api_key:
            self._init(api_key)

    def _init(self, key: str):
        self.api_key = key
        # Re-initialization (e.g. saving a new key in Settings) must not leak
        # the previous client's keepalive TLS connections.
        if self._http is not None:
            try:
                self._http.close()
            except Exception:
                pass
        self._reasoning_ok = True
        self._http = http_client = httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            # keepalive_expiry keeps the TLS connection warm between translations.
            # Default is 5s — far shorter than the gap between in-game messages,
            # so every translation used to pay a fresh handshake (~150-500ms).
            limits=httpx.Limits(
                max_connections=5,
                max_keepalive_connections=5,
                keepalive_expiry=600.0,
            ),
        )
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=key,
            http_client=http_client,
        )
        logger.info(f"Translator initialized with model: {self.model}")

    def _create(self, messages, stream: bool, max_tokens: int = 80):
        """Create a completion, disabling model reasoning for low latency."""
        kwargs = dict(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1,
            stream=stream,
        )
        # OpenRouter-specific knobs: route to the lowest-latency provider (cuts
        # the random 5-9s spikes from congested providers) and disable
        # chain-of-thought reasoning for instant short replies.
        extra = {"provider": {"sort": "latency"}}
        if self._reasoning_ok:
            extra["reasoning"] = {"enabled": False}
        kwargs["extra_body"] = extra
        try:
            return self.client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            # Only a 400 mentioning the reasoning param means the provider
            # mandates reasoning — anything else (429s, quota errors that
            # happen to contain the word) must not disable the optimization.
            if self._reasoning_ok and "reasoning" in str(e).lower():
                logger.warning("Reasoning-off param rejected; retrying without it.")
                self._reasoning_ok = False
                extra.pop("reasoning", None)
                return self.client.chat.completions.create(**kwargs)
            raise

    def warm(self):
        """Pre-open the TCP/TLS connection with a zero-token GET.
        Called when the quick popup opens: while the user is typing, the
        handshake (~150-500ms) happens in parallel, so the actual translation
        starts on a warm connection. Costs no tokens at all."""
        if not self.client:
            return
        try:
            self._http.get(
                f"{OPENROUTER_BASE_URL}/key",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=3.0,
            )
        except Exception:
            pass  # best-effort; translation works either way

    def set_model(self, model_slug: str):
        """Switch the active OpenRouter model (slug, e.g. 'google/gemini-2.5-flash-lite')."""
        if model_slug and model_slug != self.model:
            self.model = model_slug
            # A different provider may have different reasoning support; re-allow.
            self._reasoning_ok = True
            logger.info(f"Model switched to: {model_slug}")

    def ready(self) -> bool:
        return bool(self.api_key and self.client)

    def test(self) -> tuple[bool, str]:
        """Test the API connection. Returns (ok, message)."""
        if not self.ready():
            return False, "No API key"
        try:
            self._create([{"role": "user", "content": "Say OK"}], stream=False, max_tokens=3)
            logger.info("API connection test: OK")
            return True, "Connected"
        except Exception as e:
            err = str(e)
            logger.warning(f"API connection test failed: {err[:100]}")
            if "401" in err:
                return False, "Invalid API key"
            if "timeout" in err.lower():
                return False, "Timeout"
            return False, f"Error: {err[:60]}"

    def stream(self, text: str, custom_rules: str = "", game_mode: str = "General",
               ai_tone: str = "Gamer (Default)",
               source_key: str = "", target_key: str = "",
               context=None, cancel=None,
               on_token=None, on_done=None, on_error=None):
        """Stream a translation request. Callbacks are called from the caller's thread.

        context: list of (source_text, translated_text) pairs from the current game
        session, sent as prior turns so the model resolves cross-message references.
        cancel: optional threading.Event — when set, the request is aborted and NO
        callbacks fire (the user changed their mind; nothing should be pasted).
        """
        if not text or not text.strip():
            if on_error:
                on_error("Empty")
            return
        if not self.ready():
            if on_error:
                on_error("No API key")
            return
        if cancel is not None and cancel.is_set():
            return

        try:
            # Build system prompt — resolve source/target from keys
            src_info = SOURCE_LANGUAGES.get(source_key)
            tgt_info = TARGET_LANGUAGES.get(target_key)
            if src_info and tgt_info:
                sys_prompt = build_system_prompt(src_info[0], tgt_info)
            else:
                if not src_info:
                    logger.warning("Unknown source language key: '%s', using default prompt.", source_key)
                if not tgt_info:
                    logger.warning("Unknown target language key: '%s', using default prompt.", target_key)
                sys_prompt = SYSTEM_PROMPT

            game_addition = GAME_PRESETS.get(game_mode, "")
            if game_addition:
                sys_prompt += game_addition

            tone_addition = TONE_PRESETS.get(ai_tone, TONE_PRESETS["Gamer (Default)"])
            sys_prompt += tone_addition

            if custom_rules and custom_rules.strip():
                sys_prompt += f"\n\nUSER CUSTOM RULES (OVERRIDE ALL OTHERS):\n{custom_rules.strip()}"

            # Prior turns from this game session (cheap input tokens, big quality win)
            messages = [{"role": "system", "content": sys_prompt}]
            for src, dst in (context or []):
                messages.append({"role": "user", "content": src})
                messages.append({"role": "assistant", "content": dst})
            messages.append({"role": "user", "content": text.strip()})

            t0 = time.time()
            chunks = self._create(messages, stream=True)

            full = ""
            for c in chunks:
                if cancel is not None and cancel.is_set():
                    try:
                        chunks.close()  # abort the HTTP stream, stop paying for tokens
                    except Exception:
                        pass
                    logger.info("Translation cancelled by user.")
                    return
                if c.choices and c.choices[0].delta.content:
                    t = c.choices[0].delta.content
                    full += t
                    if on_token:
                        on_token(t)

            if cancel is not None and cancel.is_set():
                return

            # Clean up the result — only strip newlines, not parentheses
            result = full.strip().split("\n")[0].strip()
            # Remove wrapping quotes if present
            if len(result) >= 2 and result[0] in ('"', "'", "\u201c") and result[-1] in ('"', "'", "\u201d"):
                result = result[1:-1].strip()

            elapsed = time.time() - t0
            logger.info(f"Translation completed in {elapsed:.2f}s: '{text[:30]}...' -> '{result[:30]}...'")

            if on_done:
                on_done(result or "[Empty]")

        except Exception as e:
            if cancel is not None and cancel.is_set():
                return  # aborting a cancelled stream can raise; stay silent
            err = str(e)
            logger.error(f"Translation failed: {err[:100]}")
            if "401" in err:
                msg = "Invalid API key"
            elif "429" in err:
                msg = "Rate limited"
            elif "timeout" in err.lower():
                msg = "Timeout"
            else:
                msg = f"Error: {err[:60]}"
            if on_error:
                on_error(msg)
