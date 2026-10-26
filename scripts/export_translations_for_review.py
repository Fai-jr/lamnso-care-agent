"""Make a sheet a fluent Lamnso speaker can fill in, then turn their ratings into numbers for the deck.

    python scripts/export_translations_for_review.py                  # writes docs/evidence/translation_review.csv
    python scripts/export_translations_for_review.py --sample         # layout check only (no model needed)
    python scripts/export_translations_for_review.py --summarise docs/evidence/translation_review.csv

The speaker fills three columns (open the CSV in Excel, LibreOffice or Google Sheets):
  meaning_1to5     does the Lamnso keep the meaning of the English?        1 = no, 5 = fully
  natural_1to5     does it sound like something a person would say?        1 = no, 5 = fully
  safe_yes_no      is it safe to show to someone who is struggling?        yes / no
and may write a better version in `corrected_lamnso`.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import ROOT, get_settings  # noqa: E402
from backend.app.pipeline import looks_degenerate  # noqa: E402
from backend.app.safety import CRISIS_ENGLISH, CRISIS_LAMNSO  # noqa: E402

SENTENCES = [
    "I am sorry you are feeling sad.", "It is okay to have hard days.", "You are not alone.", "I am here to listen.",
    "Would you like to tell me more?", "It sounds like you are very tired.", "Take a slow, deep breath.",
    "Try to rest a little tonight.", "Your feelings matter.", "It is okay to ask for help.",
    "Talk to someone you trust.", "A short walk can help you feel better.", "You are doing the best you can.",
    "Many people feel this way sometimes.", "Let us take one small step today.", "I hear that you are worried.",
    "Thank you for telling me how you feel.", "It is hard when you cannot sleep.", "I am glad you shared this with me.",
    "Please contact your local emergency services if you are in danger.",
]
COLUMNS = ["id", "english", "lamnso_machine", "looks_repetitive", "meaning_1to5", "natural_1to5", "safe_yes_no",
           "corrected_lamnso", "notes"]
DEFAULT_OUT = ROOT / "docs" / "evidence" / "translation_review.csv"


def build_rows(translator) -> list:
    rows = []
    for i, english in enumerate(SENTENCES, 1):
        try:
            lamnso = (translator.translate(english) or "").strip()
        except Exception:  # keep going: a failure is itself a result worth showing the speaker
            lamnso = ""
        flag = "empty" if not lamnso else ("yes" if looks_degenerate(lamnso) else "no")
        rows.append({"id": i, "english": english, "lamnso_machine": lamnso, "looks_repetitive": flag})
    # the fixed crisis text is NOT machine-translated: it is the wording that needs a speaker's sign-off most
    rows.append({"id": "crisis", "english": CRISIS_ENGLISH, "lamnso_machine": CRISIS_LAMNSO, "looks_repetitive": "n/a",
                 "notes": "FIXED crisis message (shown with no model involved). Please check meaning, tone and safety closely."})
    return rows


def write_csv(rows: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig so Excel shows Lamnso tone marks
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in COLUMNS})


def summarise(path: Path) -> dict:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["id"] != "crisis"]

    def nums(col):
        out = []
        for r in rows:
            try:
                v = float(r[col])
            except (TypeError, ValueError):
                continue
            if 1 <= v <= 5:
                out.append(v)
        return out

    meaning, natural = nums("meaning_1to5"), nums("natural_1to5")
    rated = [r for r in rows if (r["safe_yes_no"] or "").strip().lower() in ("yes", "no")]
    safe = [r for r in rated if r["safe_yes_no"].strip().lower() == "yes"]
    crisis = [r for r in csv.DictReader(open(path, newline="", encoding="utf-8-sig")) if r["id"] == "crisis"]
    return {
        "sentences": len(rows), "rated": len(rated),
        "meaning_avg": round(sum(meaning) / len(meaning), 2) if meaning else None,
        "natural_avg": round(sum(natural) / len(natural), 2) if natural else None,
        "meaning_4_or_5": sum(1 for v in meaning if v >= 4),
        "safe_yes": len(safe), "safe_no": len(rated) - len(safe),
        "crisis_message_safe": (crisis[0]["safe_yes_no"].strip().lower() or None) if crisis else None,
    }


def main(argv: list) -> int:
    if "--summarise" in argv:
        path = Path(argv[argv.index("--summarise") + 1])
        for key, value in summarise(path).items():
            print(f"{key:22} {value}")
        return 0
    if "--sample" in argv:
        from translation.translator import SampleTranslator
        translator = SampleTranslator()
    else:
        from translation.translator import LamnsoTranslator, TranslatorUnavailable
        s = get_settings()
        try:
            translator = LamnsoTranslator(s.weights_path, s.tokenizer_path)
        except TranslatorUnavailable as exc:
            print("Could not load the translator:", exc)
            return 1
    write_csv(build_rows(translator), DEFAULT_OUT)
    print(f"Wrote {DEFAULT_OUT}\nGive it to a fluent speaker; afterwards run:\n"
          f"  python scripts/export_translations_for_review.py --summarise {DEFAULT_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
