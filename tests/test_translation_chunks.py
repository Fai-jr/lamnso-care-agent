from backend.app.memory import SessionMemory
from backend.app.pipeline import handle_message, looks_degenerate, split_sentences, translate_reply

# the real looping output produced by the model on a 3-sentence English reply
LOOP = ("Vèn yén ri kinyo ke kí dzə̀ á? Vèn dzə̀ á yiì a dzə̀ kinyo ke ru kí, a dzə̀ á wàa koóy mo á? "
        "Vèn kù dzə̀ kíwun ke m suuy ki dzə̀ á? Vèn kù dzə̀ kíwun ke ru kí, a dzə̀ á wàa ghan e vèn kí. "
        "Vèn kù dzə̀ kinyo ke ru kí, a dzə̀ kíwun ke m suuy ki dzə̀ á?")
GOOD = ["M dzə̀ kém,", "M kì kwaʼtì ji m wáa dzə.", "À dzə̀ wír, a bó à yòʼ kér vifií.",
        "M yíi a dzə moo ŋgáŋàŋ, e kfə̀n a dzə sho.", "M dzə̀ʼə̀m, a m dzə̀ e věn mvəm."]


class Echo:
    def __init__(self, fn=None):
        self.calls, self.fn = [], fn

    def translate(self, t):
        self.calls.append(t)
        return self.fn(t) if self.fn else f"LN({t})"


def test_split_sentences():
    assert split_sentences("I hear you. That sounds hard!  Want to talk?") == [
        "I hear you.", "That sounds hard!", "Want to talk?"]
    assert split_sentences("No punctuation here") == ["No punctuation here"]
    assert split_sentences("   ") == []


def test_degenerate_detection_on_real_outputs():
    assert looks_degenerate(LOOP)
    assert not any(looks_degenerate(g) for g in GOOD)
    assert not looks_degenerate("")
    assert looks_degenerate("a b c a b c a b c d")  # same three-word run three times


def test_translates_one_sentence_per_call_and_joins():
    t = Echo()
    out, trace = translate_reply(t, "I hear you. That sounds hard.")
    assert t.calls == ["I hear you.", "That sounds hard."]
    assert out == "LN(I hear you.) LN(That sounds hard.)" and "2/2" in trace


def test_one_bad_sentence_withholds_all_lamnso():
    t = Echo(lambda s: "" if "hard" in s else "ok ok fine")
    out, trace = translate_reply(t, "I hear you. That sounds hard.")
    assert out is None and "withheld (1/2" in trace


def test_looping_sentence_is_withheld():
    out, trace = translate_reply(Echo(lambda s: LOOP), "I am here.")
    assert out is None and "withheld" in trace


def test_translator_exception_is_contained():
    def boom(s):
        raise RuntimeError("x")
    out, trace = translate_reply(Echo(boom), "Hello there.")
    assert out is None and "withheld" in trace


def test_no_translator_and_empty_input():
    assert translate_reply(None, "Hi.") == (None, "translate:unavailable")
    assert translate_reply(Echo(), "  ")[0] is None


def test_pipeline_still_returns_english_when_lamnso_is_withheld():
    class LLM:
        def chat(self, messages, **kw):
            from backend.app.nightshift import LLMResult
            return LLMResult("I am sorry. Rest a little.", "m", "m", 1)
    out = handle_message("I am tired", "s", llm=LLM(), translator=Echo(lambda s: LOOP),
                         memory=SessionMemory(), resources=[])
    assert out["route"] == "agent" and out["reply_english"] == "I am sorry. Rest a little."
    assert out["reply_lamnso"] is None and out["translation_ok"] is False
