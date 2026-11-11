"""Offline metadata audit. Does not import replay tools, read private files or call models."""
from pathlib import Path
import copy
import hashlib
import json

HERE=Path(__file__).resolve().parent
def load(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))
def unbox(name):
    return load(name)['data']
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def check_manifest():
    manifest=load('publication-manifest.json')
    for relative,expected in manifest['files'].items():
        path=(HERE/relative).resolve()
        if not path.is_relative_to(HERE) or not path.is_file() or digest(path)!=expected:
            raise ValueError('Publication file missing, escaped or changed: '+relative)
    return len(manifest['files'])
def check_projection(value,key=''):
    """Raw source text must be a typed withheld descriptor, never a body string."""
    raw_keys={'quote','exact_quote','original_quote','original_text','raw_text','content','messages','text','content_utf8','original_content','caption_lines','source_text','source_excerpt','tables'}
    if key in raw_keys and value is not None:
        if not isinstance(value,dict) or value.get('withheld') is not True:
            raise ValueError('Raw evidence body leaked into public projection')
        return
    if isinstance(value,dict):
        for k,v in value.items():check_projection(v,k)
    elif isinstance(value,list):
        for v in value:check_projection(v,key)
def check_evidence(data):
    cases=data['cases']
    if len(cases)!=20 or len({json.dumps(c['question'],sort_keys=True) for c in cases})!=20:
        raise ValueError('Independent question count')
    if sum(c['kind']=='HISTORICAL_MODEL_QUESTION' for c in cases)!=16:
        raise ValueError('Historical model denominator')
    if sum(c['kind']=='RETRIEVAL_ONLY_CONTROL' for c in cases)!=4:
        raise ValueError('Retrieval-only denominator')
    for c in cases:
        current=c['current'];budget=current['budget_trace']
        if current['actually_sent_to_model'] is not False or current['actual_prompt']!='NOT_BUILT_BY_FORMAL_EVIDENCE_FIRST_ENTRY':
            raise ValueError('Invented current model input')
        if budget['used_chunks']>20 or budget['used_chars']>39739:
            raise ValueError('Budget exceeded')
        if c['critical_roles_lost']:
            raise ValueError('Declared no-regression summary contradicted')
    native=[c for c in cases if c['case_key'] in ['P01','P02','P03','P04','P05','SHORT']]
    if len(native)!=6 or any(not c['historical'].get('alias_binding') for c in native):
        raise ValueError('Native binding missing')
    if sum(len(c['historical']['alias_binding']['aliases']) for c in native)!=120:
        raise ValueError('Native alias count')
    summary=data['summary_counts']
    if summary['historical_primary_missing_necessary_evidence']!=1 or summary['current_preview_fully_closes_primary_gaps']!=1:
        raise ValueError('Summary counts')
    return cases
def run():
    file_count=check_manifest()
    selection=unbox('qa-attr-02-case-selection.json')
    grouped=[r for g in selection['grouping'] for r in g['records']]
    complete=[g for g in selection['grouping'] if any(r['prompt_status']=='COMPLETE_SAVED_PROMPT' for r in g['records'])]
    if len(grouped)!=165 or sum(r['prompt_status']=='COMPLETE_SAVED_PROMPT' for r in grouped)!=108 or len(complete)!=39:
        raise ValueError('Historical grouping counts')
    evidence=unbox('qa-attr-02-evidence-diff.json');cases=check_evidence(evidence)
    for path in HERE.rglob('*.json'):
        document=json.loads(path.read_text(encoding='utf-8'))
        if document.get('schema')=='qa-attr-02-public-projection.v1':
            check_projection(document['data'])
    index={c['chunk_id']:c for c in load('corpus-index.json')['chunks']}
    if len(index)!=4330 or any('content' in c for c in index.values()):raise ValueError('Corpus metadata scope')
    for c in cases:
        for w in c['current']['packed_windows']:
            src=index[w['chunk_id']]
            if (src['source_id'],src['revision'],src['content_sha256'])!=(w['source_id'],w['revision'],w['content_sha256']):
                raise ValueError('Window metadata identity')
        result=unbox('replays/'+c['case_key']+'.json')['formal_result']
        if result['models_loaded']!=0 or result['generations']!=0 or result['answer'] is not None:
            raise ValueError('Replay/model boundary')
        check_projection(result)
    tests=[
        ('invented_model_input',lambda d:d['cases'][0]['current'].update(actually_sent_to_model=True)),
        ('duplicate_question',lambda d:d['cases'].__setitem__(1,copy.deepcopy(d['cases'][0]))),
        ('SHORT_binding_omitted',lambda d:next(c for c in d['cases'] if c['case_key']=='SHORT')['historical'].update(alias_binding=None)),
        ('expanded_budget',lambda d:d['cases'][0]['current']['budget_trace'].update(used_chunks=21)),
        ('control_counted_as_model',lambda d:d['cases'][-1].update(kind='HISTORICAL_MODEL_QUESTION'))]
    for name,mutate in tests:
        changed=copy.deepcopy(evidence);mutate(changed)
        try:check_evidence(changed)
        except ValueError:pass
        else:raise ValueError('Negative control not rejected: '+name)
    leaked=copy.deepcopy(evidence);leaked['cases'][0]['current']['packed_windows'][0]['quote']='private source body'
    try:check_projection(leaked)
    except ValueError:pass
    else:raise ValueError('Raw-text negative control not rejected')
    # Regression for the actual short body-field families missed by the first projection.
    missed_fields={'original_content':'synthetic short source body',
        'caption_lines':['synthetic caption body'], 'source_text':'synthetic source text',
        'source_excerpt':'synthetic excerpt', 'tables':[{'values':[['synthetic cell']]}]}
    for field,body in missed_fields.items():
        try:check_projection({field:body})
        except ValueError:pass
        else:raise ValueError('Omitted-field regression not rejected: '+field)
        check_projection({field:{'withheld':True,'sha256_utf8':'0'*64,'unicode_chars':1}})
    print(json.dumps({'status':'PASS','manifest_files':file_count,'historical_records':165,'complete_prompt_records':108,
        'complete_exact_question_groups':39,'model_questions':16,'retrieval_controls':4,'native_aliases':120,
        'replay_metadata_records':20,'negative_controls':11,'new_model_calls':0,
        'boundary':'Metadata consistency only; withheld source text, actual wire bytes and USB semantics NOT reverified.'},ensure_ascii=False))
if __name__=='__main__':run()
