"""
Inference Engine and Runtime for NairaLLM.

Handles autoregressive token generation, temperature, top-p/top-k sampling,
structured tool call parsing, and high-level conversational interfaces.
Supports both PyTorch and pure-NumPy backends.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
import numpy as np

from NairaLLM.model.architecture.naira_transformer import NairaTransformer
from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.runtime.numpy_backend import NumpyNairaModel
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer

try:
    import torch
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

_LOG = logging.getLogger("nairallm.runtime")


class NairaRuntime:
    """High-level runtime for NairaLLM inference with dual PyTorch/NumPy backend support."""

    def __init__(
        self,
        model: NairaTransformer | NumpyNairaModel | None = None,
        tokenizer: NairaTokenizer | None = None,
        checkpoint_path: str | Path | None = None,
        device: str = "cpu",
    ) -> None:
        self.device = device
        self.tokenizer = tokenizer or NairaTokenizer(Path("NairaLLM/model/tokenizer/naira_tokenizer.json"))

        if checkpoint_path is not None and Path(checkpoint_path).exists():
            self.load_checkpoint(checkpoint_path)
        elif model is not None:
            self.model = model
            self.config = model.config
        else:
            self.config = NairaModelConfig(vocab_size=self.tokenizer.vocab_size)
            if _HAS_TORCH:
                self.model = NairaTransformer(self.config).to(self.device)
            else:
                self.model = NumpyNairaModel(self.config)

    def load_checkpoint(self, checkpoint_path: str | Path) -> None:
        """Load trained model weights and configuration."""
        path = Path(checkpoint_path)
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {path}")

        self.checkpoint_path = str(path)

        if path.suffix == ".npz":
            npz_data = np.load(str(path))
            weights = {k: npz_data[k] for k in npz_data.files}
            meta_path = path.parent / f"{path.stem}_metadata.json"
            loaded_config = None
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)
                    if "model_config" in meta_data:
                        loaded_config = NairaModelConfig.from_dict(meta_data["model_config"])
                except Exception:
                    pass

            if loaded_config is not None:
                self.config = loaded_config
            else:
                d_model = weights["tok_embeddings"].shape[1]
                vocab_size = weights["tok_embeddings"].shape[0]
                num_layers = sum(1 for k in weights if k.startswith("layer_") and k.endswith("_attn_norm"))
                d_ff = weights[f"layer_0_w1"].shape[1] if "layer_0_w1" in weights else d_model * 2
                d_head = 32 if d_model % 32 == 0 else d_model
                num_heads = max(1, d_model // d_head)
                self.config = NairaModelConfig(
                    vocab_size=vocab_size,
                    d_model=d_model,
                    num_layers=num_layers,
                    num_heads=num_heads,
                    num_kv_heads=num_heads,
                    d_ff=d_ff,
                )
            self.model = NumpyNairaModel(self.config, weights=weights)
            self.backend = "NumPy"
            _LOG.info(
                "Loaded NairaLLM NumPy checkpoint from %s (d_model=%d, layers=%d, heads=%d, vocab=%d)",
                path.name,
                self.config.d_model,
                self.config.num_layers,
                self.config.num_heads,
                self.config.vocab_size,
            )
        elif path.suffix in [".pt", ".bin"]:
            if not _HAS_TORCH:
                raise RuntimeError(f"PyTorch is required to load PyTorch .pt checkpoint: {path}")
            checkpoint = torch.load(str(path), map_location=self.device)
            config_dict = checkpoint.get("model_config", checkpoint.get("config", {}))
            self.config = NairaModelConfig.from_dict(config_dict)
            self.model = NairaTransformer(self.config).to(self.device)
            state_dict = checkpoint.get("model_state_dict", checkpoint)
            self.model.load_state_dict(state_dict, strict=False)
            self.model.eval()
            self.backend = "PyTorch"
            _LOG.info("Loaded NairaLLM PyTorch checkpoint from %s (params=%d)", path.name, self.model.count_parameters())
        else:
            raise ValueError(f"Unsupported checkpoint format: {path.suffix}")

    def save_checkpoint(self, checkpoint_path: str | Path) -> None:
        """Save model checkpoint to disk."""
        path = Path(checkpoint_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if _HAS_TORCH and isinstance(self.model, NairaTransformer):
            torch.save(
                {
                    "config": self.config.to_dict(),
                    "model_state_dict": self.model.state_dict(),
                    "vocab_size": self.tokenizer.vocab_size,
                },
                str(path),
            )
            _LOG.info("Saved NairaLLM checkpoint to %s", path)

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 128,
        temperature: float = 0.0,
        top_p: float = 0.9,
        top_k: int = 40,
        stop_tokens: list[str] | None = None,
    ) -> str:
        """Generate response string from input prompt."""
        if _HAS_TORCH and isinstance(self.model, NairaTransformer):
            return self._generate_torch(prompt, max_new_tokens, temperature, top_p, top_k, stop_tokens)
        elif isinstance(self.model, NumpyNairaModel):
            return self._generate_numpy(prompt, max_new_tokens, temperature, stop_tokens)
        else:
            raise RuntimeError("No compatible model backend found.")

    def _generate_torch(
        self,
        prompt: str,
        max_new_tokens: int = 128,
        temperature: float = 0.0,
        top_p: float = 0.9,
        top_k: int = 40,
        stop_tokens: list[str] | None = None,
    ) -> str:
        self.model.eval()
        stop_token_ids = {self.tokenizer.eos_token_id}
        if stop_tokens:
            for st in stop_tokens:
                encoded = self.tokenizer.encode(st)
                if len(encoded) == 1:
                    stop_token_ids.add(encoded[0])

        input_ids = self.tokenizer.encode(prompt)
        input_tensor = torch.tensor([input_ids], dtype=torch.long, device=self.device)

        generated_ids: list[int] = []

        with torch.no_grad():
            for _ in range(max_new_tokens):
                curr_input = input_tensor[:, -min(input_tensor.shape[1], self.config.max_seq_len) :]
                logits, _, _ = self.model(curr_input)
                next_token_logits = logits[0, -1, :]

                if temperature <= 1e-4:
                    next_token_id = int(torch.argmax(next_token_logits).item())
                else:
                    scaled_logits = next_token_logits / temperature
                    if top_k > 0:
                        v, _ = torch.topk(scaled_logits, min(top_k, scaled_logits.size(-1)))
                        scaled_logits[scaled_logits < v[-1]] = float("-inf")
                    if top_p < 1.0:
                        sorted_logits, sorted_indices = torch.sort(scaled_logits, descending=True)
                        cumulative_probs = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
                        sorted_indices_to_remove = cumulative_probs > top_p
                        sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                        sorted_indices_to_remove[..., 0] = False
                        indices_to_remove = sorted_indices[sorted_indices_to_remove]
                        scaled_logits[indices_to_remove] = float("-inf")

                    probs = torch.softmax(scaled_logits, dim=-1)
                    next_token_id = int(torch.multinomial(probs, num_samples=1).item())

                if next_token_id in stop_token_ids:
                    break

                generated_ids.append(next_token_id)
                input_tensor = torch.cat(
                    [input_tensor, torch.tensor([[next_token_id]], dtype=torch.long, device=self.device)],
                    dim=1,
                )

        return self.tokenizer.decode(generated_ids, skip_special_tokens=False)

    def _generate_numpy(
        self,
        prompt: str,
        max_new_tokens: int = 128,
        temperature: float = 0.0,
        stop_tokens: list[str] | None = None,
    ) -> str:
        stop_token_ids = {self.tokenizer.eos_token_id, 1}
        if stop_tokens:
            for st in stop_tokens:
                encoded = self.tokenizer.encode(st)
                if len(encoded) == 1:
                    stop_token_ids.add(encoded[0])

        input_ids = self.tokenizer.encode(prompt)
        generated_ids: list[int] = []

        for _ in range(max_new_tokens):
            curr_input = (input_ids + generated_ids)[-self.config.max_seq_len :]
            logits = self.model.forward(curr_input, last_only=True)
            next_logits = logits[-1, :].copy()

            # Apply repetition penalty to recently generated tokens
            for prev_id in set(generated_ids[-16:]):
                if next_logits[prev_id] > 0:
                    next_logits[prev_id] /= 1.4
                else:
                    next_logits[prev_id] *= 1.4

            if temperature <= 1e-4:
                next_token_id = int(np.argmax(next_logits))
            else:
                scaled = next_logits / max(1e-4, temperature)
                exp_l = np.exp(scaled - np.max(scaled))
                probs = exp_l / np.sum(exp_l)
                next_token_id = int(np.random.choice(len(probs), p=probs))

            if next_token_id in stop_token_ids:
                break

            generated_ids.append(next_token_id)

            # Check if stop sequence is formed in text periodically
            if len(generated_ids) % 4 == 0 or next_token_id < 30:
                decoded_so_far = self.tokenizer.decode(generated_ids, skip_special_tokens=False)
                if "<|user|>" in decoded_so_far or "<|system|>" in decoded_so_far or "<|endoftext|>" in decoded_so_far:
                    break

        return self.tokenizer.decode(generated_ids, skip_special_tokens=False)

    def extract_intent(self, text: str) -> str | None:
        """Extract high-level intent from generated text."""
        match = re.search(r"<\|intent\|>\s*([a-zA-Z0-9_-]+)", text)
        if match:
            return match.group(1).strip()
        return None

    def extract_plan(self, text: str) -> str | None:
        """Extract multi-step plan from generated text."""
        match = re.search(r"<\|plan\|>\s*(.*?)(?=(?:<\||$))", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def extract_verification(self, text: str) -> str | None:
        """Extract verification rationale or check from generated text."""
        match = re.search(r"<\|verify\|>\s*(.*?)(?=(?:<\||$))", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def extract_final_response(self, text: str) -> str | None:
        """Extract final user-facing response from generated text."""
        match = re.search(r"<\|final\|>\s*(.*?)(?=(?:<\||$))", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def extract_tool_calls(self, text: str) -> list[dict[str, Any]]:
        """Extract structured tool calls from generated text across formats."""
        tool_calls: list[dict[str, Any]] = []

        # Format 1: Structured cognition <|tool_call|>\ntool_name\n{json_args}
        pattern_structured = re.findall(
            r"<\|tool_call\|>\s*([a-zA-Z0-9_]+)\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})(?=(?:<\||$))",
            text,
            re.DOTALL,
        )
        for tool_name, args_str in pattern_structured:
            try:
                args = json.loads(args_str.strip())
                if isinstance(args, dict):
                    tool_calls.append({"name": tool_name.strip(), "arguments": args})
            except json.JSONDecodeError:
                tool_calls.append({"name": tool_name.strip(), "arguments": {}})

        # Format 2: Single JSON object <|tool_call|>\n{"name": "...", "arguments": ...}
        if not tool_calls:
            pattern_control = re.findall(r"<\|tool_call\|>\s*(\{.*?\})(?=(?:<\||$))", text, re.DOTALL)
            for match in pattern_control:
                try:
                    parsed = json.loads(match.strip())
                    if isinstance(parsed, dict) and "name" in parsed:
                        tool_calls.append(parsed)
                except json.JSONDecodeError:
                    pass

        # Format 3: Tool name only <|tool_call|>\ntool_name
        if not tool_calls:
            pattern_name_only = re.findall(r"<\|tool_call\|>\s*([a-zA-Z0-9_]+)(?=(?:\s*<\||$))", text)
            for tool_name in pattern_name_only:
                if tool_name.strip() and not tool_name.strip().startswith("{"):
                    tool_calls.append({"name": tool_name.strip(), "arguments": {}})

        # Format 4: Markdown JSON fallback
        if not tool_calls:
            pattern_json = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            for match in pattern_json:
                try:
                    parsed = json.loads(match.strip())
                    if isinstance(parsed, dict) and "name" in parsed:
                        tool_calls.append(parsed)
                except json.JSONDecodeError:
                    pass

        return tool_calls
