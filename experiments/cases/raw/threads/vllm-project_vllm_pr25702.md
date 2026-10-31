# vllm-project/vllm PR #25702: [Optimization] Streamline `InputPreprocessor`
merged_at=2025-09-25T21:06:50Z merge_commit=3d54bdcb73572c8797aa6bc69bc31a6a8122b073 author=@DarkLight1337
files: vllm/inputs/preprocess.py

## body
<!-- markdownlint-disable -->

## Purpose

- Initialize multimodal processor only once
- Remove all async methods because they aren't being used in V1

FIX https://github.com/vllm-project/vllm/issues/25671

## Test Plan

## Test Result

---
<details>
<summary> Essential Elements of an Effective PR Description Checklist </summary>

- [ ] The purpose of the PR, such as "Fix some issue (link existing issues this PR will resolve)".
- [ ] The test plan, such as providing test command.
- [ ] The test results, such as pasting the results comparison before and after, or e2e results
- [ ] (Optional) The necessary documentation update, such as updating `supported_models.md` and `examples` for a new model.
- [ ] (Optional) Release notes update. If your change is user facing, please update the release notes draft in the [Google Doc](https://docs.google.com/document/d/1YyVqrgX4gHTtrstbq8oWUImOyPCKSGnJ7xtTpmXzlRs/edit?tab=t.0).
</details>

