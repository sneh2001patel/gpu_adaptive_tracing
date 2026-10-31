# vllm-project/vllm PR #9818: [Bugfix][core] replace heartbeat with pid check
merged_at=2024-10-30T16:34:07Z merge_commit=3b3f1e743631667795469946a33d8352fcc74efd author=@joerunde
files: tests/mq_llm_engine/test_error_handling.py, tests/mq_llm_engine/utils.py, vllm/engine/multiprocessing/client.py, vllm/engine/multiprocessing/engine.py, vllm/entrypoints/openai/api_server.py

## body
There are known cases where the MQLLMEngine will block up the GIL for quite a long time, which will cause it to fail to send back heartbeats to the client, crashing the whole application. This can happen when running guided decoding, or processing large multimodal inputs. Given that we know the engine process can be alive but unresponsive, maybe we shouldn't crash the server if we know that the engine process is still alive. 

This PR removes the heartbeat loop in `MQLLMEngine` and has the client ignore any timeout errors while polling the heartbeat socket. Instead, the client will check to see if the engine process is still running to determine liveness. The MQLLMEngine will still send back health status on the heartbeat socket either when it errors, or when it's idle waiting for input.

I'm hoping this all gets reworked in the V1 re-architecture, but this turned out to be a small-ish change that seems to work well in the meantime. I verified with an artillery case that would normally crush a server under guided decoding processing, this now takes many minutes to process but will eventually churn through all requests successfully.

<details>
<summary>artillery.yml</summary>

```yaml
config:
  timeout: 1000
  target: http://rundemc-dev-service:8000
  phases:
    - duration: 60
      arrivalRate: 12
      name: Load test

  payload:
    # path is relative to the location of the test script
    path: 'payloads.csv'
[... 54 lines truncated ...]

```
</details>


FIX #9082
FIX #9238 

**BEFORE SUBMITTING, PLEASE READ THE CHECKLIST BELOW AND FILL IN THE DESCRIPTION ABOVE**

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

<h3>Adding or changing kernels</h3>
<p>Each custom kernel needs a schema and one or more implementations to be registered with PyTorch.</p>
<ul>
    <li>Make sure custom ops are registered following PyTorch guidelines: <a href="https://pytorch.org/tutorials/advanced/cpp_custom_ops.html#cpp-custom-ops-tutorial">Custom C++ and CUDA Operators</a> and <a href="https://docs.google.com/document/d/1_W62p8WJOQQUzPsJYa7s701JXt0qf2OfLub2sbkHOaU">The Custom Operators Manual</a></li>
    <li>Custom operations that return <code>Tensors</code> require meta-functions. Meta-functions should be implemented and registered in python so that dynamic dims can be handled automatically. See above documents for a description of meta-functions.</li>
    <li>Use <a href="https://pytorch.org/docs/stable/library.html#torch.library.opcheck"><code>torch.libary.opcheck()</code></a> to test the function registration and meta-function for any registered ops.  See <code>tests/kernels</code> for examples.</li>
    <li>When changing the C++ signature of an existing op, the schema must be updated to reflect the changes.</li>
    <li>If a new custom type is needed, see the following document: <a href="https://docs.google.com/document/d/18fBMPuOJ0fY5ZQ6YyrHUppw9FA332CpNtgB6SOIgyuA">Custom Class Support in PT2</a>.
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


