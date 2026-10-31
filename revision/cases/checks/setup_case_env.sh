#!/bin/bash
# Recreate a case environment on the L4 host: one uv venv per vLLM release, dependencies resolved as of the
# release date (uv --exclude-newer) so that old releases do not pull present-day packages.
# Usage: setup_case_env.sh <name>     (run in /workspace/cases)
set -euo pipefail
cd /workspace/cases
# Disk is tight (32 GB): run with UV_CACHE_DIR on the same disk and UV_LINK_MODE=hardlink (queue_case_symptoms.sh),
# so environments that share wheels (v055/v060: torch 2.4.0; v032/v033: torch 2.1.2) store them once.
# /dev/shm cannot hold environments: it is mounted noexec, so shared libraries fail to load.
mkvenv() { uv venv -q -p "$1" "$2"; }  # <python version> <name>

stub_pyairports() {
  # The original pyairports was removed from PyPI; the current 0.0.1 is an empty placeholder. outlines imports
  # only AIRPORT_LIST for its airport type, so an empty list is enough.
  local d="$1/lib/python3.10/site-packages/pyairports"
  mkdir -p "$d" && touch "$d/__init__.py" && echo "AIRPORT_LIST = []" > "$d/airports.py"
}

release_env() {  # <name> <vllm version> <cutoff date: day after the release>
  mkvenv 3.10 "$1"
  VIRTUAL_ENV=$PWD/$1 uv pip install -q --exclude-newer "$3T00:00:00Z" \
    --exclude-newer-package "pyairports=2026-10-28T00:00:00Z" \
    --exclude-newer-package "vllm=2026-10-28T00:00:00Z" "vllm==$2" setuptools  # vllm is pinned exactly; its PyPI upload can trail the GitHub release
  if [ -d "$1/lib/python3.10/site-packages/outlines" ]; then stub_pyairports "$1"; fi
}

case "$1" in
  v051)  # vllm#6240, before fix. PyPI wheel is CUDA 12.1-built and lacks the SM89 CUTLASS FP8 path, so the
         # vllm package is replaced by the CUDA 12.4 build from the official image (layer 8 of vllm/vllm-openai:v0.5.1).
    mkvenv 3.10 v051
    # outlines pinned: the cutoff otherwise admits the pre-release 0.1.dev0 (satisfies "<0.1"), which lacks
    # outlines.fsm and breaks the OpenAI server's import of guided decoding.
    VIRTUAL_ENV=$PWD/v051 uv pip install -q --exclude-newer 2024-07-08T00:00:00Z \
      --exclude-newer-package "pyairports=2026-10-28T00:00:00Z" "vllm==0.5.1" "outlines==0.0.46" setuptools
    stub_pyairports v051
    TOKEN=$(curl -s "https://auth.docker.io/token?service=registry.docker.io&scope=repository:vllm/vllm-openai:pull" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
    LAYER=sha256:2735a04f6870a  # prefix; full digest resolved from the manifest below
    curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
      https://registry-1.docker.io/v2/vllm/vllm-openai/manifests/v0.5.1 > m051.json
    DIGEST=$(python3 -c "import json;l=json.load(open('m051.json'))['layers'][8]['digest'];assert l.startswith('$LAYER');print(l)")
    img=img051; mkdir -p $img
    curl -sL -H "Authorization: Bearer $TOKEN" "https://registry-1.docker.io/v2/vllm/vllm-openai/blobs/$DIGEST" \
      | tar -xz -C $img --wildcards "usr/local/lib/python3.10/dist-packages/vllm/*"
    sp=v051/lib/python3.10/site-packages
    mv $sp/vllm $sp/vllm_pypi_cu121
    mv $img/usr/local/lib/python3.10/dist-packages/vllm $sp/vllm_image_cu124
    ln -s vllm_image_cu124 $sp/vllm
    rm -rf $img ;;
  v055)    release_env v055 0.5.5 2024-08-24 ;;        # vllm#7619 / #7592, before fix
  v060)    release_env v060 0.6.0 2024-09-06 ;;        # vllm#7619 / #7592, after fix
  v052)    release_env v052 0.5.2 2024-07-16 ;;        # vllm#6240, after fix
  v064p1)  release_env v064p1 0.6.4.post1 2024-11-16 ;;  # vllm#6923, before fix
  v065)    release_env v065 0.6.5 2024-12-19 ;;        # vllm#6923, after fix
  v0110)   release_env v0110 0.11.0 2025-10-03 ;;      # vllm#25418, before fix
  v0111)   release_env v0111 0.11.1 2025-11-19 ;;      # vllm#25418, after fix
  v092)    release_env v092 0.9.2 2025-07-08 ;;        # vllm#19732; toggle xgrammar in place:
           # VIRTUAL_ENV=$PWD/v092 uv pip install -q --no-deps xgrammar==0.1.21   (fix PR #20992; overrides vLLM's 0.1.19 pin)
  v032|v033)  # vllm#3087 before / after fix #3099; outlines as of the issue date for outlines.serve.vllm
    ver=0.3.${1:3:1}; mkvenv 3.10 "$1"
    VIRTUAL_ENV=$PWD/$1 uv pip install -q --exclude-newer 2024-02-28T00:00:00Z \
      --exclude-newer-package "vllm=2026-10-28T00:00:00Z" "vllm==$ver" outlines setuptools ;;
  v0260|v0280)  # vllm#49013 before / after fix #49919 (CUDA 13 builds; Python 3.12)
    ver=0.${1:2:2}.0; cutoff=$([ "$1" = v0260 ] && echo 2026-07-28 || echo 2026-08-27)
    mkvenv 3.12 "$1"
    VIRTUAL_ENV=$PWD/$1 uv pip install -q --exclude-newer "${cutoff}T00:00:00Z" \
      --exclude-newer-package "vllm=2026-10-28T00:00:00Z" "vllm==$ver" setuptools
    "$1/bin/python" -c "import vllm, torch; print('$1', vllm.__version__, torch.__version__)"; exit 0 ;;
  *) echo "unknown env $1" >&2; exit 1 ;;
esac
"$1/bin/python" -c "import vllm, torch; print('$1', vllm.__version__, torch.__version__)"
