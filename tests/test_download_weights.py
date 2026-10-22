from translation import download_weights as dw


def test_sha256_matches_known_value(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    assert dw.sha256_of(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
