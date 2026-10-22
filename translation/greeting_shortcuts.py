"""
greeting_shortcuts.py

Maps a small, fixed set of very common English conversational words
(greetings, farewells, thanks) directly to their Rasa intent names,
bypassing the translation model entirely for these cases.

WHY THIS EXISTS:
The translation model was trained exclusively on Bible verses and
mental-health dictionary sentences — it has essentially never seen
casual conversational filler like "hello" or "thanks". On such
out-of-domain input, the decoder can predict end-of-sequence as its
very first generated token, producing an EMPTY translation. Sending
that empty string into Rasa's NLU is meaningless, and was observed in
testing to produce an unpredictable — and in one case alarming —
intent match ("hello" -> express_crisis response).

This is a deliberately narrow patch for the exact words most likely to
trigger that failure mode. It is NOT a general solution to translation
quality, and is not meant to replace Rasa's NLU for anything beyond
these few words.
"""

import re

# intent name -> set of normalized phrases that should map to it directly
GREETING_SHORTCUTS = {
    'greet': {
        'hello', 'hi', 'hey', 'hiya',
        'good morning', 'good afternoon', 'good evening',
        'morning', 'afternoon', 'evening',
    },
    'goodbye': {
        'bye', 'goodbye', 'good bye', 'see you', 'see ya', 'farewell',
    },
    'express_gratitude': {
        'thanks', 'thank you', 'thx', 'ty', 'much appreciated', 'appreciate it',
    },
}


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text


def check_greeting_shortcut(text: str):
    """
    Returns the matching Rasa intent name if the (normalized) input is an
    exact match for one of the known greeting/farewell/thanks phrases,
    otherwise returns None. Deliberately exact-match only, not substring —
    this should stay narrow rather than guessing on longer sentences that
    merely contain the word "hi" somewhere.
    """
    if not text or not text.strip():
        return None

    normalized = _normalize(text)

    for intent, phrases in GREETING_SHORTCUTS.items():
        if normalized in phrases:
            return intent

    return None


if __name__ == "__main__":
    test_cases = [
        ("hello", "greet"),
        ("Hello!", "greet"),
        ("hi", "greet"),
        ("good morning", "greet"),
        ("bye", "goodbye"),
        ("thanks", "express_gratitude"),
        ("thank you", "express_gratitude"),
        ("I am very worried and cannot sleep", None),
        ("hi there, I wanted to ask something", None),  # not an exact match — stays narrow on purpose
    ]
    print("Running self-test...")
    all_passed = True
    for text, expected in test_cases:
        result = check_greeting_shortcut(text)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] '{text}' -> {result} (expected {expected})")
    print("\nAll tests passed!" if all_passed else "\nSome tests failed — review patterns above.")
