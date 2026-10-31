# vllm-project/vllm PR #6384: [Kernel] Turn off CUTLASS scaled_mm for Ada Lovelace
merged_at=2024-07-14T13:37:20Z merge_commit=9dad5cc85902f419aea5320dd49a827621ed5668 author=@tlrmchlsmth
files: .buildkite/lm-eval-harness/configs/Meta-Llama-3-8B-Instruct-FP8-compressed-tensors.yaml, .buildkite/lm-eval-harness/configs/Meta-Llama-3-8B-Instruct-FP8.yaml, csrc/quantization/cutlass_w8a8/scaled_mm_entry.cu

## body
We haven't tuned the cutlass kernels for SM89 and performance is very bad.

The following benchmarks were run on an L40 with
```
    python benchmarks/benchmark_serving.py \
    --backend openai \
    --model neuralmagic/Meta-Llama-3-8B-Instruct-FP8 \
    --dataset-path ShareGPT_V3_unfiltered_cleaned_split.json \
    --request-rate 1 \
    --num-prompts 200 \
    --port 8000
```


Using the CUTLASS kernels:
```
============ Serving Benchmark Result ============
Successful requests:                     200
Benchmark duration (s):                  211.44
Total input tokens:                      42659
Total generated tokens:                  41049
Request throughput (req/s):              0.95
Input token throughput (tok/s):          201.76
Output token throughput (tok/s):         194.14
---------------Time to First Token----------------
Mean TTFT (ms):                          71.19
Median TTFT (ms):                        63.17
[... 8 lines truncated ...]
==================================================
```

Using torch.scaled_mm:
```
============ Serving Benchmark Result ============
Successful requests:                     200
Benchmark duration (s):                  202.07
Total input tokens:                      42659
Total generated tokens:                  40851
Request throughput (req/s):              0.99
Input token throughput (tok/s):          211.11
Output token throughput (tok/s):         202.16
---------------Time to First Token----------------
Mean TTFT (ms):                          30.50
Median TTFT (ms):                        29.03
[... 8 lines truncated ...]
==================================================
```

---

<details>
<!-- inside this <details> section, markdown rendering does not work, so we use raw html here. -->
<summary><b> PR Checklist (Click to Expand) </b></summary>

<p>Thank you for your contribution to vLLM! Before submitting the pull request, please ensure the PR meets the following criteria. This helps vLLM maintain the code quality and improve the efficiency of the review process.</p>

<h3>PR Title and Classification</h3>
<p>Only specific types of PRs will be reviewed. The PR title is prefixed appropriately to indicate the type of change. Please use one of the following:</p>
<ul>
    <li><code>[Bugfix]</code> for bug fixes.</li>
    <li><code>[CI/Build]</code> for build or continuous integration improvements.</li>
    <li><code>[Doc]</code> for documentation fixes and improvements.</li>
    <li><code>[Model]</code> for adding a new model or improving an existing model. Model name should appear in the title.</li>
    <li><code>[Frontend]</code> For changes on the vLLM frontend (e.g., OpenAI API server, <code>LLM</code> class, etc.) </li>
    <li><code>[Kernel]</code> for changes affecting CUDA kernels or other compute kernels.</li>
    <li><code>[Core]</code> for changes in the core vLLM logic (e.g., <code>LLMEngine</code>, <code>AsyncLLMEngine</code>, <code>Scheduler</code>, etc.)</li>
    <li><code>[Hardware][Vendor]</code> for hardware-specific changes. Vendor name should appear in the prefix (e.g., <code>[Hardware][AMD]</code>).</li>
    <li><code>[Misc]</code> for PRs that do not fit the above categories. Please use this sparingly.</li>
</ul>
<p><strong>Note:</strong> If the PR spans more than one category, please include all relevant prefixes.</p>

<h3>Code Quality</h3>

<p>The PR need to meet the following code quality standards:</p>

<ul>
    <li>We adhere to <a href="https://google.github.io/styleguide/pyguide.html">Google Python style guide</a> and <a href="https://google.github.io/styleguide/cppguide.html">Google C++ style guide</a>.</li>
    <li>Pass all linter checks. Please use <a href="https://github.com/vllm-project/vllm/blob/main/format.sh"><code>format.sh</code></a> to format your code.</li>
    <li>The code need to be well-documented to ensure future contributors can easily understand the code.</li>
    <li>Include sufficient tests to ensure the project to stay correct and robust. This includes both unit tests and integration tests.</li>
    <li>Please add documentation to <code>docs/source/</code> if the PR modifies the user-facing behaviors of vLLM. It helps vLLM user understand and utilize the new features or changes.</li>
</ul>

<h3>Notes for Large Changes</h3>
<p>Please keep the changes as concise as possible. For major architectural changes (>500 LOC excluding kernel/data/config/test), we would expect a GitHub issue (RFC) discussing the technical design and justification. Otherwise, we will tag it with <code>rfc-required</code> and might not go through the PR.</p>

<h3>What to Expect for the Reviews</h3>

<p>The goal of the vLLM team is to be a <i>transparent reviewing machine</i>. We would like to make the review process transparent and efficient and make sure no contributor feel confused or frustrated. However, the vLLM team is small, so we need to prioritize some PRs over others. Here is what you can expect from the review process: </p>

<ul>
    <li> After the PR is submitted, the PR will be assigned to a reviewer. Every reviewer will pick up the PRs based on their expertise and availability.</li>
    <li> After the PR is assigned, the reviewer will provide status update every 2-3 days. If the PR is not reviewed within 7 days, please feel free to ping the reviewer or the vLLM team.</li>
    <li> After the review, the reviewer will put an <code> action-required</code> label on the PR if there are changes required. The contributor should address the comments and ping the reviewer to re-review the PR.</li>
    <li> Please respond to all comments within a reasonable time frame. If a comment isn't clear or you disagree with a suggestion, feel free to ask for clarification or discuss the suggestion.
 </li>
</ul>

<h3>Thank You</h3>

<p> Finally, thank you for taking the time to read these guidelines and for your interest in contributing to vLLM. Your contributions make vLLM a great tool for everyone! </p>


</details>


