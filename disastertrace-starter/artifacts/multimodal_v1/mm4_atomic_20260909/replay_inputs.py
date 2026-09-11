"""Reconstruct actual public processor tensors and generated-token decoding on CPU."""

import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.batch.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(root / "source/src"))
    import torch
    from transformers import AutoProcessor
    from disastertrace.multimodal_atomic_v1.adapter import AtomicBackend, readability
    from disastertrace.multimodal_v1.storage import read, write

    torch.set_num_threads(4)
    execution = read(root / "EXECUTION.json")
    processor = AutoProcessor.from_pretrained(execution["model_directory"], local_files_only=True, trust_remote_code=False)
    processor.image_processor.size = {"shortest_edge": 65536, "longest_edge": 1048576}
    backend = AtomicBackend(processor, None, execution["settings"])
    rows, checks = [], []
    for worker, ids in read(root / "REQUEST_PLAN.json")["assignments"].items():
        for tid in ids:
            slot = root / "gpu_runs" / worker / "live" / tid
            if not (slot / "intent.json").exists():
                continue
            replay = output / worker / tid
            replay.mkdir(parents=True)
            task = read(slot / "request.json")
            inputs = backend.prepare(task, replay)
            if read(slot / "processor.json") != read(replay / "processor.json"):
                raise ValueError("actual processor/input tensor replay mismatch")
            for name in ["input_ids.json", "prompt.txt", "public_text.json"]:
                if (slot / name).read_bytes() != (replay / name).read_bytes():
                    raise ValueError("captured public input differs: " + name)
            checks.extend(readability(task, inputs, processor, replay))
            decoded = None
            if (slot / "generation.json").exists():
                generation = read(slot / "generation.json")
                ids_out = generation["output_ids"]
                if generation["output_tokens"] != len(ids_out):
                    raise ValueError("output token count mismatch")
                text = processor.tokenizer.decode(ids_out, skip_special_tokens=True, clean_up_tokenization_spaces=False)
                if text.encode() != (slot / "raw.txt").read_bytes():
                    raise ValueError("output token decoding differs from preserved raw")
                if generation["finish_reason"] == "eos" and ids_out[-1] != processor.tokenizer.eos_token_id:
                    raise ValueError("EOS metadata does not match final token")
                decoded = True
            rows.append({"task_id": tid, "worker": worker, "inputs_equal": True,
                         "output_decoding_equal": decoded})
    write(output / "VERIFIED.json", {"status": "passed", "generations": 0,
          "captures": rows, "pixel_checks": checks})
    print("CPU input/output replay passed:", len(rows), "captures;", len(checks), "pixel checks")


if __name__ == "__main__":
    main()
