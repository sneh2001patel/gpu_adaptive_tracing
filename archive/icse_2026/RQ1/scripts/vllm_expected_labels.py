"""Controlled workload expectations for artifact metadata/evaluation only.

These labels describe intended scenarios, not independently verified causes.
The evidence classifier must never import this mapping or receive its values.
"""

EXPECTED_LABELS = {
    "healthy": "vllm_healthy",
    "queue_pressure": "vllm_queue_pressure",
    "long_prompt": "vllm_long_prompt",
    "long_output": "vllm_long_output",
    "compute_saturation": "vllm_compute_saturation",
    "kv_cache_pressure": "vllm_kv_cache_pressure",
}
