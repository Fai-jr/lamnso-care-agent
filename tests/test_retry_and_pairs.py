from backend.app.memory import SessionMemory
from backend.app.nightshift import LLMResult, NightshiftError
from backend.app.pipeline import SIMPLIFY_PROMPT, SYSTEM_PROMPT, handle_message

LOOP = "a b c a b c a b c d e f"


class SeqLLM:
    """Returns the given replies in order; records every request."""
    def __init__(self, *texts, fail_on=None):
        self.texts, self.requests, self.fail_on = list(texts), [], fail_on

    def chat(self, messages, **kw):
        self.requests.append(messages)
        if self.fail_on == len(self.requests):
            raise NightshiftError("down")
        return LLMResult(self.texts[min(len(self.requests), len(self.texts)) - 1], f"model-{len(self.requests)}", "r", 1)


class Fussy:
    """Translates only sentences that contain no apostrophe."""
    def translate(self, t):
        return "" if "'" in t else f"LN[{t}]"


def run(llm, translator=Fussy()):
    return handle_message("I am tired", "s", llm=llm, translator=translator, memory=SessionMemory(), resources=[])


def test_prompt_asks_for_plain_short_sentences_without_contractions():
    assert "contractions" in SYSTEM_PROMPT and "idioms" in SYSTEM_PROMPT and "under 9 words" in SYSTEM_PROMPT


def test_pairs_are_returned_alongside_the_reply():
    out = run(SeqLLM("I am here. You are not alone."))
    assert out["translation_ok"] is True and len(out["sentences"]) == 2
    assert out["sentences"][0] == {"english": "I am here.", "lamnso": "LN[I am here.]"}


def test_retry_with_a_simpler_reply_recovers_the_translation():
    llm = SeqLLM("I hear you're having a hard day. It's okay.", "I hear you. It is okay.")
    out = run(llm)
    assert len(llm.requests) == 2
    assert llm.requests[1][-1] == {"role": "user", "content": SIMPLIFY_PROMPT}
    assert out["translation_ok"] is True and out["reply_english"] == "I hear you. It is okay."
    assert out["model_used"] == "model-2" and any(t.startswith("retry:simplified -> translate:ok") for t in out["trace"])


def test_failed_retry_keeps_the_original_english_and_still_shows_pairs():
    llm = SeqLLM("I hear you're tired. Rest now.", "It's still bad. Sorry.")
    out = run(llm)
    assert out["translation_ok"] is False and out["reply_lamnso"] is None
    assert out["reply_english"] == "I hear you're tired. Rest now."
    assert out["sentences"][0]["lamnso"] is None and out["sentences"][1]["lamnso"] == "LN[Rest now.]"


def test_retry_that_errors_is_harmless():
    out = run(SeqLLM("I hear you're tired.", fail_on=2))
    assert out["route"] == "agent" and out["reply_lamnso"] is None and out["reply_english"]


def test_no_retry_when_the_first_translation_works_or_there_is_no_translator():
    llm = SeqLLM("I am here.")
    run(llm)
    assert len(llm.requests) == 1
    llm2 = SeqLLM("I am here.")
    run(llm2, translator=None)
    assert len(llm2.requests) == 1
