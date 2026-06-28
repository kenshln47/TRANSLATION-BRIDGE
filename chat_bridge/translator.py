"""
Translation Bridge — AI Translation Engine
"""

import logging
import time

import httpx
from openai import OpenAI

from .constants import (
    OPENROUTER_BASE_URL, OPENROUTER_MODEL,
    SYSTEM_PROMPT, GAME_PRESETS, TONE_PRESETS,
    SOURCE_LANGUAGES, TARGET_LANGUAGES, build_system_prompt,
)

logger = logging.getLogger(__name__)


class Translator:
    """Handles API communication with OpenRouter for translation."""

    # grok-4.1-fast "thinks" before answering by default, which adds seconds of
    # latency. We ask OpenRouter to turn reasoning off for instant short replies.
    # If a provider ever rejects the param, this flips to False and we retry plain.
    _reasoning_ok = True

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.model = OPENROUTER_MODEL
        self.client = None
        if api_key:
            self._init(api_key)

    def _init(self, key: str):
        self.api_key = key
        http_client = httpx.Client(
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

    def _create(self, messages, stream: bool):
        """Create a completion, disabling model reasoning for low latency."""
        kwargs = dict(
            model=self.model,
            messages=messages,
            max_tokens=80,
            temperature=0.1,
            stream=stream,
        )
        if Translator._reasoning_ok:
            # OpenRouter-specific: turn off chain-of-thought for speed.
            kwargs["extra_body"] = {"reasoning": {"enabled": False}}
        try:
            return self.client.chat.completions.create(**kwargs)
        except Exception as e:
            # Some providers mandate reasoning and 400 on enabled:false — retry once.
            if Translator._reasoning_ok and "reasoning" in str(e).lower():
                logger.warning("Reasoning-off param rejected; retrying without it.")
                Translator._reasoning_ok = False
                kwargs.pop("extra_body", None)
                return self.client.chat.completions.create(**kwargs)
            raise

    def set_model(self, model_slug: str):
        """Switch the active OpenRouter model (slug, e.g. 'x-ai/grok-4.1-fast')."""
        if model_slug and model_slug != self.model:
            self.model = model_slug
            # A different provider may have different reasoning support; re-allow.
            Translator._reasoning_ok = True
            logger.info(f"Model switched to: {model_slug}")

    def ready(self) -> bool:
        return bool(self.api_key and self.client)

    def test(self) -> tuple[bool, str]:
        """Test the API connection. Returns (ok, message)."""
        if not self.ready():
            return False, "No API key"
        try:
            self._create([{"role": "user", "content": "Say OK"}], stream=False)
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
               on_token=None, on_done=None, on_error=None):
        """Stream a translation request. Callbacks are called from the caller's thread."""
        if not text or not text.strip():
            if on_error:
                on_error("Empty")
            return
        if not self.ready():
            if on_error:
                on_error("No API key")
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

            t0 = time.time()
            chunks = self._create(
                [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": text.strip()},
                ],
                stream=True,
            )

            full = ""
            for c in chunks:
                if c.choices and c.choices[0].delta.content:
                    t = c.choices[0].delta.content
                    full += t
                    if on_token:
                        on_token(t)

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
