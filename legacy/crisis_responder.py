"""
crisis_responder.py

Forces the configured crisis response when the safety net in
crisis_safety.py fires. Uses Rasa's /trigger_intent endpoint so the
ACTUAL response text stays defined in one place (domain.yml) instead
of being duplicated here — except for FALLBACK_CRISIS_MESSAGE, which is
an intentional, independent duplicate used ONLY if Rasa cannot be
reached at all. That duplication is deliberate: it is the last line of
defense, and it must not depend on Rasa being up.
"""

import requests

RASA_URL = "http://localhost:5005"

# This MUST match the intent name used in your domain.yml / nlu.yml for
# crisis expressions. Based on the naming pattern of your other intents
# (express_anxiety, express_depression, etc.) this is almost certainly
# "express_crisis" — confirm against your domain.yml and change if needed.
CRISIS_INTENT_NAME = "express_crisis"

# IMPORTANT: replace this with the actual Lamnso crisis response text from
# your domain.yml (utter_express_crisis or equivalent), word for word. This
# is the message a user sees ONLY if Rasa itself is down or unreachable —
# it should never normally be needed, but it must exist.
FALLBACK_CRISIS_MESSAGE = (
    "M yù tóŋ yémé e mò. Éè Nyùy Tàr, ku wìy. Nyùy wom, ku lùŋèr mo. "
    "M dzə̀ fèn fo à lán feyì."
)


def trigger_intent_response(sender_id: str, intent_name: str, timeout: int = 5):
    """
    Generic version of the intent-triggering call — forces Rasa to fire
    ANY named intent for this conversation, bypassing NLU classification.
    Returns a list of bot message strings. Raises on failure so callers
    can decide how to handle it.
    """
    url = f"{RASA_URL}/conversations/{sender_id}/trigger_intent"
    params = {"output_channel": "latest"}
    payload = {"name": intent_name, "entities": {}}

    response = requests.post(url, params=params, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    messages = [m["text"] for m in data.get("messages", []) if "text" in m]

    if not messages:
        raise ValueError(
            f"trigger_intent for '{intent_name}' succeeded but returned no messages"
        )

    return messages


def trigger_crisis_response(sender_id: str, timeout: int = 5):
    """
    Forces Rasa to fire the crisis intent for this conversation, bypassing
    NLU classification entirely. Returns a list of bot message strings.

    Raises the underlying exception on failure so the caller can decide
    how to handle it (we want the caller to fall back, not silently swallow
    a Rasa outage).
    """
    return trigger_intent_response(sender_id, CRISIS_INTENT_NAME, timeout=timeout)


def get_crisis_response(sender_id: str):
    """
    Top-level safety entry point. Tries the real Rasa-configured crisis
    response first; falls back to a hardcoded message if Rasa is
    unreachable or misbehaves in any way. Never raises.
    """
    try:
        messages = trigger_crisis_response(sender_id)
        return {
            "bot_responses": messages,
            "safety_net_triggered": True,
            "fallback_used": False,
        }
    except Exception as e:
        return {
            "bot_responses": [FALLBACK_CRISIS_MESSAGE],
            "safety_net_triggered": True,
            "fallback_used": True,
            "fallback_reason": str(e),
        }
