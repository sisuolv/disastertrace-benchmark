"""Outcome-blind E representations and strict response accounting."""
import json

TRUTH = {'true', 'false', 'unknown', 'conflict'}
COMMON = (
    'Use only disclosed native report labels, never future weather outcomes. '
    'E asks whether ANY registered neighbor slot has reported visibility strictly below threshold_m. '
    'An unread/missing slot is unknown, not false. A visibility interval proves true only if all '
    'its possible values are below the threshold; it proves false if all are at least the threshold. '
    'Use open and closed endpoints. Current source versions replace superseded ones; incompatible '
    'coexisting facts are conflict. Aggregate all registered slots: conflict if any is conflicting; '
    'otherwise true if any is true; otherwise false only if every slot is false; else unknown. '
    'A TAF is not a neighbor observation. Output JSON strings for truth values, never booleans. '
    'Return exactly the requested JSON object, with no prose or markdown. '
)


def aggregate(values):
    values = list(values)
    if not values or any(v not in TRUTH for v in values):
        raise ValueError('A nonempty registered set of slot statuses is required')
    return ('conflict' if 'conflict' in values else 'true' if 'true' in values
            else 'false' if all(v == 'false' for v in values) else 'unknown')


def focused(view):
    question = view['baseline']['content']['E_question']
    return {
        'question': question, 'cutoff': view['cutoff'],
        'support_scope': 'native report labels; not physical visibility truth',
        'slots': [{'query_id': qid, 'disclosed_versions': [
            {k: asset[k] for k in ('asset_id', 'source_revision', 'available_at', 'completed_at',
                                  'raw', 'content', 'missingness', 'support_rule_version')}
            for asset in view['assets'] if asset['content']['query_id'] == qid
        ]} for qid in question['query_ids']],
    }


def messages(view, representation, reasoning):
    if representation not in {'full_bundle', 'focused_slots'} or reasoning not in {'direct', 'slotwise'}:
        raise ValueError('Unregistered diagnostic factor')
    instruction = ('The output must have exactly fact_truth.' if reasoning == 'direct' else
                   'The output must have exactly slots and fact_truth. slots is an object mapping '
                   'EVERY registered query_id to its truth string. fact_truth is their aggregate.')
    return [{'role': 'system', 'content': COMMON + instruction},
            {'role': 'user', 'content': json.dumps(view if representation == 'full_bundle' else focused(view),
                                                 sort_keys=True, separators=(',', ':'), allow_nan=False)}]


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate response key')
        result[key] = value
    return result


def parse(raw, query_ids, reasoning):
    value = json.loads(raw, object_pairs_hook=unique)
    fields = {'fact_truth'} if reasoning == 'direct' else {'fact_truth', 'slots'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Invalid response fields')
    if type(value['fact_truth']) is not str or value['fact_truth'] not in TRUTH:
        raise ValueError('Invalid fact truth')
    if reasoning == 'slotwise':
        slots = value['slots']
        if not isinstance(slots, dict) or set(slots) != set(query_ids):
            raise ValueError('Every registered slot is required exactly once')
        if any(type(v) is not str or v not in TRUTH for v in slots.values()):
            raise ValueError('Invalid slot truth')
    return value


def independent_reference(view):
    """Second reducer over already disclosed native intervals; no future labels."""
    q = view['baseline']['content']['E_question']
    result = {}
    for qid in q['query_ids']:
        assets = [a for a in view['assets'] if a['content']['query_id'] == qid
                  and a['completed_at'] <= view['cutoff']]
        if not assets:
            result[qid] = 'unknown'
            continue
        current_at = max(a['available_at'] for a in assets)
        lower, upper, lower_closed, upper_closed = 0, float('inf'), True, False
        conflict = False
        for asset in assets:
            if asset['available_at'] != current_at:
                continue
            content = asset['content']
            if content['status'] == 'inconsistent_same_slot_facts':
                conflict = True
            if content['status'] != 'disclosed_product_fact' or len(content.get('reports', [])) != 1:
                continue
            v = content['reports'][0]['visibility']
            if v is None:
                continue
            lo, hi = v['lower'], v['upper']
            lo = -float('inf') if lo in (None, '-inf') else lo
            hi = float('inf') if hi in (None, '+inf') else hi
            if lo > lower:
                lower, lower_closed = lo, v['lower_closed']
            elif lo == lower:
                lower_closed = lower_closed and v['lower_closed']
            if hi < upper:
                upper, upper_closed = hi, v['upper_closed']
            elif hi == upper:
                upper_closed = upper_closed and v['upper_closed']
        if conflict or lower > upper or (lower == upper and not (lower_closed and upper_closed)):
            result[qid] = 'conflict'
        elif upper < q['threshold_m'] or (upper == q['threshold_m'] and not upper_closed):
            result[qid] = 'true'
        elif lower >= q['threshold_m']:
            result[qid] = 'false'
        else:
            result[qid] = 'unknown'
    return {'slots': result, 'fact_truth': aggregate(result.values())}
