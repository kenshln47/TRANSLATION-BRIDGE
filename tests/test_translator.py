import unittest
from types import SimpleNamespace

from chat_bridge.constants import (
    DEFAULT_SOURCE,
    DEFAULT_TARGET,
    MAX_CUSTOM_RULES_CHARS,
    MAX_INPUT_CHARS,
    build_system_prompt,
)
from chat_bridge.translator import Translator


class TranslatorSafetyTests(unittest.TestCase):
    @staticmethod
    def _translator_with_fake_response(response="translated"):
        translator = Translator()
        translator.api_key = "test"
        translator.client = object()
        calls = []

        def fake_create(messages, stream, max_tokens=80):
            calls.append(messages)
            return [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=response))]
                )
            ]

        translator._create = fake_create
        return translator, calls

    def test_rejects_oversized_text_before_network_access(self):
        errors = []
        Translator().stream("x" * (MAX_INPUT_CHARS + 1), on_error=errors.append)
        self.assertEqual(errors, [f"Text is too long (max {MAX_INPUT_CHARS} characters)"])

    def test_rejects_oversized_custom_rules_before_request(self):
        errors = []
        translator = Translator()
        # No network client is needed: the guard runs before completion creation.
        translator.api_key = "test"
        translator.client = object()
        translator.stream(
            "hello",
            custom_rules="x" * (MAX_CUSTOM_RULES_CHARS + 1),
            source_key=DEFAULT_SOURCE,
            target_key=DEFAULT_TARGET,
            on_error=errors.append,
        )
        self.assertEqual(
            errors,
            [f"Custom rules are too long (max {MAX_CUSTOM_RULES_CHARS} characters)"],
        )

    def test_compact_prompt_keeps_language_specific_hint(self):
        prompt = build_system_prompt("Arabic (Saudi/Gulf dialect)", "American English")
        self.assertLess(len(prompt), 1_000)
        self.assertIn("Gulf Arabic", prompt)
        self.assertIn("only one-line translation", prompt)

    def test_short_reference_gets_only_two_recent_turns(self):
        context = [("one", "1"), ("two", "2"), ("three", "3")]
        self.assertEqual(Translator._select_context("who is he?", context), context[-2:])
        self.assertEqual(
            Translator._select_context("rotate to the other site after you finish buying", context),
            [],
        )

    def test_common_game_token_returns_without_network(self):
        completed = []
        translator = Translator()
        translator.stream("GG", on_done=completed.append)
        self.assertEqual(completed, ["GG"])

    def test_repeated_request_uses_memory_cache(self):
        translator, calls = self._translator_with_fake_response()
        completed = []
        kwargs = {
            "source_key": DEFAULT_SOURCE,
            "target_key": DEFAULT_TARGET,
            "on_done": completed.append,
        }
        translator.stream("وينه؟", **kwargs)
        translator.stream("وينه؟", **kwargs)
        self.assertEqual(completed, ["translated", "translated"])
        self.assertEqual(len(calls), 1)

    def test_disabling_cache_keeps_requests_independent(self):
        translator, calls = self._translator_with_fake_response()
        kwargs = {
            "source_key": DEFAULT_SOURCE,
            "target_key": DEFAULT_TARGET,
            "cache_enabled": False,
        }
        translator.stream("وينه؟", **kwargs)
        translator.stream("وينه؟", **kwargs)
        self.assertEqual(len(calls), 2)

    def test_cache_does_not_cross_continuations_with_different_context(self):
        translator, calls = self._translator_with_fake_response()
        kwargs = {
            "source_key": DEFAULT_SOURCE,
            "target_key": DEFAULT_TARGET,
        }
        translator.stream("هو وين؟", context=[("عدوي", "my enemy")], **kwargs)
        translator.stream("هو وين؟", context=[("صاحبي", "my friend")], **kwargs)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
