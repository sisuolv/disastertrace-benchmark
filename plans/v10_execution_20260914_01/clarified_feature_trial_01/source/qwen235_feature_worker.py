"""Four-H100 tensor-parallel inference on the exact frozen feature/F packets."""

import argparse
import datetime as dt
import hashlib
import json
import os
import socket
import time
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def save(path,value):
    with path.open("x") as handle:
        json.dump(value,handle,sort_keys=True,allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(16*1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def main():
    import torch
    import transformers
    import vllm
    from transformers import AutoTokenizer
    from vllm import LLM,SamplingParams

    parser=argparse.ArgumentParser()
    parser.add_argument("--batch",type=Path,required=True)
    args=parser.parse_args()
    batch=args.batch
    plan=read(batch/"PLAN.json")
    out=batch/"worker_0"
    out.mkdir(exist_ok=False)
    save(out/"STARTED.json",{"hostname":socket.gethostname(),"pid":os.getpid(),"plan_sha256":digest(batch/"PLAN.json"),"rank":0})
    versions={"torch":torch.__version__.split("+")[0],"transformers":transformers.__version__,"vllm":vllm.__version__}
    qualification=read(batch/"QUALIFICATION.json")
    if versions!=qualification["runtime_versions"] or torch.cuda.device_count()!=4:
        raise ValueError("Four-H100 qualified runtime required")
    devices=[{"name":torch.cuda.get_device_properties(i).name,"memory_bytes":torch.cuda.get_device_properties(i).total_memory} for i in range(4)]
    if any("H100" not in d["name"] for d in devices):
        raise ValueError("Wrong GPU device")
    for rel,sha in qualification["frozen_files"].items():
        if digest(batch/rel)!=sha:
            raise ValueError("Frozen GPU code/input changed")
    manifest=read(batch/"MODEL_MANIFEST.json")
    for item in manifest["files"]:
        path=Path(manifest["directory"])/item["path"]
        if path.stat().st_size!=item["bytes"] or digest(path)!=item["sha256"]:
            raise ValueError("Local model bytes changed")
    save(batch/"WORKER_PREFLIGHT.json",{"verified_model_files":[r["path"] for r in manifest["files"]],"source_and_input_bindings_pass":True})
    save(out/"HARDWARE.json",{"name":devices[0]["name"],"gpus":devices,"versions":versions,"tensor_parallel_size":4})
    tokenizer=AutoTokenizer.from_pretrained(plan["model_directory"],local_files_only=True,trust_remote_code=False)
    torch.set_num_threads(4)
    started=time.perf_counter()
    llm=LLM(model=plan["model_directory"],tokenizer=plan["model_directory"],tensor_parallel_size=4,
        dtype="auto",quantization="fp8",trust_remote_code=False,seed=plan["generation"]["seed"],**plan["engine"])
    save(out/"MODEL_LOADED.json",{"seconds":time.perf_counter()-started,"model":plan["model"]})
    eos=read(Path(plan["model_directory"])/"generation_config.json")["eos_token_id"]
    eos=eos if isinstance(eos,list) else [eos]
    deadline=dt.datetime.fromisoformat(plan["last_worker_time"])

    def invoke(rows,cap):
        if dt.datetime.now(dt.timezone.utc)>=deadline:
            raise TimeoutError("Frozen local collection deadline reached")
        start_ns,begin=time.time_ns(),time.perf_counter()
        prompts,requests=[],[]
        for row in rows:
            cid=row["call_id"]
            messages=row["messages"]
            ids=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False)
            if len(ids)>plan["input_token_cap"] or len(ids)+cap>plan["engine"]["max_model_len"]:
                raise ValueError("Frozen token/context bound exceeded")
            request={"call_id":cid,"messages":messages,"input_ids":ids,"max_new_tokens":cap,
                     "wall_started_ns":start_ns,"batch_size":len(rows),"template":"thinking_disabled"}
            save(out/(cid+".request.json"),request)
            requests.append(request)
            prompts.append({"prompt_token_ids":ids})
        generated_at=time.perf_counter()
        outputs=llm.generate(prompts,SamplingParams(temperature=0,max_tokens=cap,seed=plan["generation"]["seed"]),use_tqdm=False)
        generation_seconds=time.perf_counter()-generated_at
        if len(outputs)!=len(rows):
            raise ValueError("Original local batch has missing responses")
        results=[]
        for request,output in zip(requests,outputs,strict=True):
            cid=request["call_id"]
            answer=output.outputs[0]
            ids=list(answer.token_ids)
            ended=answer.finish_reason=="stop" and ((ids and ids[-1] in eos) or answer.stop_reason in eos)
            response={"call_id":cid,"raw":answer.text,"output_ids":ids,"input_tokens":len(request["input_ids"]),
                "output_tokens":len(ids),"seconds":generation_seconds,"ended_with_eos":bool(ended),
                "finish_reason":answer.finish_reason,"stop_reason":answer.stop_reason,
                "request_sha256":digest(out/(cid+".request.json")),"wall_returned_ns":time.time_ns()}
            save(out/(cid+".response.json"),response)
            save(out/(cid+".publication.json"),{"call_id":cid,"response_sha256":digest(out/(cid+".response.json")),
                "lifecycle_started_ns":start_ns,"published_observed_ns":time.time_ns(),
                "lifecycle_seconds":time.perf_counter()-begin,"generation_seconds":generation_seconds,
                "scope":"whole TP4 batch prompt preparation through this durable response; shared elapsed is not additive compute"})
            results.append(response)
        return results

    smoke=invoke([{"call_id":"compatibility","messages":[{"role":"user","content":"Return exactly READY."}]}],16)[0]
    if smoke["raw"].strip().rstrip(".")!="READY" or not smoke["ended_with_eos"]:
        raise ValueError("Original compatibility failed; no benchmark requests")
    completed=[]
    for index in range(0,len(plan["tasks"]),plan["batch_size"]):
        tasks=plan["tasks"][index:index+plan["batch_size"]]
        policies=[]
        for task in tasks:
            path=batch/"policy"/(task["call_id"]+".json")
            if digest(path)!=task["policy_sha256"]:
                raise ValueError("Registered policy changed")
            policies.append(read(path))
        responses=invoke(policies,plan["max_tokens"])
        completed.extend(r["call_id"] for r in responses)
        print(json.dumps({"completed":len(completed),"registered":len(plan["tasks"])}),flush=True)
    save(out/"COMPLETE.json",{"benchmark_calls":len(completed),"compatibility_calls":1,"completed_call_ids":completed})
    save(batch/"WORKERS_EXIT.json",{"exit_codes":[0],"all_workers_complete":True,"tensor_parallel_gpus":4})


if __name__=="__main__":
    main()
