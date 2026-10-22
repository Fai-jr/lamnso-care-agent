"""Download the model weights from the GitHub Release and verify their SHA-256.

    python -m translation.download_weights
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

URL = "https://github.com/Fai-jr/lamnso-care-agent/releases/download/v0.1-weights/best_model.pt"
HERE = Path(__file__).resolve().parent
DEST = HERE / "weights" / "best_model.pt"
CHECKSUM_FILE = HERE / "weights.sha256"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_hash() -> str:
    # weights.sha256 is the output of `sha256sum`: "<hash>  <path>"
    return CHECKSUM_FILE.read_text().split()[0].strip().lower()


def main() -> int:
    want = expected_hash()
    if DEST.exists() and sha256_of(DEST) == want:
        print(f"OK: {DEST} already present and verified.")
        return 0
    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_suffix(".part")
    print(f"Downloading {URL} ...")
    urllib.request.urlretrieve(URL, tmp)
    got = sha256_of(tmp)
    if got != want:
        tmp.unlink(missing_ok=True)
        print(f"CHECKSUM MISMATCH (expected {want}, got {got}). File discarded.", file=sys.stderr)
        return 1
    tmp.replace(DEST)
    print(f"OK: saved and verified {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
