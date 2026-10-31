"""For each fix PR, find the last release before the fix and the first release that contains it.

Usage: python fix_releases.py PR [PR ...]   (reads raw/releases.txt: "tag published_at" per line, from the GitHub releases API)
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def contains(tag, sha):
    return json.loads(gh("api", f"repos/vllm-project/vllm/compare/{tag}...{sha}"))["status"] in ("behind", "identical")


def main():
    releases = sorted((line.split()[1], line.split()[0]) for line in open(HERE / "raw" / "releases.txt"))
    for pr in sys.argv[1:]:
        info = json.loads(gh("pr", "view", pr, "-R", "vllm-project/vllm", "--json", "mergeCommit,mergedAt"))
        sha, merged = info["mergeCommit"]["oid"], info["mergedAt"]
        after = [t for d, t in releases if d >= merged]
        before = [t for d, t in releases if d < merged]
        first = next((t for t in after if contains(t, sha)), None)
        print(f"PR {pr} merged {merged[:10]} sha {sha[:10]}: last release before = {before[-1] if before else None}; first containing = {first}")


if __name__ == "__main__":
    main()
