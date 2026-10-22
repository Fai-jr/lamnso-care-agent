"""
crisis_safety.py

Safety-net crisis detection for the Lamnso mental health chatbot.

WHY THIS EXISTS:
The translation model and Rasa NLU classifier can both fail on short,
high-stakes input (e.g. "i want to die" translated to an empty string
and was then misclassified as `deny`). This module is a deliberately
"dumb" keyword/pattern scanner that runs on the RAW user text, before
translation and before NLU, so crisis detection never depends on either
of those components working correctly.

This is NOT meant to replace Rasa's NLU-based `express_crisis` intent.
It is a redundant failsafe: when in doubt, treat as crisis. False
positives here are an acceptable cost; false negatives are not.
"""

import re
import unicodedata


# ---------------------------------------------------------------------------
# ENGLISH crisis patterns
# Deliberately broad. Word-boundary regex so "die" alone doesn't match things
# like "diesel", but phrases are matched loosely (extra words in between are
# tolerated where it's safe to do so).
# ---------------------------------------------------------------------------
CRISIS_PATTERNS_EN = [
    r"\bwant(ed)? to die\b",
    r"\bwish(ed)? (i|to) (was|were|be) dead\b",
    r"\bkill(ing)? myself\b",
    r"\b(please|just)\s+kill me\b",
    r"\bsomeone (should |needs to )?kill me\b",
    r"\bi want (you |someone )?to kill me\b",
    r"\bwish(ed)? (someone|somebody) would kill me\b",
    r"\bsuicid\w*\b",
    r"\bend(ing)? my (own )?life\b",
    r"\bend(ing)? it all\b",
    r"\bno reason to live\b",
    r"\bbetter off dead\b",
    r"\bdon'?t want to (live|be alive)\b",
    r"\bcan'?t (go on|do this anymore|take (it|this) anymore|keep (living|going)( like this)?|live like this|continue like this)\b",
    r"\bno point (in )?(living|continuing|going on)\b",
    r"\bgiv(e|ing) up on (life|everything|myself)\b",
    r"\bfeel like giving up\b",
    r"\btake my (own )?life\b",
    r"\bhurt myself\b",
    r"\bharm myself\b",
    r"\bself[\s-]?harm\b",
    r"\bcutting myself\b",
    r"\bi('m| am)? ?done with (life|living|everything)\b",
    r"\bi want to disappear\b",
    r"\blife (is|isn'?t) worth (living|it)\b",
    r"\bplanning to die\b",
    r"\bnot worth living\b",
]

# ---------------------------------------------------------------------------
# LAMNSO crisis patterns
# Built directly from your express_crisis intent's 13 training examples
# in nlu.yml — NOT hand-guessed. Each phrase below was mined as an n-gram
# that is UNIQUE to express_crisis: it does not appear anywhere in your
# greet/affirm/deny/anxiety/depression/schizophrenia/hopelessness/grief/
# request_help/referral/gratitude/out_of_scope examples.
#
# This matters because words like "kpú"/"kpu" (die/death) also show up in
# express_grief, express_depression, express_schizophrenia_symptoms, and
# express_hopelessness in non-crisis ways (mourning, severity idioms,
# symptom descriptions). Matching on the bare word would have caused this
# safety net to override perfectly appropriate grief/depression responses
# with the crisis message — so only verified crisis-unique multi-word
# spans are used here, checked against every other intent before inclusion.
#
# IMPORTANT: this was built by a tool that does not understand Lamnso —
# it only checked for text overlap across your training data. A fluent
# Lamnso speaker should sanity-check that these phrases really do carry
# crisis/suicidal meaning before this is trusted in production. As substring
# matches, each will also catch the phrase if it appears embedded in a
# longer sentence, not just verbatim.
#
# This is deliberately narrower in scope than the English list: it is a
# secondary safety net for Lamnso input (which already goes straight to
# Rasa's NLU, tested at 100% intent accuracy), not the primary defense.
# The English list matters more, since English text passes through the
# translation model first, which is where things can go wrong.
# ---------------------------------------------------------------------------
CRISIS_PATTERNS_LN_PHRASES = [
    "fàn a dzə kpú",            # covers two training examples — "fear unto death"
    "fó mentsə m me kpu",
    "wevrì fo wiíy koy",
    "yòʼ kpú",                  # "[I] want to die"
    "jeéti jeètín",
    "semrì e wiíy koy",
    "kifiʼìr ké kpu",
    "wìr koóm",
    "lo sə m kí gháʼ",
    "yòʼ dzəə e ntèʼ fen",
    "ghàʼkpu sí kív tàr wor",
    "wáa dzəə yúy wír",
]


def _normalize(text: str) -> str:
    """Lowercase, normalize unicode, strip most punctuation, collapse whitespace.
    Keeps Lamnso tonal marks intact (NFKC normalization, not stripping accents)."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\w\sʼ'-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text


def check_crisis_keywords(text: str) -> bool:
    """
    Returns True if the raw input text matches any known crisis pattern,
    in either English or Lamnso. Intended to run on the ORIGINAL user
    input, before any translation.
    """
    if not text or not text.strip():
        return False

    normalized = _normalize(text)

    for pattern in CRISIS_PATTERNS_EN:
        if re.search(pattern, normalized, flags=re.UNICODE):
            return True

    for phrase in CRISIS_PATTERNS_LN_PHRASES:
        if phrase in normalized:
            return True

    return False


if __name__ == "__main__":
    # Quick self-test
    test_cases = [
        ("i want to die", True),
        ("I want to DIE.", True),
        ("hello", False),
        ("bonjour", False),
        ("I am very worried and cannot sleep", False),
        ("M lóo ghan, m kù a fàn a dzə̀ kpú", True),       # real express_crisis example
        ("M yòʼ kpú", True),                                # real express_crisis example
        ("Wìr koóm", True),                                 # real express_crisis example
        ("sometimes i feel like giving up on life", True),
        ("the diesel engine is loud", False),               # should NOT match "die"
        # Negative controls: these use "kpu"/"kpú" but are NOT crisis intent
        # in the training data (grief, depression, schizophrenia) — must
        # stay False or the safety net would wrongly override those responses.
        ("Wàn kpù fó laʼ, m joó adzə̀m", False),             # express_grief
        ("Wánlè nsùm kpù, m wáa shèŋ vitú", False),          # express_depression
        ("Wiíy yù kpú lum, e lò, a yumyúm", False),          # express_schizophrenia_symptoms
    ]
    print("Running self-test...")
    all_passed = True
    for text, expected in test_cases:
        result = check_crisis_keywords(text)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] '{text}' -> {result} (expected {expected})")
    print("\nAll tests passed!" if all_passed else "\nSome tests failed — review patterns above.")
