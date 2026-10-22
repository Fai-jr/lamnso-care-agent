"""Translation transformer architecture.

PRE-EXISTING: extracted unchanged from the original project's integrate.py (written before the
hackathon). It must stay identical to the architecture used in training or the weights will not load.
"""
import math

import torch
import torch.nn as nn


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
