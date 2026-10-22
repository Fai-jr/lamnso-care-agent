"""English -> Lamnso translation (the project's own pre-existing model), behind a small interface.

The model only translates English -> Lamnso. torch / sentencepiece are imported lazily so the rest of
the app (and SAMPLE_MODE) runs on machines without them.
"""
from __future__ import annotations

from pathlib import Path

MODEL_CONFIG = {
    'vocab_size': 8000, 'd_model': 256, 'nhead': 4,
    'num_encoder_layers': 3, 'num_decoder_layers': 3,
    'dim_feedforward': 512, 'dropout': 0.1,
    'pad_id': 0, 'bos_id': 2, 'eos_id': 3, 'max_seq_len': 128,
}


class TranslatorUnavailable(RuntimeError):
    """torch/sentencepiece missing, or weights not downloaded."""


class SampleTranslator:
    """Offline stand-in for SAMPLE_MODE. Output is clearly marked and is NOT Lamnso."""
    name = "sample-translator"

    def translate(self, english_text: str) -> str:
        return f"[sample-lamnso] {english_text}"


class LamnsoTranslator:
    name = "lamnso-transformer"

    def __init__(self, weights_path: Path, tokenizer_path: Path, device: str = "cpu"):
        try:
            import torch
            import sentencepiece as spm
            from translation.model import TranslationTransformer
        except ImportError as exc:
            raise TranslatorUnavailable(
                "Install torch and sentencepiece to use the real translator (see requirements.txt)."
            ) from exc
        weights_path, tokenizer_path = Path(weights_path), Path(tokenizer_path)
        if not weights_path.exists():
            raise TranslatorUnavailable(
                f"Weights not found at {weights_path}. Run: python -m translation.download_weights")
        if not tokenizer_path.exists():
            raise TranslatorUnavailable(f"Tokenizer not found at {tokenizer_path}")

        self._torch = torch
        self.cfg = dict(MODEL_CONFIG)
        self.device = torch.device(device)
        self.sp = spm.SentencePieceProcessor()
        self.sp.load(str(tokenizer_path))
        self.model = TranslationTransformer(self.cfg).to(self.device)
        try:
            ckpt = torch.load(weights_path, map_location=self.device, weights_only=True)
        except Exception:
            # Older torch, or non-tensor metadata in the checkpoint. The file is checksum-verified.
            ckpt = torch.load(weights_path, map_location=self.device)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()
        self.info = {"val_loss": ckpt.get("val_loss"), "bleu_score": ckpt.get("bleu_score")}

    def translate(self, english_text: str, max_len: int = 128) -> str:
        """Greedy decoding, unchanged from the original project. May return '' on out-of-domain input."""
        torch, cfg = self._torch, self.cfg
        self.model.eval()
        with torch.no_grad():
            src_ids = ([cfg["bos_id"]] + self.sp.encode_as_ids(english_text)[: max_len - 2]
                       + [cfg["eos_id"]])
            src = torch.tensor([src_ids], dtype=torch.long).to(self.device)
            src_pad_mask = src == cfg["pad_id"]
            memory = self.model.encode(src, src_pad_mask)
            tgt = torch.tensor([[cfg["bos_id"]]], dtype=torch.long).to(self.device)
            for _ in range(max_len):
                n = tgt.size(1)
                tgt_mask = torch.triu(torch.ones(n, n), diagonal=1).bool().to(self.device)
                out = self.model.decode(tgt, memory, tgt_mask=tgt_mask,
                                        memory_key_padding_mask=src_pad_mask)
                logits = self.model.output_projection(out[:, -1, :])
                nxt = logits.argmax(dim=-1).unsqueeze(0)
                tgt = torch.cat([tgt, nxt.T], dim=1)
                if nxt.item() == cfg["eos_id"]:
                    break
            ids = tgt[0, 1:].tolist()
            if cfg["eos_id"] in ids:
                ids = ids[: ids.index(cfg["eos_id"])]
            return self.sp.decode_ids(ids)
