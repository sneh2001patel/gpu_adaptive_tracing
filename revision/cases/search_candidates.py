"""Find closed vLLM issues closed by a merged PR, as reproduction candidates for the case benchmark (proposal §4.1).

Queries GitHub search through `gh api graphql`; writes raw/candidates.jsonl (one issue per line) and raw/retrieved_at.txt.
Only the search frame is automated; screening is manual (see SCREENING.md).
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
REPO = "vllm-project/vllm"
QUERIES = [
    f"repo:{REPO} is:issue is:closed label:performance linked:pr",
    f"repo:{REPO} is:issue is:closed linked:pr in:title slow",
    f"repo:{REPO} is:issue is:closed linked:pr in:title regression",
    f"repo:{REPO} is:issue is:closed linked:pr in:title throughput",
    f"repo:{REPO} is:issue is:closed linked:pr in:title latency",
]
GQL = """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { ... on Issue {
      number title url createdAt closedAt stateReason
      labels(first: 10) { nodes { name } }
      closedByPullRequestsReferences(first: 5, includeClosedPrs: true) {
        nodes { number title merged mergedAt url }
      }
    } }
  }
}"""


def search(q):
    after = None
    while True:
        args = ["gh", "api", "graphql", "-f", f"query={GQL}", "-f", f"q={q}"]
        if after:
            args += ["-f", f"after={after}"]
        data = json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)["data"]["search"]
        yield from data["nodes"]
        if not data["pageInfo"]["hasNextPage"]:
            return
        after = data["pageInfo"]["endCursor"]


def main():
    seen = {}
    for q in QUERIES:
        for node in search(q):
            prs = [p for p in node["closedByPullRequestsReferences"]["nodes"] if p["merged"]]
            if not prs:
                continue
            entry = seen.setdefault(node["number"], {
                "number": node["number"], "title": node["title"], "url": node["url"],
                "created": node["createdAt"], "closed": node["closedAt"],
                "labels": [l["name"] for l in node["labels"]["nodes"]],
                "fix_prs": [{"number": p["number"], "title": p["title"], "merged_at": p["mergedAt"]} for p in prs],
                "queries": [],
            })
            entry["queries"].append(q)
    (HERE / "raw").mkdir(exist_ok=True)
    with open(HERE / "raw" / "candidates.jsonl", "w") as f:
        for n in sorted(seen):
            f.write(json.dumps(seen[n]) + "\n")
    (HERE / "raw" / "retrieved_at.txt").write_text(datetime.now(timezone.utc).isoformat(timespec="seconds") + "\n")
    print(f"{len(seen)} issues closed by a merged PR")


if __name__ == "__main__":
    main()
