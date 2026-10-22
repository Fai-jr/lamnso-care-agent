# =============================================================
# STEP B4: INTEGRATION MODULE
# Lamnso Mental Health Chatbot — Translation + Rasa Integration
# =============================================================
# This module provides a single function: get_bot_response()
#
# It accepts text in EITHER English or Lamnso, automatically
# detects which language it is, translates if needed, sends
# to Rasa, and returns the Lamnso response.
#
# Flow:
#   English input  → Translation Model → Lamnso → Rasa → Lamnso response
#   Lamnso input    → (skip translation) → Rasa → Lamnso response
#
# This file will later be imported by the Django backend (Step 5)
#
# Run standalone for testing:
#   python translation/integrate.py
# =============================================================

import torch
import torch.nn as nn
import sentencepiece as spm
import json
import math
import requests
import re
from pathlib import Path

# Dual-mode import: works both when this file is run directly
# (`python translation/integrate.py`, where Python adds translation/
# itself to sys.path) AND when it's imported by Django as a submodule
# of the `translation` package (`from translation.integrate import
# get_bot_response`, where translation/ is never added to sys.path on
# its own — only relative imports resolve correctly in that case).
try:
    from .crisis_safety import check_crisis_keywords
    from .crisis_responder import get_crisis_response, trigger_intent_response
    from .greeting_shortcuts import check_greeting_shortcut
    from .mental_health_keywords import check_mental_health_keywords
except ImportError:
    from crisis_safety import check_crisis_keywords
    from crisis_responder import get_crisis_response, trigger_intent_response
    from greeting_shortcuts import check_greeting_shortcut
    from mental_health_keywords import check_mental_health_keywords

# -------------------------------------------------------------
# CONFIGURATION
# Paths are built as ABSOLUTE paths based on this file's
# location, not relative to wherever the script is run from.
# This is essential because Django runs from backend/ while
# this module lives in translation/ — relative paths would
# break depending on which directory the server starts in.
# -------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent  # translation/

CONFIG = {
    'tokenizer_model': str(_THIS_DIR / 'lamnso_tokenizer.model'),
    'model_path':      str(_THIS_DIR / 'best_model.pt'),
    'vocab_size':      8000,
    'd_model':         256,
    'nhead':           4,
    'num_encoder_layers': 3,
    'num_decoder_layers': 3,
    'dim_feedforward': 512,
    'dropout':         0.1,
    'pad_id':          0,
    'bos_id':          2,
    'eos_id':          3,
    'max_seq_len':     128,
    'device':          'cpu',
    # Rasa server URL — must be running (rasa run --enable-api)
    'rasa_url':        'http://localhost:5005/webhooks/rest/webhook',
}

# -------------------------------------------------------------
# MODEL DEFINITION
# Must be identical to the architecture used in training
# -------------------------------------------------------------
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, dropout=0.1, max_len=512):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() *
            (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x):
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class TranslationTransformer(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.d_model = config['d_model']
        self.embedding = nn.Embedding(
            config['vocab_size'], config['d_model'],
            padding_idx=config['pad_id']
        )
        self.pos_encoding = PositionalEncoding(
            config['d_model'], config['dropout']
        )
        self.transformer = nn.Transformer(
            d_model=config['d_model'],
            nhead=config['nhead'],
            num_encoder_layers=config['num_encoder_layers'],
            num_decoder_layers=config['num_decoder_layers'],
            dim_feedforward=config['dim_feedforward'],
            dropout=config['dropout'],
            batch_first=True
        )
        self.output_projection = nn.Linear(
            config['d_model'], config['vocab_size']
        )

    def encode(self, src, src_key_padding_mask=None):
        src_emb = self.pos_encoding(
            self.embedding(src) * math.sqrt(self.d_model)
        )
        return self.transformer.encoder(
            src_emb, src_key_padding_mask=src_key_padding_mask
        )

    def decode(self, tgt, memory, tgt_mask=None,
               tgt_key_padding_mask=None,
               memory_key_padding_mask=None):
        tgt_emb = self.pos_encoding(
            self.embedding(tgt) * math.sqrt(self.d_model)
        )
        return self.transformer.decoder(
            tgt_emb, memory,
            tgt_mask=tgt_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=memory_key_padding_mask
        )


# -------------------------------------------------------------
# LANGUAGE DETECTION
# Distinguishes English from Lamnso using character analysis
# -------------------------------------------------------------
# Lamnso tonal characters that never appear in English
LAMNSO_MARKERS = set('əŋʼèéìíòóùúàáǎě')

# A much larger English vocabulary than the original 24-word list,
# covering common stopwords/function words, greetings, and the
# mental-health domain terms this chatbot actually deals with.
# This is still a heuristic, not a real language model — but the
# original 24-word list missed plain greetings like "hello", which
# is the realistic everyday case that matters most here.
ENGLISH_COMMON_WORDS = {
    # pronouns / determiners / core function words
    'i', 'im', 'ive', 'id', 'ill', 'me', 'my', 'mine', 'myself',
    'you', 'youre', 'your', 'yours', 'yourself',
    'he', 'she', 'it', 'its', 'we', 'were', 'us', 'our', 'ours',
    'they', 'theyre', 'them', 'their', 'theirs',
    'this', 'that', 'these', 'those',
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as',
    'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about',
    'against', 'between', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in',
    'out', 'on', 'off', 'over', 'under', 'again', 'further',
    'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
    'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
    'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too',
    'very', 'just', 'no', 'nor', 'not', 'one', 'else',
    # verbs
    'is', 'am', 'are', 'was', 'be', 'been', 'being',
    'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
    'will', 'would', 'shall', 'should', 'can', 'cant', 'cannot',
    'could', 'may', 'might', 'must', 'want', 'wanted', 'need',
    'needed', 'feel', 'feeling', 'feelings', 'felt', 'think',
    'thought', 'know', 'knew', 'go', 'going', 'went', 'come',
    'coming', 'came', 'see', 'seeing', 'saw', 'hear', 'hearing',
    'heard', 'talk', 'talking', 'speak', 'speaking', 'say', 'said',
    'tell', 'told', 'help', 'helped', 'helping',
    # greetings / common short replies
    'hello', 'hi', 'hey', 'morning', 'afternoon', 'evening',
    'goodbye', 'bye', 'please', 'thanks', 'thank', 'sorry',
    'yes', 'yeah', 'yep', 'no', 'nope', 'ok', 'okay', 'sure',
    'fine', 'good', 'bad', 'great', 'well', 'maybe', 'sometimes',
    'always', 'never',
    # mental-health domain vocabulary
    'today', 'tonight', 'yesterday', 'tomorrow', 'now', 'long',
    'time', 'god', 'lord', 'sad', 'sadness', 'worried', 'worry',
    'worrying', 'anxious', 'anxiety', 'nervous', 'voices', 'voice',
    'hopeless', 'hopelessness', 'alone', 'lonely', 'scared',
    'afraid', 'fear', 'frightened', 'tired', 'exhausted', 'sleep',
    'sleeping', 'cry', 'crying', 'depressed', 'depression', 'die',
    'died', 'dying', 'death', 'kill', 'killing', 'suicide',
    'suicidal', 'hurt', 'harm', 'pain', 'painful', 'life', 'living',
    'doctor', 'hospital', 'sick', 'illness', 'mental', 'support',
    'trouble', 'distress', 'refuge', 'safe', 'danger',
}

def _is_ascii_only(text):
    """True if every character is plain ASCII (no Lamnso/French/etc.
    accented characters at all)."""
    return all(ord(c) < 128 for c in text)


def detect_language(text):
    """
    Returns 'lamnso', 'english', or 'unknown'.

    Logic:
    - If text contains ANY Lamnso-specific tonal character, it's Lamnso.
    - Else if it overlaps with the English word list, it's English.
    - Else if it's plain ASCII with no recognizable English words at
      all, it's almost certainly neither language we support (e.g. a
      different language entirely, like French) — we now say so
      explicitly ('unknown') instead of guessing Lamnso, which used to
      send unrelated text straight to Rasa's NLU and produce a
      confidently wrong intent match (e.g. "bonjour" -> depression).
    - Only text that's NOT plain ASCII and has no Lamnso markers either
      (rare — usually some other accented-Latin language) still
      defaults to Lamnso, preserving the original safer-fallback
      reasoning for genuinely ambiguous cases.
    """
    text_lower = text.lower()

    lamnso_char_count = sum(1 for c in text_lower if c in LAMNSO_MARKERS)
    if lamnso_char_count > 0:
        return 'lamnso'

    words = set(re.findall(r'\b\w+\b', text_lower))
    if words & ENGLISH_COMMON_WORDS:
        return 'english'

    if _is_ascii_only(text):
        return 'unknown'

    # Not ASCII-only, no Lamnso markers, no English overlap — keep the
    # original conservative default rather than guess wrong.
    return 'lamnso'


# -------------------------------------------------------------
# TRANSLATOR CLASS
# Loads the model ONCE and reuses it for all translations
# (loading takes ~1 second, we don't want to repeat this
#  every time a user sends a message)
# -------------------------------------------------------------
class LamnsoTranslator:
    def __init__(self, config=CONFIG):
        self.config = config
        self.device = torch.device(config['device'])

        # Load tokenizer
        self.sp = spm.SentencePieceProcessor()
        self.sp.load(config['tokenizer_model'])

        # Load model
        self.model = TranslationTransformer(config).to(self.device)
        checkpoint = torch.load(
            config['model_path'], map_location=self.device
        )
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()

        print(f"[Translator] Loaded successfully")
        print(f"[Translator] Best val_loss: {checkpoint.get('val_loss', 'N/A')}")
        print(f"[Translator] BLEU score: {checkpoint.get('bleu_score', 'N/A')}")

    def _make_causal_mask(self, seq_len):
        mask = torch.triu(torch.ones(seq_len, seq_len), diagonal=1).bool()
        return mask.to(self.device)

    def _make_padding_mask(self, tensor):
        return (tensor == self.config['pad_id'])

    def translate(self, english_text, max_len=128):
        """
        Translates English text to Lamnso using greedy decoding.
        Returns the Lamnso translation as a string.
        """
        self.model.eval()
        with torch.no_grad():
            src_ids = [self.config['bos_id']] + \
                      self.sp.encode_as_ids(english_text)[:max_len-2] + \
                      [self.config['eos_id']]
            src = torch.tensor([src_ids], dtype=torch.long).to(self.device)
            src_pad_mask = self._make_padding_mask(src)

            memory = self.model.encode(src, src_pad_mask)
            tgt = torch.tensor(
                [[self.config['bos_id']]], dtype=torch.long
            ).to(self.device)

            for _ in range(max_len):
                tgt_mask = self._make_causal_mask(tgt.size(1))
                output = self.model.decode(
                    tgt, memory, tgt_mask=tgt_mask,
                    memory_key_padding_mask=src_pad_mask
                )
                logits = self.model.output_projection(output[:, -1, :])
                next_token = logits.argmax(dim=-1).unsqueeze(0)
                tgt = torch.cat([tgt, next_token.T], dim=1)
                if next_token.item() == self.config['eos_id']:
                    break

            output_ids = tgt[0, 1:].tolist()
            if self.config['eos_id'] in output_ids:
                output_ids = output_ids[:output_ids.index(self.config['eos_id'])]
            return self.sp.decode_ids(output_ids)


# -------------------------------------------------------------
# RASA COMMUNICATION
# Sends Lamnso text to the running Rasa server and gets response
# -------------------------------------------------------------
def send_to_rasa(lamnso_text, sender_id='user', rasa_url=CONFIG['rasa_url']):
    """
    Sends a message to the Rasa REST webhook and returns
    the bot's Lamnso response(s).

    IMPORTANT: Rasa server must be running first:
      cd rasa
      rasa run --enable-api --cors "*"
    """
    payload = {
        'sender': sender_id,
        'message': lamnso_text
    }
    try:
        response = requests.post(rasa_url, json=payload, timeout=10)
        response.raise_for_status()
        bot_messages = response.json()
        # Rasa returns a list of message objects, extract text
        texts = [msg.get('text', '') for msg in bot_messages if msg.get('text')]
        return texts if texts else ["M yoʼ biìmé kinyo ke à suuy ki e mò shéʼ."]
    except requests.exceptions.ConnectionError:
        return ["[ERROR] Rasa server is not running. "
                "Start it with: cd rasa && rasa run --enable-api --cors \"*\""]
    except requests.exceptions.Timeout:
        return ["[ERROR] Rasa server took too long to respond."]
    except Exception as e:
        return [f"[ERROR] {str(e)}"]


# -------------------------------------------------------------
# MAIN INTEGRATION FUNCTION
# This is the single function the Django backend will call
# -------------------------------------------------------------
_translator_instance = None

def get_translator():
    """Singleton pattern — load translator model only once"""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = LamnsoTranslator()
    return _translator_instance


def get_bot_response(user_text, sender_id='user'):
    """
    MAIN ENTRY POINT for the chatbot system.

    Accepts text in English OR Lamnso, automatically detects
    language, translates if needed, and returns the bot's
    Lamnso response(s).

    SAFETY NET: before anything else (before language detection,
    before translation, before NLU), the raw input is scanned for
    crisis/suicidal keywords in both English and Lamnso. This exists
    because the translation model and Rasa's NLU classifier can both
    fail on short, high-stakes input (e.g. "i want to die" was once
    translated to an empty string and misclassified as `deny`).
    Crisis detection must never depend on either of those components
    working correctly.

    Args:
        user_text: the message typed by the user
        sender_id: unique identifier for conversation tracking

    Returns:
        dict with keys:
            'detected_language': 'english', 'lamnso', 'unknown',
                                  'crisis_override' if the crisis safety
                                  net fired, 'mental_health_shortcut' if
                                  the anxiety/depression/schizophrenia/
                                  hopelessness keyword net fired, or
                                  'english_shortcut' if a common
                                  greeting/farewell/thanks word was routed
                                  directly without translation
            'translated_input':  the Lamnso version sent to Rasa
                                  (same as user_text if already Lamnso,
                                  or if any safety net/shortcut fired —
                                  no translation is attempted in those cases)
            'bot_responses':     list of Lamnso response strings
            'safety_net_triggered': True if the CRISIS keyword safety net
                                  fired specifically (not the mental
                                  health one, which is lower-stakes and
                                  uses 'matched_intent' instead)
            'fallback_used':     True if Rasa was unreachable and the
                                  hardcoded fallback message was used
                                  (only present when safety_net_triggered)
            'matched_intent':    which of the four mental-health intents
                                  matched (only present when
                                  detected_language == 'mental_health_shortcut')
            'translation_failed': True if the translation model produced
                                  an empty result (only present in that case)
    """
    # --- SAFETY NET: runs before translation/NLU, never skipped ---
    if check_crisis_keywords(user_text):
        crisis_result = get_crisis_response(sender_id)
        return {
            'detected_language':   'crisis_override',
            'original_input':      user_text,
            'translated_input':    user_text,  # no translation attempted
            'bot_responses':       crisis_result['bot_responses'],
            'safety_net_triggered': True,
            'fallback_used':       crisis_result['fallback_used'],
        }

    # --- MENTAL HEALTH KEYWORD SHORTCUT: anxiety / depression /
    # schizophrenia symptoms / hopelessness. See mental_health_keywords.py
    # docstring for why this exists — these intents showed ~0% recall
    # on held-out test data despite 100% on training data. ---
    mh_intent = check_mental_health_keywords(user_text)
    if mh_intent:
        try:
            messages = trigger_intent_response(sender_id, mh_intent)
            return {
                'detected_language':   'mental_health_shortcut',
                'original_input':      user_text,
                'translated_input':    user_text,
                'bot_responses':       messages,
                'safety_net_triggered': False,
                'matched_intent':      mh_intent,
            }
        except Exception:
            # Rasa unreachable or returned nothing — fall through to the
            # normal pipeline below rather than failing outright.
            pass

    # --- GREETING SHORTCUT: a few common conversational words the
    # translation model is known to mishandle (see greeting_shortcuts.py
    # docstring) get routed directly to their Rasa intent, skipping
    # translation entirely. ---
    shortcut_intent = check_greeting_shortcut(user_text)
    if shortcut_intent:
        try:
            messages = trigger_intent_response(sender_id, shortcut_intent)
            return {
                'detected_language':   'english_shortcut',
                'original_input':      user_text,
                'translated_input':    user_text,
                'bot_responses':       messages,
                'safety_net_triggered': False,
            }
        except Exception:
            # If Rasa is unreachable or anything else goes wrong, fall
            # through to the normal pipeline below rather than failing.
            pass

    detected_lang = detect_language(user_text)

    if detected_lang == 'unknown':
        # Plain ASCII text that matched neither Lamnso markers nor any
        # recognized English word — most likely a different language
        # entirely (e.g. French). Previously this defaulted to the
        # Lamnso path and got sent to Rasa's NLU, which produced a
        # confidently wrong intent match. Better to say so plainly.
        return {
            'detected_language': 'unknown',
            'original_input':    user_text,
            'translated_input':  user_text,
            'bot_responses':     [
                "Sorry, I can only understand English or Lamnso. "
                "Could you try writing that again in one of those?"
            ],
            'safety_net_triggered': False,
        }

    if detected_lang == 'english':
        translator = get_translator()
        lamnso_input = translator.translate(user_text)

        if not lamnso_input or not lamnso_input.strip():
            # The translation model produced nothing — this happens on
            # input far outside its Bible/dictionary training domain.
            # Forwarding an empty string to Rasa's NLU produces an
            # unpredictable (and once, alarming) intent match, so we
            # stop here instead rather than guessing.
            return {
                'detected_language':  'english',
                'original_input':     user_text,
                'translated_input':   lamnso_input,
                'bot_responses':      [
                    "I'm not sure how to say that in Lamnso yet — could "
                    "you try describing how you're feeling, or what kind "
                    "of help you're looking for, in a different way?"
                ],
                'safety_net_triggered': False,
                'translation_failed': True,
            }
    else:
        lamnso_input = user_text

    bot_responses = send_to_rasa(lamnso_input, sender_id=sender_id)

    return {
        'detected_language': detected_lang,
        'original_input':    user_text,
        'translated_input':  lamnso_input,
        'bot_responses':     bot_responses,
        'safety_net_triggered': False,
    }


# -------------------------------------------------------------
# STANDALONE TEST
# Run this file directly to test the full pipeline
# -------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 60)
    print("STEP B4: Testing Integration Module")
    print("=" * 60)

    print("\nIMPORTANT: Make sure Rasa server is running in another")
    print("terminal first:")
    print("  cd rasa")
    print("  rasa run --enable-api --cors \"*\"")
    print("\nLoading translation model...")

    test_inputs = [
        # English inputs — will be translated first
        "I am very worried and cannot sleep",
        "Please help me, I feel very sad today",
        "God is my refuge in times of trouble",
        # Lamnso inputs — sent directly, no translation
        "Wìy ó fèn",
        "M júʼum jùʼùmén",
        # Safety net test cases — these should bypass translation/NLU
        # entirely and go straight to the crisis response
        "i want to die",
        "M lóo ghan, m kù a fàn a dzə̀ kpú",
        # Language detection fix test cases
        "hello",
        "bonjour",
    ]

    for text in test_inputs:
        print("\n" + "-" * 60)
        print(f"USER INPUT: {text}")
        result = get_bot_response(text)
        print(f"DETECTED LANGUAGE: {result['detected_language']}")
        if result['detected_language'] == 'english':
            print(f"TRANSLATED TO LAMNSO: {result['translated_input']}")
        if result.get('safety_net_triggered'):
            print(f"SAFETY NET TRIGGERED (fallback_used={result['fallback_used']})")
        if result.get('translation_failed'):
            print(f"TRANSLATION FAILED — empty result, guard intercepted before Rasa")
        print(f"BOT RESPONSE(S):")
        for r in result['bot_responses']:
            print(f"  {r}")

    print("\n" + "=" * 60)
    print("STEP B4 TEST COMPLETE")
    print("=" * 60)
