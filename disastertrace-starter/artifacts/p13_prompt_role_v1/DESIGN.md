# DeepSeek prompt-role placement development study

P9 has already completed and scored1/1542 on the common system-contract native
task,with substantial coordinate-unit violations and556 unattempted slots after
context failures. P11 is generating at registration;its model scores have not
been read. P12 is offline-accepted but has not generated at registration. This
new study is motivated by known P9 failures and the previously archived official
DeepSeek model-card recommendation to avoid a system prompt and put instructions
in the user prompt. It is not a heldout test or an optimized-model leaderboard.

## Registered intervention

Use only the pinned DeepSeek-R1-Distill-Qwen-7B checkpoint. Compare against its
planned P12 default-JSON-spacing track on the unchanged P10 six-storm task:
804 checkpoints,three methods,repeat0,2412 answers,two one-H100 workers with1206
slots each. Preserve whole-target ownership,seeds,raw evidence,Gold,scorer,static
output schema,default JSON spacing,native reasoning parser,BF16,TP1,batch4,
context32768,output8192,temp0.6,top_p0.95,top_k20 and the existing stop policy.

The only prompt change is deterministic role placement. Starting from the same
logical two-message request,render one user message with content exactly:

    original_system_content + "\n\n" + original_user_content

Apply the pinned native chat template to that one user message. Do not add new
instructions,examples,source IDs,reference answers,unit hints or response repair.
The benchmark contract text is byte-identical,and the evidence/carrier JSON
suffix is byte-identical. Relative token placement and template tokens change;
this is a protocol intervention,not a token-length-matched comparison.

Every prepared request retains the original logical messages for source-policy
reconstruction and separately records rendered_messages,its hash,the actual
template prompt and exact prompt token IDs. The live backend consumes only those
verified prompt IDs. Diagnostics resolve the unchanged logical task;they are not
LLM answers. Tests must prove exact contract/evidence preservation and actual
single-user template rendering for the installed tokenizer.

Register a distinct prompt_role_live namespace,execution schema,model origin,
one-use claims and request identities. Never mutate frozen adapter globals or
reuse P9/P11/P12 model captures. P13 generations feed only P13 histories.

## Budget and release ordering

At most2412 new answers and19759104 reserved output tokens,two full H100s,zero
model/platform retries. Global pending plus running allocations remain at most4.
One fresh no-generation hardware preflight is permitted after the P12 submission
controller has finished and capacity is available. Full diagnostics,installed
backend checks,independent audit and CPU relocation precede live dispatch.

The live controller waits for both P12 DeepSeek jobs to release and its own
preflight to pass/release. It may overlap the still-running P12 Qwen jobs if the
complete owned-job capacity listing permits two more GPUs. Maximum live duration
is4 hours,capped by2026-09-09T02:05:16.104344+00:00. If fewer than30 minutes remain
before dispatch,retain an honest offline-only result. A started phase keeps every
planned slot in its denominator even if the deadline or context guard stops it.
There is no paid API,training,new model acquisition,heldout inference,human Gold
or LLM judge. The user's existing ten-hour/four-H100 authorization covers this
separately bounded development experiment.

## Interpretation

Report coverage,strict scores,unit/time/value/citation components,format and
length failures,whitespace,tokens,allocation time and single-repeat whole-target
success. Compare on the complete same2412 source slots,by method and storm.
Original histories diverge through each run's own answers;the comparison is of
full trajectories,not a shared-prefix causal effect. Do not normalize units or
rescore old outputs. A benefit would support this specific prompt placement
under the retained settings,not universal DeepSeek superiority or full compliance
with every model-card recommendation. A null or negative result is retained.

The whole-worker failure policy remains a limitation. Arbitrary output strings,
incomplete reasoning and context growth are still possible despite bounded
formatting whitespace. Record these separately from observed semantic errors.
