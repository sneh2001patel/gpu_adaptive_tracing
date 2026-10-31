"""Generate reviewed source pins and a bounded, exact deployment archive."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
ids=ROOT/'revision/protocol/sources/vllm_0_10_2/event_ids'
names={'serving_completion.py.txt':'vllm/entrypoints/openai/serving_completion.py',
 'serving_engine.py.txt':'vllm/entrypoints/openai/serving_engine.py',
 'protocol.py.txt':'vllm/entrypoints/openai/protocol.py','async_llm.py.txt':'vllm/v1/engine/async_llm.py',
 'processor.py.txt':'vllm/v1/engine/processor.py','parallel_sampling.py.txt':'vllm/v1/engine/parallel_sampling.py',
 'utils_init.py.txt':'vllm/utils/__init__.py'}
pins={target:sha(ids/source) for source,target in names.items()}
pins['vllm/engine/arg_utils.py']=sha(ROOT/'revision/protocol/sources/vllm_0_10_2/events/arg_utils.py.txt')
save(ids/'SOURCE_MANIFEST.json',dict(origin='read_only_installed_vllm_0.10.2_on_authorized_L4',files=pins,
 mapping_scope='nonstreaming_single_string_prompt_n1_no_beam_no_best_of_no_X_Request_Id_header',
 rule='submitted request_id -> response cmpl-{request_id} -> engine cmpl-{request_id}-0',
 review='serving_engine._base_request_id; serving_completion.create_completion/request_output_to_completion_response; AsyncLLM.add_request/_add_request; Processor.process_inputs forwards ID unchanged for n=1',
 license='../LICENSE.txt'))
paths=set()
for folder in ('revision/tracing','revision/evaluation','revision/feasibility','revision/scripts','revision/tests'):
 paths.update((ROOT/folder).glob('*.py'))
paths.update((ROOT/'revision/configs').glob('*.json'))
paths.update(p for p in (ROOT/'revision/protocol/sources/vllm_0_10_2').rglob('*') if p.is_file())
paths.update((ROOT/'revision/examples/server_events/prospective_001').glob('*'))
paths.add(ROOT/'revision/hardware/l4_20261028/capacity_001/corpus.json')
paths.update(p for p in HERE.glob('*') if p.suffix in ('.py','.sh','.conf'))
archive=HERE/'source_step028.tar.gz'
if archive.exists():raise FileExistsError('Preserve frozen archive; use a new corrective deployment')
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted(paths):tar.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
save(HERE/'source_archive.json',dict(sha256=sha(archive),files={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}))
print(json.dumps(dict(files=len(paths),archive_sha256=sha(archive))))
