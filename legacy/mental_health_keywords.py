"""
mental_health_keywords.py

Extends the crisis_safety.py keyword-safety-net pattern to four more
intents: express_anxiety, express_depression,
express_schizophrenia_symptoms, and express_hopelessness.

WHY THIS EXISTS:
A held-out evaluation (rasa test nlu against examples never seen
during training — see tests/) showed these four intents at or near
0% recall on novel phrasing, despite 100% accuracy on training data
itself. That's a small-data overfitting signature: each intent only
had 5-16 training examples, likely too few for the DIET classifier to
learn a generalizable notion of "what anxiety sounds like" rather
than memorizing the specific training sentences. crisis already had
an equivalent safety net and was the one intent NOT showing this
fragility in the same way when the net is active — this module gives
the other four mental-health-disclosure intents the same kind of
defense in depth.

METHODOLOGY (same rigor as crisis_safety.py):
- Lamnso phrases below were mined as n-grams from each intent's
  ACTUAL training examples in nlu.yml, then verified to not appear in
  ANY of the other 17 intents' examples (including the other 3 target
  intents here) — checked programmatically, not guessed. One
  candidate ("m wáa dzə") was caught and fixed for matching as a
  word-boundary-violating PREFIX of an unrelated word in a different
  intent's example ("dzəə́") — worth knowing this class of bug exists
  in substring matching on a tonal language and double-checking any
  future additions the same way.
- English patterns deliberately avoid bare disease-name words alone
  (e.g. NOT just "depression") because express_depression's sibling
  intent ask_about_depression also legitimately mentions that word —
  "I feel depressed" and "what is depression" cannot be told apart by
  a bare keyword. Patterns require first-person experiential framing
  instead. A question-marker guard (see _looks_like_question) is an
  additional layer: if the message looks like a question, none of
  these four shortcuts fire at all, regardless of pattern match.

LIKE crisis_safety.py, this is NOT a replacement for Rasa's NLU — it's
a redundant, narrower-precision-by-design safety net for cases the
NLU is currently known to handle poorly. If ambiguous (more than one
of these four intents' patterns match), this module deliberately
returns None rather than guessing, leaving the decision to the normal
pipeline.

CAVEAT: as with the crisis keyword list, the Lamnso phrases here were
verified against your own training data for cross-intent uniqueness,
but I do not speak Lamnso and cannot independently confirm semantic
correctness. Worth a fluent speaker's sanity check before relying on
this in production, same as crisis_safety.py.
"""

import re


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\sʼ'-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text


def _looks_like_question(normalized_text: str) -> bool:
    """
    Guards against hijacking ask_about_anxiety / ask_about_depression /
    ask_about_schizophrenia, which share vocabulary with their express_*
    counterparts but mean something very different ("what is anxiety"
    vs "I feel anxious"). If this returns True, none of the shortcuts
    in this module should fire.
    """
    if normalized_text.strip().endswith("?"):
        return True
    question_starts = (
        "what", "whats", "what's", "how", "why", "can you", "could you",
        "tell me about", "explain", "do you know", "is there",
    )
    return any(normalized_text.startswith(q) for q in question_starts)


# ---------------------------------------------------------------------------
# ENGLISH patterns — first-person experiential framing required, not bare
# disease-name words, to avoid colliding with the ask_about_* intents.
# ---------------------------------------------------------------------------
ENGLISH_PATTERNS = {
    "express_anxiety": [
        r"\bi'?m (so |really |very )?anxious\b",
        r"\bi feel(ing)? anxious\b",
        r"\bi have (bad |severe )?anxiety\b",
        r"\bpanic attack\b", r"\bpanicking\b",
        r"\bcan'?t stop worrying\b", r"\bconstantly worried\b",
        r"\bworry(ing)? about everything\b",
        r"\bover[\s-]?thinking\b", r"\bcan'?t stop overthinking\b",
        r"\bracing thoughts\b", r"\bthoughts (keep |are )?racing\b",
        r"\bmind (won'?t|wont) stop racing\b",
        r"\bon edge\b",
        r"\bcan'?t (relax|sit still)\b",
        r"\bnervous wreck\b",
        r"\bheart (is |keeps )?racing\b", r"\bheart (won'?t stop )?pounding\b",
        r"\bsomething bad is (about to|going to) happen\b",
        r"\b(hands?|body|legs?) (won'?t|wont|can'?t) stop (shaking|trembling)\b",
    ],
    "express_depression": [
        r"\bi'?m (so |really |very )?depressed\b",
        r"\bi feel(ing)? depressed\b",
        r"\bi have depression\b",
        r"\bno energy (for anything|at all|these days|anymore)\b",
        r"\bno motivation\b",
        r"\bdon'?t feel like doing anything\b",
        r"\bcrying (a lot|all the time)\b", r"\bcan'?t stop crying\b",
        r"\bfeel(ing)? empty\b", r"\bfeel(ing)? numb\b",
        r"\blost interest in (everything|things)\b",
        r"\bstay in bed all day\b",
        r"\bdon'?t enjoy anything\b", r"\bnothing makes me happy\b",
        r"\bsad all the time\b", r"\bfeel sad every day\b",
        r"\beverything feels (heavy|pointless)\b",
    ],
    "express_schizophrenia_symptoms": [
        r"\bhear(ing)? voices\b", r"\bvoices? in my head\b",
        r"\bhear(ing)? (someone|something).{0,40}(when|that) no one\b",
        r"\bsee(ing)? things that.{0,40}(aren'?t|arent|isn'?t) there\b",
        r"\bpeople (are )?watching me\b", r"\bbeing watched\b",
        r"\bsomeone is following me\b",
        r"\bfeel(ing)? paranoid\b",
        r"\bthoughts (aren'?t|that aren'?t) my own\b",
        r"\bsomeone (is )?putting thoughts in my head\b",
        r"\bcan'?t tell what'?s real\b", r"\bdon'?t know what'?s real\b",
        r"\bthoughts feel scattered\b",
    ],
    "express_hopelessness": [
        r"\bi'?ve given up (trying|hope|on (life|everything|myself|my dreams))\b",
        r"\bi'?m giving up (on (life|everything|myself|trying))\b",
        r"\bno point (in )?trying\b", r"\bwhat'?s the point\b",
        r"\bnothing (will ever|is (ever )?going to) (get better|change)\b",
        r"\bthings (will|are going to) never (change|get better)\b",
        r"\bno way out\b",
        r"\bno future\b", r"\bstuck with no future\b",
        r"\blost (all )?hope\b", r"\bfeel(ing)? hopeless\b",
        r"\b(no reason|don'?t see (any |a )?reason) to (keep|continue) trying\b",
    ],
}

# ---------------------------------------------------------------------------
# LAMNSO phrases — mined from nlu.yml, each verified unique to its target
# intent across all 18 intents (see module docstring).
# ---------------------------------------------------------------------------
LAMNSO_PHRASES = {
    "express_anxiety": [
        "m wáa gìr", "m wáa júʼúm", "m wáa kàŋkàŋ", "m wáa rəm", "m wáa rəsí",
        "m tankìr e", "yù sáʼka wùmòʼ", "m júʼum jùʼùmén",
    ],
    "express_depression": [
        "m dzə kém", "m wáa dzə e", "m wáa joó", "m wáa wón",
        "m sí lar làrìn", "m wiy fo kwaʼ", "m jày dzə ə", "m lim lim dór",
        "wánlè nsùm kpù", "kimbèʼbìy kí wíy kpu",
    ],
    "express_schizophrenia_symptoms": [
        "m wáa ghànghàn", "m wáa yèn virə", "m wáa jìŋ", "m wáa bùn",
        "m wáa no meluʼ", "m wáa yumyúm", "m yú kiŋkar",
        "taàtá lòo kpu", "wiíy yù kpú lum", "ŋgaàbaá lóo dzə",
    ],
    "express_hopelessness": [
        "m sí wuunè wuùnèn", "m làa yòʼ yen", "m làa yòʼ kér",
        "m joonè joònèn", "kinjòʼsì ké dzə", "m yèn ŋgeʼ e wǎn",
        "bó ŋgeʼ si yòʼ biíme", "ji m mey",
    ],
}


def _looks_like_bereavement(normalized_text: str) -> bool:
    """
    Guards express_depression's crying-related patterns against
    bereavement context. "I can't stop crying" is a symptom shared by
    both depression and grief, but if the message also mentions a
    death, grief is the better fit even though grief has no dedicated
    safety net of its own yet — confidently mislabeling it as
    depression is worse than letting it fall through to the normal
    pipeline.
    """
    bereavement_markers = (
        "passed away", "passed on", "died", "death of", "funeral",
        "lost my mother", "lost my father", "lost my brother",
        "lost my sister", "lost my child", "lost my husband",
        "lost my wife", "lost my parent", "lost my grandmother",
        "lost my grandfather", "lost my son", "lost my daughter",
    )
    return any(marker in normalized_text for marker in bereavement_markers)


def check_mental_health_keywords(text: str):
    """
    Returns the matched intent name ('express_anxiety',
    'express_depression', 'express_schizophrenia_symptoms', or
    'express_hopelessness') if exactly one of them matches the input,
    or None if zero or more than one match (ambiguous — let the normal
    pipeline decide rather than guess), or if the text looks like a
    question (to avoid hijacking the ask_about_* intents).
    """
    if not text or not text.strip():
        return None

    normalized = _normalize(text)

    if _looks_like_question(normalized):
        return None

    is_bereavement = _looks_like_bereavement(normalized)

    matched_intents = set()

    for intent, patterns in ENGLISH_PATTERNS.items():
        if intent == "express_depression" and is_bereavement:
            continue  # let grief-context crying fall through, not depression
        for pattern in patterns:
            if re.search(pattern, normalized, flags=re.UNICODE):
                matched_intents.add(intent)
                break

    for intent, phrases in LAMNSO_PHRASES.items():
        if intent == "express_depression" and is_bereavement:
            continue
        for phrase in phrases:
            if phrase in normalized:
                matched_intents.add(intent)
                break

    if len(matched_intents) == 1:
        return matched_intents.pop()
    return None


if __name__ == "__main__":
    test_cases = [
        ("I feel anxious all the time", "express_anxiety"),
        ("My heart is racing and I can't calm down", "express_anxiety"),
        ("I'm so depressed lately", "express_depression"),
        ("I don't feel like doing anything anymore", "express_depression"),
        ("I keep hearing voices when no one is there", "express_schizophrenia_symptoms"),
        ("I feel like people are watching me", "express_schizophrenia_symptoms"),
        ("I've given up trying", "express_hopelessness"),
        ("Nothing is ever going to get better", "express_hopelessness"),
        # Question guard — should NOT fire despite shared vocabulary
        ("What is anxiety?", None),
        ("Can you explain what depression means", None),
        ("What are the symptoms of schizophrenia?", None),
        # Should not match anything
        ("Hello, how are you?", None),
        ("Thank you so much", None),
        # Real Lamnso training-derived examples
        ("M wáa júʼúm e mǒ e vinyo ve bi", "express_anxiety"),
        ("M wáa joó e mǒ sidzə̀m", "express_depression"),
        ("M wáa ghànghàn, bo kár kitú", "express_schizophrenia_symptoms"),
        ("M sí wuunè wuùnèn lán", "express_hopelessness"),
    ]
    print("Running self-test...")
    all_passed = True
    for text, expected in test_cases:
        result = check_mental_health_keywords(text)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] '{text}' -> {result} (expected {expected})")
    print("\nAll tests passed!" if all_passed else "\nSome tests failed — review patterns above.")
