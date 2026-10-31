# vllm-project/vllm PR #39169: fix(gdn): Align prefill warmup with real prefill path
merged_at=2026-04-10T00:49:50Z merge_commit=9853a3c15959a9d8f113501f697de6e4e0edeee6 author=@ibrahim1023
files: vllm/model_executor/layers/mamba/gdn_linear_attn.py

## body

## Purpose

Fixes [#39163](https://github.com/vllm-project/vllm/issues/39163) by aligning GDN prefill warmup with the real prefill path.

Real GDN prefills build `q/k/v/g/beta` via `fused_post_conv_prep` and call `chunk_gated_delta_rule(..., use_qk_l2norm_in_kernel=False)`. The previous warmup path did not mirror that contract, which could leave first-request work deferred to the first real prefill. This PR updates the warmup path and adds a regression test.

Duplicate-work check:
- Ran `gh issue view 39163 --repo vllm-project/vllm --comments`
- Ran `gh pr list --repo vllm-project/vllm --state open --search '39163 in:body'`
- Ran `gh pr list --repo vllm-project/vllm --state open --search 'GDN prefill warmup first request Qwen3.5 Blackwell'`
- I did not find an open PR already addressing this fix

AI assistance:
- This PR was prepared with AI assistance. The submitting human reviewed the changed lines and is responsible for the change end-to-end.

## Test Plan

```bash
python -m compileall vllm/model_executor/layers/mamba/gdn_linear_attn.py tests/model_executor/test_gdn_linear_attn.py
.venv/bin/python -m pytest --noconftest tests/model_executor/test_gdn_linear_attn.py -v
.venv/bin/pre-commit run --files vllm/model_executor/layers/mamba/gdn_linear_attn.py tests/model_executor/test_gdn_linear_attn.py
```

## Test Result

`compileall` passed.

Targeted pytest:
```text
1 passed
```

Changed-file pre-commit:
```text
ruff check Passed
ruff format Passed
typos Passed
mypy-local Passed
all remaining relevant file checks Passed
```

Notes:
- I did not reproduce the original Blackwell/Qwen3.5 issue end-to-end on this machine because the environment does not expose the target GPU stack.
- `pre-commit run --all-files` still has unrelated repo-baseline/local-environment issues on this machine, but the checks for the files changed in this PR pass.

---
<details>
<summary> Essential Elements of an Effective PR Description Checklist </summary>

- [x] The purpose of the PR, such as "Fix some issue (link existing issues this PR will resolve)".
- [x] The test plan, such as providing test command.
- [x] The test results, such as pasting the results comparison before and after, or e2e results
- [ ] (Optional) The necessary documentation update, such as updating `supported_models.md` and `examples` for a new model.
- [ ] (Optional) Release notes update. If your change is user facing, please update the release notes draft in the [Google Doc](https://docs.google.com/document/d/1YyVqrgX4gHTtrstbq8oWUImOyPCKSGnJ7xtTpmXzlRs/edit?tab=t.0).
</details>
