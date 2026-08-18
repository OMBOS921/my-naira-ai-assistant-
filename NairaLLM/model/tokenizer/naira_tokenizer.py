"""
Custom Tokenizer for NairaLLM.

Supports English, Hindi (Devanagari), Hinglish, code, JSON, file paths,
and special Naira control tokens. Supports both HuggingFace `tokenizers` and
a zero-dependency pure-Python Byte-Level BPE implementation.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

try:
    from tokenizers import Tokenizer, decoders, models, normalizers, pre_tokenizers, trainers
    _HAS_TOKENIZERS_LIB = True
except ImportError:
    _HAS_TOKENIZERS_LIB = False

_LOG = logging.getLogger("nairallm.tokenizer")

SPECIAL_TOKENS = [
    "<|pad|>",
    "<|endoftext|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|context|>",
    "<|intent|>",
    "<|plan|>",
    "<|tool_call|>",
    "<|tool_result|>",
    "<|verify|>",
    "<|recover|>",
    "<|no_tool|>",
    "<|proactive|>",
    "<|final|>",
    "<|thought|>",
    "<|unk|>",
]


def _bytes_to_unicode() -> dict[int, str]:
    """GPT-2 standard byte-to-unicode mapping to represent all 256 bytes safely as unicode chars."""
    bs = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    cs = bs[:]
    n = 0
    for b in range(2**8):
        if b not in bs:
            bs.append(b)
            cs.append(2**8 + n)
            n += 1
    return {b: chr(c) for b, c in zip(bs, cs)}


class PurePythonBpeTokenizer:
    """Pure-Python Byte-Level BPE Tokenizer for zero-dependency environments."""

    def __init__(self, special_tokens: list[str]) -> None:
        self.special_tokens = list(special_tokens)
        self.special_token_map = {tok: idx for idx, tok in enumerate(self.special_tokens)}
        self.byte_encoder = _bytes_to_unicode()
        self.byte_decoder = {v: k for k, v in self.byte_encoder.items()}
        self.vocab: dict[str, int] = {}
        self.inverse_vocab: dict[int, str] = {}
        self.merges: list[tuple[str, str]] = []
        self.bpe_ranks: dict[tuple[str, str], int] = {}
        self.cache: dict[str, list[str]] = {}

        self._init_base_vocab()

    def _init_base_vocab(self) -> None:
        self.vocab = {}
        for idx, tok in enumerate(self.special_tokens):
            self.vocab[tok] = idx
        for b_code, char_rep in self.byte_encoder.items():
            if char_rep not in self.vocab:
                self.vocab[char_rep] = len(self.vocab)
        self.inverse_vocab = {idx: tok for tok, idx in self.vocab.items()}

    def load_from_dict(self, data: dict[str, Any]) -> None:
        added = data.get("added_tokens", [])
        for tok_item in added:
            tok_content = tok_item["content"]
            tok_id = tok_item["id"]
            if tok_content not in self.special_tokens:
                self.special_tokens.append(tok_content)
            self.special_token_map[tok_content] = tok_id

        model_dict = data.get("model", {})
        self.vocab = dict(model_dict.get("vocab", {}))
        for tok, idx in self.special_token_map.items():
            self.vocab[tok] = idx

        self.inverse_vocab = {int(idx): tok for tok, idx in self.vocab.items()}

        raw_merges = model_dict.get("merges", [])
        self.merges = []
        self.bpe_ranks = {}
        for rank, m in enumerate(raw_merges):
            if isinstance(m, str):
                parts = m.strip().split()
                if len(parts) == 2:
                    pair = (parts[0], parts[1])
                    self.merges.append(pair)
                    self.bpe_ranks[pair] = rank
            elif isinstance(m, list) and len(m) == 2:
                pair = (m[0], m[1])
                self.merges.append(pair)
                self.bpe_ranks[pair] = rank

    def get_vocab_size(self) -> int:
        return len(self.vocab)

    def _bpe(self, token: str) -> list[str]:
        if token in self.cache:
            return self.cache[token]

        word = list(token)
        pairs = set(zip(word[:-1], word[1:]))

        if not pairs:
            return [token]

        while True:
            min_rank = float("inf")
            bigram = None
            for p in pairs:
                rank = self.bpe_ranks.get(p, float("inf"))
                if rank < min_rank:
                    min_rank = rank
                    bigram = p

            if bigram is None or bigram not in self.bpe_ranks:
                break

            first, second = bigram
            new_word: list[str] = []
            i = 0
            while i < len(word):
                if i < len(word) - 1 and word[i] == first and word[i + 1] == second:
                    new_word.append(first + second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            word = new_word
            if len(word) == 1:
                break
            pairs = set(zip(word[:-1], word[1:]))

        self.cache[token] = word
        return word

    def encode(self, text: str) -> list[int]:
        if not text:
            return []

        # Split around special tokens preserving them
        pattern = "(" + "|".join(re.escape(tok) for tok in self.special_tokens) + ")"
        parts = re.split(pattern, text)

        token_ids: list[int] = []
        for part in parts:
            if not part:
                continue
            if part in self.special_token_map:
                token_ids.append(self.special_token_map[part])
                continue

            # Convert utf-8 bytes of string to unicode chars
            byte_encoded = "".join(self.byte_encoder[b] for b in part.encode("utf-8"))
            bpe_tokens = self._bpe(byte_encoded)

            for bpe_tok in bpe_tokens:
                if bpe_tok in self.vocab:
                    token_ids.append(self.vocab[bpe_tok])
                else:
                    # Fallback to individual byte chars
                    for ch in bpe_tok:
                        token_ids.append(self.vocab.get(ch, self.special_token_map.get("<|unk|>", 10)))

        return token_ids

    def decode(self, token_ids: list[int], skip_special_tokens: bool = False) -> str:
        special_ids = set(self.special_token_map.values())
        chars: list[str] = []

        for tid in token_ids:
            if tid in special_ids:
                if not skip_special_tokens:
                    chars.append(self.inverse_vocab.get(tid, ""))
            else:
                tok_str = self.inverse_vocab.get(tid, "")
                chars.append(tok_str)

        all_text = "".join(chars)
        # Decode byte-level unicode back to utf-8 string
        out_bytes = bytearray()
        i = 0
        while i < len(all_text):
            ch = all_text[i]
            # Check if this character is part of a special token string
            found_special = False
            for sp_tok in self.special_tokens:
                if all_text[i:].startswith(sp_tok):
                    out_bytes.extend(sp_tok.encode("utf-8"))
                    i += len(sp_tok)
                    found_special = True
                    break
            if not found_special:
                if ch in self.byte_decoder:
                    out_bytes.append(self.byte_decoder[ch])
                else:
                    out_bytes.extend(ch.encode("utf-8"))
                i += 1

        return out_bytes.decode("utf-8", errors="replace")

    def train_from_texts(self, texts: list[str], vocab_size: int = 2048) -> None:
        self._init_base_vocab()
        word_counts: dict[str, int] = {}
        for text in texts:
            clean = text
            for st in self.special_tokens:
                clean = clean.replace(st, " ")
            byte_encoded = "".join(self.byte_encoder[b] for b in clean.encode("utf-8"))
            for w in byte_encoded.split():
                if w:
                    word_counts[w] = word_counts.get(w, 0) + 1

        splits: dict[str, list[str]] = {w: list(w) for w in word_counts}

        # Build initial pair counts and pair-to-word index
        pair_counts: dict[tuple[str, str], int] = {}
        pair_to_words: dict[tuple[str, str], set[str]] = {}
        for w, freq in word_counts.items():
            symbols = splits[w]
            for p in zip(symbols[:-1], symbols[1:]):
                pair_counts[p] = pair_counts.get(p, 0) + freq
                pair_to_words.setdefault(p, set()).add(w)

        while len(self.vocab) < vocab_size and pair_counts:
            best_pair = max(pair_counts, key=pair_counts.get)
            if pair_counts[best_pair] < 1:
                break

            del pair_counts[best_pair]
            new_token = best_pair[0] + best_pair[1]
            if new_token not in self.vocab:
                self.vocab[new_token] = len(self.vocab)
                self.inverse_vocab[len(self.inverse_vocab)] = new_token
                self.merges.append(best_pair)
                self.bpe_ranks[best_pair] = len(self.bpe_ranks)

            # Update only affected words
            affected_words = list(pair_to_words.get(best_pair, []))
            for w in affected_words:
                freq = word_counts[w]
                old_symbols = splits[w]
                # Remove old pairs
                for p in zip(old_symbols[:-1], old_symbols[1:]):
                    if p in pair_counts:
                        pair_counts[p] -= freq
                        if pair_counts[p] <= 0:
                            del pair_counts[p]

                # Merge
                new_symbols: list[str] = []
                i = 0
                while i < len(old_symbols):
                    if i < len(old_symbols) - 1 and old_symbols[i] == best_pair[0] and old_symbols[i + 1] == best_pair[1]:
                        new_symbols.append(new_token)
                        i += 2
                    else:
                        new_symbols.append(old_symbols[i])
                        i += 1
                splits[w] = new_symbols

                # Add new pairs
                for p in zip(new_symbols[:-1], new_symbols[1:]):
                    pair_counts[p] = pair_counts.get(p, 0) + freq
                    pair_to_words.setdefault(p, set()).add(w)


class NairaTokenizer:
    """Tokenizer tailored for NairaLLM operations."""

    def __init__(self, tokenizer_file: str | Path | None = None) -> None:
        self.special_tokens = list(SPECIAL_TOKENS)
        self.special_token_map = {tok: idx for idx, tok in enumerate(self.special_tokens)}
        self._tokenizer: Any = None
        self._pure_bpe: PurePythonBpeTokenizer | None = None

        if tokenizer_file is None:
            default_path = Path(__file__).resolve().parent / "naira_tokenizer.json"
            if default_path.exists():
                tokenizer_file = default_path

        if tokenizer_file is not None and Path(tokenizer_file).exists():
            self.load(tokenizer_file)
        else:
            self._init_default_tokenizer()

    def _init_default_tokenizer(self) -> None:
        """Initialize base BPE tokenizer structure."""
        if _HAS_TOKENIZERS_LIB:
            tokenizer = Tokenizer(models.BPE(unk_token="<|unk|>"))
            tokenizer.normalizer = normalizers.Sequence([normalizers.NFKC()])
            tokenizer.pre_tokenizer = pre_tokenizers.Sequence([
                pre_tokenizers.ByteLevel(add_prefix_space=False),
            ])
            tokenizer.decoder = decoders.ByteLevel()
            self._tokenizer = tokenizer
        else:
            self._pure_bpe = PurePythonBpeTokenizer(self.special_tokens)

    def train_on_corpus(
        self,
        texts: list[str],
        vocab_size: int = 4096,
        min_frequency: int = 1,
    ) -> None:
        """Train tokenizer on in-memory text samples."""
        if _HAS_TOKENIZERS_LIB:
            trainer = trainers.BpeTrainer(
                vocab_size=vocab_size,
                min_frequency=min_frequency,
                special_tokens=self.special_tokens,
                initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
            )
            self._tokenizer.train_from_iterator(texts, trainer=trainer)
        else:
            if self._pure_bpe is None:
                self._pure_bpe = PurePythonBpeTokenizer(self.special_tokens)
            self._pure_bpe.train_from_texts(texts, vocab_size=vocab_size)

    def encode(self, text: str) -> list[int]:
        """Encode a string into token IDs."""
        if _HAS_TOKENIZERS_LIB and self._tokenizer is not None:
            encoding = self._tokenizer.encode(text)
            return list(encoding.ids)
        elif self._pure_bpe is not None:
            return self._pure_bpe.encode(text)
        raise RuntimeError("Tokenizer is not initialized.")

    def decode(self, token_ids: list[int], skip_special_tokens: bool = False) -> str:
        """Decode token IDs back to a string."""
        if _HAS_TOKENIZERS_LIB and self._tokenizer is not None:
            return self._tokenizer.decode(token_ids, skip_special_tokens=skip_special_tokens)
        elif self._pure_bpe is not None:
            return self._pure_bpe.decode(token_ids, skip_special_tokens=skip_special_tokens)
        raise RuntimeError("Tokenizer is not initialized.")

    @property
    def vocab_size(self) -> int:
        """Return the total vocabulary size."""
        if _HAS_TOKENIZERS_LIB and self._tokenizer is not None:
            return self._tokenizer.get_vocab_size()
        elif self._pure_bpe is not None:
            return self._pure_bpe.get_vocab_size()
        return len(self.special_tokens)

    @property
    def pad_token_id(self) -> int:
        return self.special_token_map["<|pad|>"]

    @property
    def eos_token_id(self) -> int:
        return self.special_token_map["<|endoftext|>"]

    def save(self, file_path: str | Path) -> None:
        """Save tokenizer configuration and vocabulary to JSON."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if _HAS_TOKENIZERS_LIB and self._tokenizer is not None:
            self._tokenizer.save(str(path))
        elif self._pure_bpe is not None:
            data = {
                "version": "1.0",
                "added_tokens": [
                    {"id": idx, "content": tok, "special": True} for tok, idx in self.special_token_map.items()
                ],
                "model": {
                    "type": "BPE",
                    "vocab": self._pure_bpe.vocab,
                    "merges": [" ".join(p) for p in self._pure_bpe.merges],
                },
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        _LOG.info("NairaTokenizer saved to %s (vocab=%d)", path, self.vocab_size)

    def load(self, file_path: str | Path) -> None:
        """Load tokenizer from JSON file."""
        path = Path(file_path)
        if _HAS_TOKENIZERS_LIB:
            try:
                self._tokenizer = Tokenizer.from_file(str(path))
                _LOG.info("NairaTokenizer loaded via tokenizers lib from %s (vocab=%d)", path, self.vocab_size)
                return
            except Exception:
                pass

        # Pure Python fallback loader
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._pure_bpe = PurePythonBpeTokenizer(self.special_tokens)
        self._pure_bpe.load_from_dict(data)
        _LOG.info("NairaTokenizer loaded via PurePythonBPE from %s (vocab=%d)", path, self.vocab_size)
