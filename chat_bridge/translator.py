"""
Translation Bridge — AI Translation Engine
"""

import logging
import hashlib
import re
import threading
import time
from collections import OrderedDict
from functools import lru_cache

import httpx
from openai import OpenAI, BadRequestError

from .constants import (
    OPENROUTER_BASE_URL, OPENROUTER_MODEL,
    SOURCE_LANGUAGES, TARGET_LANGUAGES, build_system_prompt,
    MAX_INPUT_CHARS, MAX_CUSTOM_RULES_CHARS,
    GAME_CONTEXT_HINTS, TONE_HINTS, CONTEXT_SEND_MAX_EXCHANGES,
    TRANSLATION_CACHE_MAX_ITEMS, TRANSLATION_CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

_UNCHANGED_GAME_TOKENS = frozenset({
    "afk", "brb", "ez", "fps", "gg", "ggwp", "gl", "glhf", "idk", "ign",
    "kda", "lol", "lmao", "nt", "omw", "ping", "pog", "rip", "wp", "wtf",
})
_REFERENCE_MARKERS = (
    " he ", " she ", " they ", " it ", " him ", " her ", " there ",
    " that ", " same ", " again ", " this ", "هو", "هي", "هم", "هذا", "هذي",
    "ذاك", "نفس", "هناك", "مرة",
)
_NUMBER_OR_PUNCTUATION = re.compile(r"[\d\s.,:/+\-]+$")


@lru_cache(maxsize=128)
def _base_prompt(source_lang: str, target_lang: str, game_mode: str, ai_tone: str) -> str:
    """Cache the static prompt portion; only chat text varies per request."""
    prompt = build_system_prompt(source_lang, target_lang)
    game_hint = GAME_CONTEXT_HINTS.get(game_mode, "")
    tone_hint = TONE_HINTS.get(ai_tone, TONE_HINTS["Gamer (Default)"])
    if game_hint:
        prompt += f"\nGame context: {game_hint}"
    return f"{prompt}\nTone: {tone_hint}"


class Translator:
    """Handles API communication with OpenRouter for translation."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.model = OPENROUTER_MODEL
        self.client = None
        self._http = None
        self._last_warm = 0.0
        self._cache = OrderedDict()
        self._cache_lock = threading.Lock()
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
        self._last_warm = 0.0
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

    def configure_api_key(self, key: str):
        """Public configuration entry point used by the UI."""
        if key and key.strip():
            self._init(key.strip())
        else:
            self.close()
            self.api_key = ""

    def close(self):
        """Release persistent HTTP resources before the application exits."""
        http, self._http = self._http, None
        self.client = None
        if http is not None:
            try:
                http.close()
            except Exception as e:
                logger.warning(f"Failed to close HTTP client: {e}")

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
        if not self.client or not self._http:
            return
        now = time.monotonic()
        # A kept-alive client is already warm. Avoid a protected API request
        # for every hotkey press while still refreshing idle connections.
        if now - self._last_warm < 300:
            return
        self._last_warm = now
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
            self.clear_cache()
            logger.info(f"Model switched to: {model_slug}")

    def clear_cache(self):
        """Forget the in-memory performance cache immediately."""
        with self._cache_lock:
            self._cache.clear()

    def _cache_get(self, key):
        now = time.monotonic()
        with self._cache_lock:
            value = self._cache.get(key)
            if value is None:
                return None
            expires_at, translation = value
            if expires_at <= now:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return translation

    def _cache_set(self, key, translation: str):
        with self._cache_lock:
            self._cache[key] = (time.monotonic() + TRANSLATION_CACHE_TTL_SECONDS, translation)
            self._cache.move_to_end(key)
            while len(self._cache) > TRANSLATION_CACHE_MAX_ITEMS:
                self._cache.popitem(last=False)

    @staticmethod
    def _is_local_passthrough(text: str, source_key: str, target_key: str) -> bool:
        """Avoid a remote request only for unambiguous no-translation input."""
        stripped = text.strip()
        normalized = stripped.casefold()
        return (
            source_key == target_key
            or normalized in _UNCHANGED_GAME_TOKENS
            or bool(_NUMBER_OR_PUNCTUATION.fullmatch(stripped))
        )

    @staticmethod
    def _select_context(text: str, context) -> list[tuple[str, str]]:
        """Send only the last two turns, and only when a reference is likely."""
        turns = list(context or [])
        if not turns:
            return []
        padded = f" {text.casefold()} "
        needs_context = len(text.strip()) <= 16 or any(marker in padded for marker in _REFERENCE_MARKERS)
        return turns[-CONTEXT_SEND_MAX_EXCHANGES:] if needs_context else []

    def ready(self) -> bool:
        return bool(self.api_key and self.client)

    def test(self) -> tuple[bool, str]:
        """Test the API connection. Returns (ok, message)."""
        if not self.ready():
            return False, "No API key"
        try:
            # Checking the key endpoint verifies authentication without buying
            # an unnecessary completion at startup or after every settings save.
            response = self._http.get(
                f"{OPENROUTER_BASE_URL}/key",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5.0,
            )
            response.raise_for_status()
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
               context=None, cancel=None, cache_enabled: bool = True,
               on_token=None, on_done=None, on_error=None):
        """Stream a translation request. Callbacks are called from the caller's thread.

        context: list of (source_text, translated_text) pairs from the current game
        session, sent as prior turns so the model resolves cross-message references.
        cancel: optional threading.Event — when set, the request is aborted and NO
        callbacks fire (the user changed their mind; nothing should be pasted).
        """
        clean_text = text.strip() if text else ""
        if not clean_text:
            if on_error:
                on_error("Empty")
            return
        if len(clean_text) > MAX_INPUT_CHARS:
            if on_error:
                on_error(f"Text is too long (max {MAX_INPUT_CHARS} characters)")
            return
        if cancel is not None and cancel.is_set():
            return

        if self._is_local_passthrough(clean_text, source_key, target_key):
            if on_token:
                on_token(clean_text)
            if on_done:
                on_done(clean_text)
            return

        if not self.ready():
            if on_error:
                on_error("No API key")
            return

        try:
            rules = custom_rules.strip()
            if len(rules) > MAX_CUSTOM_RULES_CHARS:
                if on_error:
                    on_error(f"Custom rules are too long (max {MAX_CUSTOM_RULES_CHARS} characters)")
                return

            # Build the compact static prompt — resolve source/target from keys.
            src_info = SOURCE_LANGUAGES.get(source_key)
            tgt_info = TARGET_LANGUAGES.get(target_key)
            if src_info and tgt_info:
                source_lang, target_lang = src_info[0], tgt_info
            else:
                if not src_info:
                    logger.warning("Unknown source language key; using default prompt.")
                if not tgt_info:
                    logger.warning("Unknown target language key; using default prompt.")
                source_lang, target_lang = "Arabic (Saudi/Gulf dialect)", "American English"
            sys_prompt = _base_prompt(source_lang, target_lang, game_mode, ai_tone)
            if rules:
                sys_prompt += f"\nUser preferences: {rules}"

            selected_context = self._select_context(clean_text, context)
            context_digest = hashlib.sha256(
                repr(selected_context).encode("utf-8")
            ).digest()
            cache_key = (
                self.model, source_key, target_key, game_mode, ai_tone,
                hashlib.sha256(rules.encode("utf-8")).digest(), context_digest, clean_text,
            )
            if cache_enabled:
                cached = self._cache_get(cache_key)
                if cached is not None:
                    logger.info("Translation cache hit (%d input chars).", len(clean_text))
                    if on_token:
                        on_token(cached)
                    if on_done:
                        on_done(cached)
                    return

            # Context helps with references, but six turns on every message is
            # wasted latency and token cost for ordinary independent callouts.
            messages = [{"role": "system", "content": sys_prompt}]
            for src, dst in selected_context:
                messages.append({"role": "user", "content": src})
                messages.append({"role": "assistant", "content": dst})
            messages.append({"role": "user", "content": clean_text})

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
            logger.info("Translation completed in %.2fs (%d input chars, %d output chars).",
                        elapsed, len(clean_text), len(result))

            final = result or "[Empty]"
            if cache_enabled and result:
                self._cache_set(cache_key, result)
            if on_done:
                on_done(final)

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
