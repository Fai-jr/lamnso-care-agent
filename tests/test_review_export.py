import csv
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("review", Path(__file__).resolve().parents[1] / "scripts" / "export_translations_for_review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class Fake:
    def translate(self, t):
        if "tired" in t:
            return ""                                    # an empty result must be flagged, not hidden
        if "sleep" in t:
            return "a b c a b c a b c d e f"             # looping output must be flagged
        return f"LN[{t}]"


def test_rows_cover_all_sentences_and_flag_bad_output(tmp_path):
    rows = review.build_rows(Fake())
    assert len(rows) == len(review.SENTENCES) + 1 and rows[-1]["id"] == "crisis"
    flags = {r["english"]: r["looks_repetitive"] for r in rows}
    assert flags["It sounds like you are very tired."] == "empty"
    assert flags["It is hard when you cannot sleep."] == "yes"
    assert flags["You are not alone."] == "no"
    out = tmp_path / "r.csv"
    review.write_csv(rows, out)
    with open(out, newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    assert header == review.COLUMNS


def test_summary_counts_only_valid_ratings_and_reports_the_crisis_verdict(tmp_path):
    out = tmp_path / "r.csv"
    rows = review.build_rows(Fake())
    for i, r in enumerate(rows[:-1]):
        r["meaning_1to5"] = str(5 if i < 10 else 3)
        r["natural_1to5"] = "4" if i < 4 else ""          # blanks are ignored
        r["safe_yes_no"] = "yes" if i < 15 else "NO"
    rows[-1]["safe_yes_no"] = "yes"
    review.write_csv(rows, out)
    s = review.summarise(out)
    assert s["sentences"] == 20 and s["rated"] == 20
    assert s["meaning_avg"] == 4.0 and s["meaning_4_or_5"] == 10
    assert s["natural_avg"] == 4.0
    assert s["safe_yes"] == 15 and s["safe_no"] == 5 and s["crisis_message_safe"] == "yes"
