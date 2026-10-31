# vllm-project/vllm#7949: [Performance]: vLLM version issue.
state=closed reason=not_planned created=2024-08-28T09:33:41Z closed=2024-12-28T01:59:01Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@zjjznw123)
### Proposal to improve performance

_No response_

### Report of performance regression

_No response_

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

Is it possible that even with the same version, the code downloaded at different times might be slightly different? For example, if the tag is 0.5.5, could the code downloaded earlier differ slightly from the code downloaded today? Because I noticed that for the same version, the log outputs are different, and the line numbers in the same Python file also differ. So I wanted to ask about this.

### Before submitting a new issue...

- [X] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @DarkLight1337 2024-08-28T10:08:50Z
How are you downloading/using the vLLM code?

## comment @zjjznw123 2024-08-28T11:17:04Z
> How are you downloading/using the vLLM code?

One was installed via pip, and the other was compiled using a Dockerfile. When running the apiserver.py file in the container, there was a bug. I noticed that the line number of the Python file where the error occurred is different from the line number in the Python file installed via pip

## comment @DarkLight1337 2024-08-28T13:00:09Z
Make sure the Docker container isn't outdated. For both the pip and Docker installation, can you import vLLM and print its version number?

## comment @github-actions[bot] 2024-11-27T02:04:58Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2024-12-28T01:59:01Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!