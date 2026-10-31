"""Fetch each pilot issue (body + comments) via the gh CLI into compact markdown for coding.

Code/log blocks longer than MAX_BLOCK_LINES are truncated with an explicit marker so that the
presence of profiler output stays visible while long dumps do not dominate the reading copy.
"""

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "raw" / "threads"
MAX_BLOCK_LINES = 15
FENCE = re.compile(r"```.*?```", re.S)


def gh_json(path):
    out = subprocess.run(["gh", "api", "--paginate", path], check=True, capture_output=True, text=True).stdout
    # --paginate concatenates JSON arrays; normalise to one list.
    return json.loads("[" + out.replace("][", ",")[1:-1] + "]") if out.startswith("[") else json.loads(out)


def compact(text):
    def shorten(m):
        lines = m.group(0).splitlines()
        if len(lines) <= MAX_BLOCK_LINES:
            return m.group(0)
        keep = lines[: MAX_BLOCK_LINES - 3] + [f"[... {len(lines) - MAX_BLOCK_LINES} lines truncated ...]"] + lines[-2:]
        return "\n".join(keep)

    return FENCE.sub(shorten, text or "")


def fetch(url):
    owner, repo, _, number = url.split("/")[-4:]
    issue = gh_json(f"repos/{owner}/{repo}/issues/{number}")
    comments = gh_json(f"repos/{owner}/{repo}/issues/{number}/comments?per_page=100")
    events = gh_json(f"repos/{owner}/{repo}/issues/{number}/timeline?per_page=100")
    linked = sorted({
        e["source"]["issue"]["html_url"]
        for e in events
        if e.get("event") == "cross-referenced" and e.get("source", {}).get("issue", {}).get("pull_request")
    })
    parts = [
        f"# {owner}/{repo}#{number}: {issue['title']}",
        f"state={issue['state']} reason={issue.get('state_reason')} created={issue['created_at']} "
        f"closed={issue.get('closed_at')} labels={[l['name'] for l in issue['labels']]}",
        f"cross-referenced PRs: {linked or 'none'}",
        f"\n## body (@{issue['user']['login']})\n{compact(issue['body'])}",
    ]
    for c in comments:
        parts.append(f"\n## comment @{c['user']['login']} {c['created_at']}\n{compact(c['body'])}")
    (OUT / f"{owner}_{repo}_{number}.md").write_text("\n".join(parts))
    return len(comments)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with open(HERE / "pilot_sample.csv") as f:
        for row in csv.DictReader(f):
            n = fetch(row["url"])
            print(f"{row['url']}  comments={n}", file=sys.stderr)


if __name__ == "__main__":
    main()
