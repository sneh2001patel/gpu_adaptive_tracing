# vllm-project/vllm PR #12536: [Kernel] Use self.kv_cache and forward_context.attn_metadata in Attention.forward
merged_at=2025-02-05T21:24:26Z merge_commit=4c3aac51e14214880a3205b45c26aa16535992b5 author=@heheda12345
files: vllm/attention/layer.py

## body
This PR does the following things:
1. Use self.kv_cache instead of getting attn object from forward_context and access attn object's kv_cache attribute . This can avoid unnecessary torch.compile guards as mentioned in #12410
2. Remove the direct access of attn_metadata in dynamic kv cache scale.
3. Add notes about how to use kv_cache and attn_metadata in this function

@anko-intel does this PR fix your problem?

fix #12410 
CC @youkaichao 
