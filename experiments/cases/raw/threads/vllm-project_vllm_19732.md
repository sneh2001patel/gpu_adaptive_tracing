# vllm-project/vllm#19732: [Performance]: very slow performance for nested list with length constraints
state=closed reason=completed created=2025-06-17T08:07:18Z closed=2025-07-16T02:42:18Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/20992']

## body (@naturomics)
### Proposal to improve performance

_No response_

### Report of performance regression

_No response_

### Misc discussion on performance

See this report at [xgrammar issue](https://github.com/mlc-ai/xgrammar/issues/339).

- env:
  - vllm: `0.9.1`
  - xgrammar: `0.1.19`

- Structured json schema:
```
class Table(BaseModel):
   content: conlist(conlist(str, min_length=5, max_length=10), min_length=5, max_length=10)

json_schema = Table.model_json_schema()
```

This schema leads to very low thoughput (< 3 tokens/s).
Is there any way to improve performance?

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.