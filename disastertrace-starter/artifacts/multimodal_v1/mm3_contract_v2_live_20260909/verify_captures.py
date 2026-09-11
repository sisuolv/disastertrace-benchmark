"""CPU-only replay of captured image inputs and tokenizer output decoding."""

import argparse
from pathlib import Path

from transformers import AutoProcessor

from disastertrace.multimodal_live_v1.adapter import QwenBackend
from disastertrace.multimodal_v1.storage import read, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import torch

    torch.set_num_threads(4)
    root = args.batch.resolve()
    args.output.mkdir(exist_ok=False)
    execution = read(root / "EXECUTION.json")
    processor = AutoProcessor.from_pretrained(execution["model_directory"], local_files_only=True, trust_remote_code=False)
    processor.image_processor.size = {"shortest_edge": 65536, "longest_edge": 1048576}
    backend = QwenBackend(processor, None, execution["settings"])
    rows = []
    for trajectory in read(root / "REQUEST_PLAN.json")["trajectories"]:
        for i, template in enumerate(trajectory["requests"]):
            slot = root / "gpu_run/live" / trajectory["id"] / f"{i:04d}"
            if not (slot / "intent.json").exists():
                continue
            replay = args.output / trajectory["id"] / f"{i:04d}"
            replay.mkdir(parents=True)
            backend.prepare(read(slot / "request.json"), replay)
            if read(slot / "processor.json") != read(replay / "processor.json"):
                raise ValueError("processor/input tensors differ on CPU replay")
            if (slot / "input_ids.json").read_bytes() != (replay / "input_ids.json").read_bytes():
                raise ValueError("input token sequence differs")
            if (slot / "generation.json").exists():
                generation = read(slot / "generation.json")
                ids = generation["output_ids"]
                text = processor.tokenizer.decode(ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)
                if text.encode() != (slot / "raw.txt").read_bytes():
                    raise ValueError("raw response does not match generated token sequence")
                if generation["finish_reason"] == "eos" and ids[-1] != processor.tokenizer.eos_token_id:
                    raise ValueError("EOS finish does not match last token")
                rows.append({"trajectory": trajectory["id"], "checkpoint": template["checkpoint"],
                             "inputs_equal": True, "decoded_output_equal": True, "output_tokens": len(ids)})
    write(args.output / "VERIFIED.json", {"status": "passed", "generations": 0, "captures": rows})
    print("verified actual processor tensors, input IDs and output decoding:", len(rows))


if __name__ == "__main__":
    main()
