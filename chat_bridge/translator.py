"""
Translation Bridge — AI Translation Engine
"""

import hashlib
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache

import httpx
from openai import OpenAI, BadRequestError

from .constants import (
    OPENROUTER_BASE_URL, OPENROUTER_MODEL,
    SOURCE_LANGUAGES, TARGET_LANGUAGES, build_system_prompt,
    MAX_INPUT_CHARS, MAX_CUSTOM_RULES_CHARS,
    GAME_CONTEXT_HINTS, GAME_GLOSSARY_HINTS, TONE_HINTS, CONTEXT_SEND_MAX_EXCHANGES,
    MAX_CHAT_CONTEXT_MESSAGES, MAX_CHAT_CONTEXT_CHARS,
    MODEL_REQUEST_POLICIES, MODEL_FALLBACKS,
    TRANSLATION_CACHE_MAX_ITEMS, TRANSLATION_CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

_UNCHANGED_GAME_TOKENS = frozenset({
    "afk", "brb", "ez", "fps", "gg", "ggwp", "gl", "glhf", "idk", "ign",
    "kda", "lol", "lmao", "nt", "omw", "ping", "pog", "rip", "wp", "wtf",
})
_REFERENCE_WORDS = frozenset({
    # English
    "he", "she", "they", "it", "him", "her", "them", "this", "that",
    "those", "there", "same", "again", "also", "too",
    # Arabic
    "هو", "هي", "هم", "هذا", "هذه", "هذي", "ذاك", "ذلك", "هذولا",
    "نفس", "هناك", "أيضا", "أيضاً", "كمان", "برضو", "اللي", "الي",
    # Turkish / Spanish / French / Portuguese / German / Russian
    "bu", "şu", "orada", "aynı", "yine", "él", "ella", "eso", "esto",
    "allí", "mismo", "también", "il", "elle", "ça", "ceci", "là", "même",
    "encore", "ele", "ela", "isso", "isto", "mesmo", "er", "sie", "es",
    "das", "dies", "dort", "wieder", "auch", "он", "она", "они", "это",
    "там", "снова", "тоже",
})
_CJK_REFERENCE_MARKERS = (
    "それ", "あれ", "その", "彼", "彼女", "那个", "這個", "这个",
    "他", "她", "它", "그거", "그", "그녀",
)
_ARABIC_ATTACHED_REFERENCE = re.compile(r"(?:وين|أين|اين)(?:ه|ها|هم)?(?:\W|$)")
_NUMBER_OR_PUNCTUATION = re.compile(r"[\d\s.,:/+\-]+$")
_TRANSIENT_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_MAX_PRETOKEN_ATTEMPTS = 2
_MAX_RETRY_DELAY_SECONDS = 1.5


class _EmptyStreamError(RuntimeError):
    """A provider completed a stream without returning translation text."""


@lru_cache(maxsize=128)
def _base_prompt(source_lang: str, target_lang: str, game_mode: str, ai_tone: str) -> str:
    """Cache the static prompt portion; only chat text varies per request."""
    prompt = build_system_prompt(source_lang, target_lang)
    game_hint = GAME_CONTEXT_HINTS.get(game_mode, "")
    glossary_hint = GAME_GLOSSARY_HINTS.get(game_mode, "")
    tone_hint = TONE_HINTS.get(ai_tone, TONE_HINTS["Gamer (Default)"])
    if game_hint:
        prompt += f"\nGame context: {game_hint}"
    if glossary_hint:
        prompt += f"\nTerminology: {glossary_hint}"
    return f"{prompt}\nTone: {tone_hint}"


class Translator:
    """Handles API communication with OpenRouter for translation."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.model = OPENROUTER_MODEL
        self.client = None
        self._http = None
        self._client_lock = threading.Lock()
        self._active_requests = 0
        self._retired_http = []
        self._last_warm = 0.0
        self._cache = OrderedDict()
        self._cache_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._last_metrics = {}
        # Remember only genuine capability rejections. This is per model so a
        # fallback cannot accidentally change the selected model's policy.
        self._reasoning_rejected = set()
        if api_key:
            self._init(api_key)

    def _init(self, key: str):
        http_client = httpx.Client(
            timeout=httpx.Timeout(10.0, connect=3.0),
            # keepalive_expiry keeps the TLS connection warm between translations.
            # Default is 5s — far shorter than the gap between in-game messages,
            # so every translation used to pay a fresh handshake (~150-500ms).
            limits=httpx.Limits(
                max_connections=5,
                max_keepalive_connections=5,
                keepalive_expiry=600.0,
            ),
        )
        try:
            client = OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=key,
                http_client=http_client,
                # Retries are managed below so they are bounded, observable,
                # and can switch to the configured low-latency fallback.
                max_retries=0,
            )
        except Exception:
            http_client.close()
            raise

        close_now = []
        with self._client_lock:
            previous_http = self._http
            self.api_key = key
            self._http = http_client
            self.client = client
            self._last_warm = 0.0
            if previous_http is not None:
                if self._active_requests:
                    self._retired_http.append(previous_http)
                else:
                    close_now.append(previous_http)
        self._close_transports(close_now)
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
        close_now = []
        with self._client_lock:
            http, self._http = self._http, None
            self.client = None
            if http is not None:
                if self._active_requests:
                    self._retired_http.append(http)
                else:
                    close_now.append(http)
            if not self._active_requests and self._retired_http:
                close_now.extend(self._retired_http)
                self._retired_http.clear()
        self._close_transports(close_now)

    @staticmethod
    def _close_transports(transports):
        for http in transports:
            try:
                http.close()
            except Exception as e:
                logger.warning(f"Failed to close HTTP client: {e}")

    def _begin_request(self):
        """Pin and return one immutable client/transport/key snapshot."""
        with self._client_lock:
            if not self.api_key or self.client is None:
                return None
            self._active_requests += 1
            return self.client, self._http, self.api_key

    def _end_request(self):
        close_now = []
        with self._client_lock:
            self._active_requests = max(0, self._active_requests - 1)
            if not self._active_requests and self._retired_http:
                close_now = self._retired_http[:]
                self._retired_http.clear()
        self._close_transports(close_now)

    @staticmethod
    def _policy_for(model_slug: str) -> dict:
        """Return a copy of the request policy, including dated model aliases."""
        policy = MODEL_REQUEST_POLICIES.get(model_slug)
        if policy is None:
            for known_slug, known_policy in MODEL_REQUEST_POLICIES.items():
                if model_slug.startswith(f"{known_slug}-"):
                    policy = known_policy
                    break
        return dict(policy or {"reasoning": None, "temperature": 0.1})

    @staticmethod
    def _max_output_tokens(text: str) -> int:
        """Budget for translation expansion plus minimal mandatory reasoning."""
        # A 1,000-character CJK/Arabic message can expand substantially in the
        # target language. The previous fixed value of 80 could silently cut it.
        return max(256, min(1_536, len(text) * 2 + 64))

    def _create(self, messages, stream: bool, max_tokens: int = 160,
                model_slug: str | None = None, request_client=None):
        """Create a completion using model-specific OpenRouter capabilities."""
        request_model = model_slug or self.model
        policy = self._policy_for(request_model)
        kwargs = dict(
            model=request_model,
            messages=messages,
            max_tokens=max_tokens,
            stream=stream,
        )
        if policy.get("temperature") is not None:
            kwargs["temperature"] = policy["temperature"]
        # OpenRouter-specific knobs: route to the lowest-latency provider (cuts
        # random spikes from congested providers). Reasoning is minimal on
        # Gemini 3.1 (where it is mandatory) and disabled only where supported.
        extra = {"provider": {"sort": "latency"}}
        reasoning = policy.get("reasoning")
        if reasoning is not None and request_model not in self._reasoning_rejected:
            extra["reasoning"] = dict(reasoning)
        kwargs["extra_body"] = extra
        api_client = request_client or self.client
        try:
            return api_client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            # A provider can lag behind OpenRouter's advertised capabilities.
            # Retry once without only the rejected optional field.
            if "reasoning" in extra and "reasoning" in str(e).lower():
                logger.warning("Reasoning policy rejected for %s; retrying without it.", request_model)
                self._reasoning_rejected.add(request_model)
                extra.pop("reasoning", None)
                return api_client.chat.completions.create(**kwargs)
            raise

    def warm(self):
        """Pre-open the TCP/TLS connection with a zero-token GET.
        Called when the quick popup opens: while the user is typing, the
        handshake (~150-500ms) happens in parallel, so the actual translation
        starts on a warm connection. Costs no tokens at all."""
        resources = self._begin_request()
        if not resources:
            return
        try:
            now = time.monotonic()
            _client, http, api_key = resources
            with self._client_lock:
                # A kept-alive client is already warm. Avoid a protected API
                # request on every hotkey press while refreshing idle links.
                if self._http is http and now - self._last_warm < 300:
                    return
            if http is None:
                return
            http.get(
                f"{OPENROUTER_BASE_URL}/key",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=3.0,
            )
            with self._client_lock:
                if self._http is http:
                    self._last_warm = now
        except Exception:
            pass  # best-effort; translation works either way
        finally:
            self._end_request()

    def set_model(self, model_slug: str):
        """Switch the active OpenRouter model (slug, e.g. 'google/gemini-2.5-flash-lite')."""
        if model_slug and model_slug != self.model:
            self.model = model_slug
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

    def _publish_metrics(self, metrics: dict, callback=None):
        """Store privacy-safe timings; never include source or translated text."""
        snapshot = dict(metrics)
        with self._metrics_lock:
            self._last_metrics = snapshot
        logger.info(
            "Translation metrics: status=%s model=%s cache=%s attempts=%d "
            "ttft_ms=%s total_ms=%s input_chars=%d output_chars=%d",
            snapshot.get("status"), snapshot.get("model_used"),
            snapshot.get("cache_hit", False), snapshot.get("attempts", 0),
            snapshot.get("ttft_ms"), snapshot.get("total_ms"),
            snapshot.get("input_chars", 0), snapshot.get("output_chars", 0),
        )
        if callback:
            try:
                callback(dict(snapshot))
            except Exception:
                logger.exception("Translation metrics callback failed.")

    def get_last_metrics(self) -> dict:
        """Return the latest request measurements without message contents."""
        with self._metrics_lock:
            return dict(self._last_metrics)

    @staticmethod
    def _status_code(error) -> int | None:
        status = getattr(error, "status_code", None)
        if status is None:
            status = getattr(getattr(error, "response", None), "status_code", None)
        try:
            return int(status) if status is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_transient_error(cls, error) -> bool:
        if isinstance(error, (_EmptyStreamError, httpx.TimeoutException, httpx.NetworkError)):
            return True
        status = cls._status_code(error)
        if status in _TRANSIENT_STATUS_CODES:
            return True
        name = type(error).__name__.casefold()
        text = str(error).casefold()
        return any(marker in name or marker in text for marker in (
            "timeout", "connectionerror", "connection error", "temporarily unavailable",
        ))

    @staticmethod
    def _retry_after_seconds(error, attempt_number: int) -> float:
        """Honor Retry-After while capping pauses for a live-chat workflow."""
        headers = getattr(getattr(error, "response", None), "headers", None) or {}
        raw = headers.get("retry-after") or headers.get("Retry-After")
        delay = None
        if raw is not None:
            try:
                delay = max(0.0, float(raw))
            except (TypeError, ValueError):
                try:
                    retry_at = parsedate_to_datetime(str(raw))
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    delay = max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    delay = None
        if delay is None:
            delay = 0.15 * (2 ** max(0, attempt_number - 1))
        return min(delay, _MAX_RETRY_DELAY_SECONDS)

    @staticmethod
    def _normalize_chat_context(chat_context) -> list[str]:
        """Normalize recent OCR lines without writing images or text to disk."""
        if not chat_context:
            return []
        raw_items = chat_context.splitlines() if isinstance(chat_context, str) else list(chat_context)
        lines = []
        for item in raw_items:
            if isinstance(item, dict):
                speaker = item.get("speaker") or item.get("name") or ""
                body = item.get("text") or item.get("message") or item.get("content") or ""
                value = f"{speaker}: {body}" if speaker else str(body)
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                value = f"{item[0]}: {item[1]}"
            else:
                value = str(item)
            value = " ".join(value.split()).strip()
            if value:
                lines.append(value)

        # Keep the newest messages and enforce a total network/prompt budget.
        kept_reversed = []
        remaining = MAX_CHAT_CONTEXT_CHARS
        for line in reversed(lines[-MAX_CHAT_CONTEXT_MESSAGES:]):
            if remaining <= 0:
                break
            clipped = line[:remaining]
            if clipped:
                kept_reversed.append(clipped)
                remaining -= len(clipped)
        return list(reversed(kept_reversed))

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
        """Send recent turns only for explicit cross-message references."""
        turns = list(context or [])
        if not turns:
            return []
        normalized = text.casefold()
        words = set(re.findall(r"[^\W\d_]+", normalized, flags=re.UNICODE))
        needs_context = (
            bool(words & _REFERENCE_WORDS)
            or bool(_ARABIC_ATTACHED_REFERENCE.search(normalized))
            or any(marker in normalized for marker in _CJK_REFERENCE_MARKERS)
        )
        return turns[-CONTEXT_SEND_MAX_EXCHANGES:] if needs_context else []

    def ready(self) -> bool:
        with self._client_lock:
            return bool(self.api_key and self.client)

    def test(self) -> tuple[bool, str]:
        """Test the API connection. Returns (ok, message)."""
        resources = self._begin_request()
        if not resources:
            return False, "No API key"
        try:
            _client, http, api_key = resources
            if http is None:
                return False, "No API key"
            # Checking the key endpoint verifies authentication without buying
            # an unnecessary completion at startup or after every settings save.
            response = http.get(
                f"{OPENROUTER_BASE_URL}/key",
                headers={"Authorization": f"Bearer {api_key}"},
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
        finally:
            self._end_request()

    def stream(self, text: str, custom_rules: str = "", game_mode: str = "General",
               ai_tone: str = "Gamer (Default)",
               source_key: str = "", target_key: str = "",
               context=None, cancel=None, cache_enabled: bool = True,
               on_token=None, on_done=None, on_error=None,
               chat_context=None, on_metrics=None):
        """Stream a translation request. Callbacks are called from the caller's thread.

        context: list of (source_text, translated_text) pairs from the current game
        session, sent as prior turns so the model resolves cross-message references.
        chat_context: optional recent OCR chat lines. They are bounded, kept in
        memory only, and sent as explicitly untrusted reference data.
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
            self._publish_metrics({
                "status": "local", "request_model": self.model, "model_used": "local",
                "cache_hit": False, "attempts": 0, "ttft_ms": 0, "total_ms": 0,
                "input_chars": len(clean_text), "output_chars": len(clean_text),
                "context_turns": 0, "chat_context_messages": 0,
            }, on_metrics)
            return

        resources = self._begin_request()
        if not resources:
            if on_error:
                on_error("No API key")
            return
        request_client, _request_http, _request_api_key = resources

        try:
            rules = custom_rules.strip()
            if len(rules) > MAX_CUSTOM_RULES_CHARS:
                if on_error:
                    on_error(f"Custom rules are too long (max {MAX_CUSTOM_RULES_CHARS} characters)")
                return

            requested_model = self.model

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

            selected_context = self._select_context(clean_text, context)
            visible_chat = self._normalize_chat_context(chat_context)
            context_digest = hashlib.sha256(
                repr((selected_context, visible_chat)).encode("utf-8")
            ).digest()
            cache_key = (
                requested_model, source_key, target_key, game_mode, ai_tone,
                hashlib.sha256(rules.encode("utf-8")).digest(), context_digest, clean_text,
            )
            if cache_enabled:
                cached = self._cache_get(cache_key)
                if cached is not None:
                    if on_token:
                        on_token(cached)
                    if on_done:
                        on_done(cached)
                    self._publish_metrics({
                        "status": "ok", "request_model": requested_model,
                        "model_used": "memory-cache", "cache_hit": True,
                        "attempts": 0, "ttft_ms": 0, "total_ms": 0,
                        "input_chars": len(clean_text), "output_chars": len(cached),
                        "context_turns": len(selected_context),
                        "chat_context_messages": len(visible_chat),
                    }, on_metrics)
                    return

            # One JSON message keeps history, OCR text, preferences, and the
            # newest text in the data plane. None can become system instructions.
            task_data = {"text_to_translate": clean_text}
            if selected_context:
                task_data["prior_translation_pairs"] = [
                    {"source": str(src), "translation": str(dst)}
                    for src, dst in selected_context
                ]
            if visible_chat:
                task_data["untrusted_visible_chat_context"] = visible_chat
            if rules:
                task_data["translation_preferences"] = rules
            messages = [{"role": "system", "content": sys_prompt}]
            messages.append({
                "role": "user",
                "content": json.dumps(task_data, ensure_ascii=False, separators=(",", ":")),
            })

            started_at = time.monotonic()
            first_token_at = None
            max_tokens = self._max_output_tokens(clean_text)
            fallback = MODEL_FALLBACKS.get(requested_model)
            request_plan = [requested_model]
            if fallback and fallback != requested_model:
                request_plan.append(fallback)
            else:
                request_plan.append(requested_model)
            request_plan = request_plan[:_MAX_PRETOKEN_ATTEMPTS]

            full = ""
            model_used = requested_model
            attempts = 0
            for attempt_index, request_model in enumerate(request_plan, start=1):
                chunks = None
                emitted_content = False
                attempts = attempt_index
                model_used = request_model
                try:
                    if cancel is not None and cancel.is_set():
                        return
                    chunks = self._create(
                        messages, stream=True, max_tokens=max_tokens,
                        model_slug=request_model, request_client=request_client,
                    )
                    for c in chunks:
                        if cancel is not None and cancel.is_set():
                            try:
                                chunks.close()
                            except Exception:
                                pass
                            logger.info("Translation cancelled by user.")
                            return
                        if c.choices and c.choices[0].delta.content:
                            token = c.choices[0].delta.content
                            if first_token_at is None:
                                first_token_at = time.monotonic()
                            emitted_content = True
                            full += token
                            if on_token:
                                on_token(token)
                    if not full:
                        raise _EmptyStreamError("Provider returned an empty translation")
                    break
                except Exception as request_error:
                    if chunks is not None:
                        try:
                            chunks.close()
                        except Exception:
                            pass
                    if cancel is not None and cancel.is_set():
                        return
                    final_attempt = attempt_index >= len(request_plan)
                    # Never restart after displaying a token: doing so could
                    # duplicate a prefix in the UI and in the game chat.
                    if emitted_content or final_attempt or not self._is_transient_error(request_error):
                        raise
                    delay = self._retry_after_seconds(request_error, attempt_index)
                    logger.warning(
                        "Transient pre-token failure from %s; retrying with %s in %.2fs.",
                        request_model, request_plan[attempt_index], delay,
                    )
                    if cancel is not None:
                        if cancel.wait(delay):
                            return
                    elif delay:
                        time.sleep(delay)

            if cancel is not None and cancel.is_set():
                return

            # Clean up the result — only strip newlines, not parentheses
            result = full.strip().split("\n")[0].strip()
            # Remove wrapping quotes if present
            if len(result) >= 2 and result[0] in ('"', "'", "\u201c") and result[-1] in ('"', "'", "\u201d"):
                result = result[1:-1].strip()

            if not result:
                raise _EmptyStreamError("Provider returned an empty translation")

            completed_at = time.monotonic()
            total_ms = round((completed_at - started_at) * 1_000)
            ttft_ms = round(((first_token_at or completed_at) - started_at) * 1_000)
            if cache_enabled and result:
                self._cache_set(cache_key, result)
            if on_done:
                on_done(result)
            self._publish_metrics({
                "status": "ok", "request_model": requested_model, "model_used": model_used,
                "cache_hit": False, "attempts": attempts, "ttft_ms": ttft_ms,
                "total_ms": total_ms, "input_chars": len(clean_text),
                "output_chars": len(result), "max_tokens": max_tokens,
                "context_turns": len(selected_context),
                "chat_context_messages": len(visible_chat),
            }, on_metrics)

        except Exception as e:
            if cancel is not None and cancel.is_set():
                return  # aborting a cancelled stream can raise; stay silent
            err = str(e)
            status = self._status_code(e)
            logger.error(
                "Translation failed: type=%s status=%s",
                type(e).__name__, status,
            )
            if status == 401 or "401" in err:
                msg = "Invalid API key"
            elif status == 429 or "429" in err:
                msg = "Rate limited"
            elif isinstance(e, _EmptyStreamError):
                msg = "Empty response"
            elif isinstance(e, httpx.TimeoutException) or "timeout" in err.lower():
                msg = "Timeout"
            elif status in {500, 502, 503, 504}:
                msg = "Service unavailable"
            else:
                msg = f"Error: {err[:60]}"
            elapsed_ms = None
            if "started_at" in locals():
                elapsed_ms = round((time.monotonic() - started_at) * 1_000)
            error_ttft_ms = None
            if "first_token_at" in locals() and first_token_at is not None and "started_at" in locals():
                error_ttft_ms = round((first_token_at - started_at) * 1_000)
            self._publish_metrics({
                "status": "error", "request_model": locals().get("requested_model", self.model),
                "model_used": locals().get("model_used", locals().get("requested_model", self.model)),
                "cache_hit": False, "attempts": locals().get("attempts", 0),
                "ttft_ms": error_ttft_ms, "total_ms": elapsed_ms,
                "input_chars": len(clean_text), "output_chars": 0,
                "context_turns": len(locals().get("selected_context", [])),
                "chat_context_messages": len(locals().get("visible_chat", [])),
            }, on_metrics)
            if on_error:
                on_error(msg)
        finally:
            self._end_request()
