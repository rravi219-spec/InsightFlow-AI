"""Explicitly provisioned small CPU model; no hosted inference or tools."""
import os
import json
from itertools import combinations
from functools import lru_cache

from rag.config import ROOT

MODEL = "HuggingFaceTB/SmolLM2-360M-Instruct"
REVISION = "a10cc1512eabd3dde888204e902eca88bddb4951"
MODEL_DIR = ROOT / "data/generation_models" / REVISION


def download():
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL, revision=REVISION, local_dir=str(MODEL_DIR), token=False,
        allow_patterns=["model.safetensors", "config.json", "generation_config.json", "tokenizer.json",
                        "tokenizer_config.json", "special_tokens_map.json", "vocab.json", "merges.txt"])


class LocalLLM:
    def __init__(self):
        if not (MODEL_DIR / "model.safetensors").is_file():
            raise FileNotFoundError("Run python -m rag.local_llm --download before asking questions")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.set_num_threads(4)
        self.tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), local_files_only=True, trust_remote_code=False)
        self.model = AutoModelForCausalLM.from_pretrained(str(MODEL_DIR), local_files_only=True,
            trust_remote_code=False, use_safetensors=True, dtype=torch.float32).eval()

    def __call__(self, messages):
        import torch
        inputs = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
            return_tensors="pt", return_dict=True)
        if inputs["input_ids"].shape[-1] > 3000:
            raise ValueError("Grounded context exceeds local model budget")
        # Constrained JSON decoding limits the small model to evidence IDs supplied
        # by the chain, including an empty selection for abstention. No factual
        # text, command, path or citation can be authored in this output channel.
        evidence_ids = [entry["id"] for entry in json.loads(messages[-1]["content"])["EVIDENCE"]]
        trie = {}
        for count in range(4):
            for selection in combinations(evidence_ids, count):
                encoded = self.tokenizer.encode(json.dumps({"evidence": list(selection)}), add_special_tokens=False)
                node = trie
                for token in encoded + [self.tokenizer.eos_token_id]:
                    node = node.setdefault(token, {})
        prompt_length = inputs["input_ids"].shape[-1]
        def allowed_tokens(batch_id, token_ids):
            node = trie
            for token in token_ids[prompt_length:].tolist():
                node = node[token]
            return list(node) or [self.tokenizer.eos_token_id]
        with torch.inference_mode():
            output = self.model.generate(**inputs, do_sample=False, max_new_tokens=80,
                prefix_allowed_tokens_fn=allowed_tokens,
                pad_token_id=self.tokenizer.eos_token_id, use_cache=True)
        return self.tokenizer.decode(output[0, inputs["input_ids"].shape[-1]:], skip_special_tokens=True)


@lru_cache(maxsize=1)
def local_llm():
    return LocalLLM()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", required=True)
    parser.parse_args()
    download()
