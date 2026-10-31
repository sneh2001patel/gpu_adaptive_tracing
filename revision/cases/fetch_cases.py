"""Fetch shortlisted candidate issues and their fix PRs into compact markdown for screening.

Usage: python fetch_cases.py NUMBER [NUMBER ...]
Reuses the Phase A thread fetcher; fix PRs come from raw/candidates.jsonl. Output goes to raw/threads/.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "phase_a"))
import fetch_threads  # noqa: E402

fetch_threads.OUT = HERE / "raw" / "threads"
REPO_URL = "https://github.com/vllm-project/vllm/issues/"


def fetch_pr(number):
    pr = fetch_threads.gh_json(f"repos/vllm-project/vllm/pulls/{number}")
    files = fetch_threads.gh_json(f"repos/vllm-project/vllm/pulls/{number}/files?per_page=100")
    text = "\n".join([
        f"# vllm-project/vllm PR #{number}: {pr['title']}",
        f"merged_at={pr.get('merged_at')} merge_commit={pr.get('merge_commit_sha')} author=@{pr['user']['login']}",
        "files: " + ", ".join(f["filename"] for f in files),
        f"\n## body\n{fetch_threads.compact(pr['body'])}",
    ])
    (fetch_threads.OUT / f"vllm-project_vllm_pr{number}.md").write_text(text)


def main():
    fetch_threads.OUT.mkdir(parents=True, exist_ok=True)
    cands = {d["number"]: d for d in map(json.loads, open(HERE / "raw" / "candidates.jsonl"))}
    for n in map(int, sys.argv[1:]):
        comments = fetch_threads.fetch(REPO_URL + str(n))
        for pr in cands[n]["fix_prs"]:
            fetch_pr(pr["number"])
        print(f"#{n} comments={comments} prs={[p['number'] for p in cands[n]['fix_prs']]}", file=sys.stderr)


if __name__ == "__main__":
    main()
