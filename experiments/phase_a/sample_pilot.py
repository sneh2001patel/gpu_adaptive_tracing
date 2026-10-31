"""Draw the seeded, stratified Phase A pilot sample from the retrieved issue frames."""

import csv
import json
import random
from pathlib import Path

RAW = Path(__file__).parent / "raw"
SEED = 20261028

# Stratum -> sample size. vLLM split follows its completed/other ratio (167/480).
STRATA = {
    "vllm_perf_completed": 8,
    "vllm_perf_other": 14,
    "sglang_perf": 4,
    "liu_s4_vllm": 4,
}


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def frames():
    vllm = load_jsonl(RAW / "vllm-project_vllm_closed_performance.jsonl")
    sglang = load_jsonl(RAW / "sgl-project_sglang_closed_performance.jsonl")
    liu = json.load(open(RAW / "liu2025_abnormal_performance_subset.json"))
    return {
        "vllm_perf_completed": [r["url"] for r in vllm if r["state_reason"] == "completed"],
        "vllm_perf_other": [r["url"] for r in vllm if r["state_reason"] != "completed"],
        "sglang_perf": [r["url"] for r in sglang],
        "liu_s4_vllm": [r["URL"].rstrip("/") for r in liu if r["repo"] == "vllm"],
    }


def main():
    rng = random.Random(SEED)
    rows = []
    for stratum, urls in frames().items():
        for url in rng.sample(sorted(urls), STRATA[stratum]):
            rows.append({"stratum": stratum, "url": url, "frame_size": len(urls)})
    out = Path(__file__).parent / "pilot_sample.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["stratum", "url", "frame_size"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} issues -> {out}")


if __name__ == "__main__":
    main()
