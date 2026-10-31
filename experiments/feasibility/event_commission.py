"""Fail-closed commissioning checks for single-string, n=1 completions only."""
from experiments.tracing.server_events import validate_snapshot


def validate_join(rows, receipt, binding):
    if not 1 <= len(rows) <= 8:
        raise ValueError('Commissioning requires one to eight charged requests')
    states = validate_snapshot(receipt['data'], receipt['command'], binding, receipt['received_at_ns'])
    joined = []
    seen = set()
    for row in rows:
        payload, response = row['payload'], row['response']
        if (not isinstance(payload['prompt'], str) or payload.get('n') != 1 or
                payload.get('stream') is not False or payload.get('use_beam_search', False) or
                payload.get('best_of') is not None):
            raise ValueError('Unsupported completion ID mapping configuration')
        base = payload['request_id']
        if not isinstance(base,str) or not base or base in seen:
            raise ValueError('Missing/duplicate submitted ID')
        seen.add(base)
        response_id = 'cmpl-' + base
        # Reviewed vLLM serving_completion.py: one prompt, index zero.
        engine_id = response_id + '-0'
        if row['http_status'] != 200 or response['id'] != response_id or engine_id not in states:
            raise ValueError('Response/engine IDs do not exactly match reviewed source rule')
        usage = response['usage']
        if (usage['prompt_tokens'] != row['expected_prompt_tokens'] or
                usage['completion_tokens'] != payload['max_tokens'] or
                usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens'] or
                len(response['choices']) != 1 or response['choices'][0]['finish_reason'] != 'length'):
            raise ValueError('Actual token work/response shape differs from declared commission')
        state = states[engine_id]
        if state['scheduled'] is None or state['finished'] is None:
            raise ValueError('Incomplete request lifecycle')
        if state['finished']['terminal_status'] != 'FINISHED_LENGTH_CAPPED':
            raise ValueError('Unexpected terminal status')
        events = [state[k] for k in ('admission', 'scheduled', 'finished')]
        if not all(row['requested_at_ns'] <= e['hook_enter_ns'] <= e['hook_return_ns'] <= row['received_at_ns'] for e in events):
            raise ValueError('Scheduler events outside mapped client request bracket')
        admission, scheduled, _ = events
        joined.append(dict(client_request_id=base,response_id=response_id,engine_request_id=engine_id,
            prompt_tokens=usage['prompt_tokens'],output_tokens=usage['completion_tokens'],
            wait_lower_ms=max(0,scheduled['hook_enter_ns']-admission['hook_return_ns'])/1e6,
            wait_upper_ms=(scheduled['hook_return_ns']-admission['hook_enter_ns'])/1e6))
    if set(states) != {r['engine_request_id'] for r in joined}:
        raise ValueError('Unexpected/unaccounted engine request IDs')
    return joined
