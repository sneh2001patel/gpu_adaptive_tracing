"""Accepted real cases as serving workloads for run_episode.py (proposal §10 step 6; REPRODUCTION.md).

Each case names its environments, model, server flags, in-server patch (case_server.py) and request body, for the
two sides of its toggle: `bug` (symptom present) and `fixed` (toggle off). Bodies follow the reproduction checks in
this directory; deviations from those checks are listed per case. Standard library only: it runs under the host's
system Python next to run_episode.py.

Rates are provisional (requests or request groups per second) until the symptom check (queue_case_symptoms.sh)
sets them: `healthy_rate` keeps the fixed side healthy with at least 3 requests in flight (the runner's in-flight
latency needs 3 samples), and `incident_rate` is the load at which the case's symptom is compared.
"""
import base64
import struct
import zlib

COMMON_ARGS = '--disable-log-requests'

CASES = {
    '6240': dict(
        title='FP8 CUTLASS GEMM slower than torch._scaled_mm on Ada', reference='kernel_hotspot:gemm',
        model='neuralmagic/Meta-Llama-3-8B-Instruct-FP8', env='v051', version='0.5.1',
        server_args='--max-model-len 4096 --gpu-memory-utilization 0.85',
        configs={'bug': {}, 'fixed': dict(patch='6240_cutlass_off')},  # effect of fix PR #6384 on SM89
        healthy_rate=0.3, incident_rate=1.0),
    '7619': dict(
        title='Block manager v2 recomputes a shared prefix on warm-up', reference='vocabulary_gap:redundant_prefill',
        model='neuralmagic/Meta-Llama-3-8B-Instruct-FP8', env='v055', version='0.5.5',
        server_args='--max-model-len 8192 --enable-prefix-caching --enforce-eager --trust-remote-code',
        configs={'bug': dict(extra_args='--use-v2-block-manager'), 'fixed': {}},  # fixed: block manager v1
        group_size=32, healthy_rate=0.03, incident_rate=0.1),  # rates in groups/s; one fresh prefix per group
    '3087': dict(
        title='Logits processors deep-copied per request', reference='host_bound',
        model='TinyLlama/TinyLlama-1.1B-Chat-v1.0',
        server_args='--max-model-len 2048 --gpu-memory-utilization 0.9',
        configs={'bug': dict(env='v032', version='0.3.2', patch='3087_json_processor'),
                 'fixed': dict(env='v033', version='0.3.3', patch='3087_json_processor')},
        healthy_rate=0.5, incident_rate=1.0,
        min_latency_samples=1),  # step 6: fewer than 3 requests in flight at 0.75 s latency, so no p95_base at 3
    '25418': dict(
        title='Per-request mm_processor_kwargs rebuild the HF processor', reference='host_bound',
        model='Qwen/Qwen2.5-VL-3B-Instruct', env='v0110', version='0.11.0',
        server_args='--max-model-len 8192 --gpu-memory-utilization 0.9 --limit-mm-per-prompt {"image":1}',
        configs={'bug': dict(mm_kwargs=True), 'fixed': dict(mm_kwargs=False)},  # workload toggle (REPRODUCTION.md)
        healthy_rate=1.0, incident_rate=1.0),
    '19732': dict(
        title='xgrammar slow on nested length-constrained lists', reference='host_bound',
        model='Qwen/Qwen2.5-1.5B-Instruct', env='v092', version='0.9.2',
        server_args='--max-model-len 4096 --gpu-memory-utilization 0.6 --guided-decoding-backend xgrammar',
        configs={'bug': dict(xgrammar='0.1.19'), 'fixed': dict(xgrammar='0.1.21')},  # swapped in place, fix PR #20992
        healthy_rate=0.5, incident_rate=4.0),  # step 6: 1.5 req/s showed no symptom unsaturated (bug/fixed p50 0.96)
    '7592': dict(
        title='Chunked-prefill scheduler regression (preemption thrash)', reference='kv_pressure',
        model='Qwen/Qwen2.5-7B-Instruct',
        server_args='--max-model-len 10000 --gpu-memory-utilization 0.9 --enforce-eager --seed 0 '
                    '--enable-chunked-prefill --max-num-seqs 256 --max-num-batched-tokens 256',
        configs={'bug': dict(env='v055', version='0.5.5'), 'fixed': dict(env='v060', version='0.6.0')},
        healthy_rate=0.3, incident_rate=3.0),  # step 6: 1.45 req/s never filled the KV cache (no preemption; bug/fixed p50 1.07)
}

# Controlled cases (CALIBRATION_PLAN.md §3.2): vLLM 0.11.0 + Qwen2.5-7B (the commissioning setup), generic
# make_schedule.py bodies. One side only ('fixed'); `schedule` holds the make_schedule.py arguments of the condition.
_CTL = dict(model='Qwen/Qwen2.5-7B-Instruct', env='v0110', version='0.11.0',
            server_args='--max-model-len 4096 --gpu-memory-utilization 0.85', configs={'fixed': {}})
CONTROLLED = {
    'ctl_healthy': dict(_CTL, reference='healthy', schedule='--pattern healthy --base-rate 1'),
    'ctl_overload': dict(_CTL, reference='queue_pressure', schedule='--pattern overload --base-rate 1 --high-rate 20'),
    # seed-100 pre-run: 1.5 req/s filled the KV cache only after ~150 s and never preempted
    'ctl_kv': dict(_CTL, reference='kv_pressure',
                   schedule='--pattern overload --base-rate 0.2 --high-rate 3 --prompt-words 1500 --max-tokens 1024'),
    # host-bound condition for θ_g and θ_b: per-step CPU stall in the engine loop
    'ctl_engine_stall': dict(_CTL, reference='host_bound', configs={'fixed': dict(patch='engine_stall_v1:40')},
                             schedule='--pattern overload --base-rate 1 --high-rate 2'),
    'ctl_lull': dict(_CTL, reference='queue_pressure', schedule='--pattern lull --base-rate 1 --high-rate 20 --lull 30'),
    'ctl_shift': dict(_CTL, reference='queue_pressure->prefill_heavy',
                      schedule='--pattern shift --base-rate 1 --high-rate 20 --shift-rate 3 --shift-prompt-words 2000'),
    'ctl_overlap': dict(_CTL, reference='queue_pressure+kv_pressure',
                        schedule='--pattern overload --base-rate 1 --high-rate 20 --prompt-words 1500'),
    # Evaluation only (they test decisions, not thresholds): overload that lasts to the horizon, and overload whose
    # heavy evidence is hidden from the controller (raw values still logged).
    'ctl_persistent': dict(_CTL, reference='queue_pressure',
                           schedule='--pattern overload --base-rate 1 --high-rate 20 --incident 180 --tail 0'),
    'ctl_withhold': dict(_CTL, reference='queue_pressure', withhold='heavy',
                         schedule='--pattern overload --base-rate 1 --high-rate 20'),
}

# vllm#7619: the table prompt of benchmarks/benchmark_prefix_caching.py at v0.5.4 is replaced by a generated
# markdown table of similar length (about 1,500 characters), so that each request group can get a fresh prefix.
TABLE_ROWS = 70

# vllm#19732: the issue's schema (Table.model_json_schema()), as in check_19732_xgrammar.py.
TABLE_SCHEMA = {
    'properties': {'content': {'items': {'items': {'type': 'string'}, 'maxItems': 10, 'minItems': 5, 'type': 'array'},
                               'maxItems': 10, 'minItems': 5, 'title': 'Content', 'type': 'array'}},
    'required': ['content'], 'title': 'Table', 'type': 'object',
}

# vllm#3087: the issue's prompt; the JSON processor itself is attached inside the server (case_server.py).
NER_PROMPT = """
Locate all the names, organizations, locations and other miscellaneous entities in the following sentence:
"Charles went and saw Anna at the coffee shop Starbucks, which was based in a small town in Germany called Essen."
"""


def config(case_id, side):
    """Resolved settings for one side of a case's toggle."""
    case = CASES[case_id] if case_id in CASES else CONTROLLED[case_id]
    cfg = {k: v for k, v in case.items() if k != 'configs'}
    cfg.update(case['configs'][side])
    cfg['server_args'] = ' '.join(filter(None, [case['server_args'], cfg.get('extra_args'), COMMON_ARGS]))
    return cfg


def png_data_url(seed, size=448):
    """A distinct, deterministic RGB PNG per seed (no PIL on the host). Unique pixels per request keep vLLM's
    multimodal caches from hitting, as the random images in check_25418_mm_kwargs.py did."""
    # Pixel (x, y) = ((a*x + c), (y + seed), (x + y)) mod 256. Rows after the first are stored with PNG's "Up"
    # filter, whose difference from the row above is the constant (0, 1, 1), so the file stays a few KB.
    a, c = 1 + seed % 7, seed * 37 % 256
    first = bytes(v for x in range(size) for v in ((a * x + c) % 256, seed % 256, x % 256))
    rows = b'\x00' + first + (b'\x02' + b'\x00\x01\x01' * size) * (size - 1)

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(rows, 6)) + chunk(b'IEND', b''))
    return 'data:image/png;base64,' + base64.b64encode(png).decode()


def table_prompt(group):
    rows = '\n'.join(f'|{group}-{r}|Item {r * 7 % 13}|{r * 31 % 97}|' for r in range(TABLE_ROWS))
    return (f'Session {group}. You are a helpful assistant that reads tables in markdown format. Answer my question '
            f'about the table.\n# Table\n|Id|Name|Value|\n|---|---|---|\n{rows}\n\n# Question\n'
            f"What's the content in the (1,1) cell?\n")


def request(case_id, side, model, index, group, rng):
    """(path, body) for one request. `index` is the request's position in the schedule, `group` its arrival group."""
    cfg = config(case_id, side)
    if case_id == '6240':  # check_6240_serving.py: greedy decode, 256 tokens
        return '/v1/completions', dict(model=model, prompt='Write a detailed history of the printing press.',
                                       max_tokens=256, temperature=0, ignore_eos=True)
    if case_id == '7619':  # benchmark_prefix_caching.py: greedy, --output-len 200
        return '/v1/completions', dict(model=model, prompt=table_prompt(group), max_tokens=200, temperature=0)
    if case_id == '3087':  # the issue's example: max_tokens=128, temperature 0
        return '/v1/completions', dict(model=model, prompt=NER_PROMPT, max_tokens=128, temperature=0)
    if case_id == '25418':  # check_25418_mm_kwargs.py, as chat requests; 112 tokens, ignore_eos
        body = dict(model=model, max_tokens=112, temperature=0, ignore_eos=True, messages=[{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': png_data_url(index)}},
            {'type': 'text', 'text': 'Describe this image.'}]}])
        if cfg['mm_kwargs']:
            body['mm_processor_kwargs'] = {'fps': rng.uniform(1.9, 2.1)}  # the reporter's patch
        return '/v1/chat/completions', body
    if case_id == '19732':  # check_19732_xgrammar.py: 512 max tokens, greedy
        return '/v1/chat/completions', dict(
            model=model, max_tokens=512, temperature=0, guided_json=TABLE_SCHEMA,
            messages=[{'role': 'user', 'content': 'Return a 6x6 table of fruit names as JSON.'}])
    if case_id == '7592':  # check_7592_chunked.py: "hi" * 511, 512 tokens, ignore_eos, temperature 1.0
        return '/v1/completions', dict(model=model, prompt='hi' * 511, max_tokens=512, temperature=1.0, top_p=1.0,
                                       ignore_eos=True)
    raise KeyError(case_id)
