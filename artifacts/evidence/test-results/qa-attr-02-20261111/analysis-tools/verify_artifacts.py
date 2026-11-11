"""Independent artifact invariants plus corruption/relabeling negative controls."""
from pathlib import Path
import json, hashlib, copy, collections
O=Path(__file__).parent
load=lambda n:json.loads((O/n).read_text())
SCOPE={'usb20':{'usb20_fw','usb20_se'},'usb32':{'usb32'},'superspeed_hub_lvs':{'superspeed_hub_lvs'}}
canonical={c['chunk_id']:c for c in load('current-corpus-readonly.json')['chunks']}
def inspect(report):
    issues=[];cases=report['cases']
    if len(cases)!=20 or len({c['question'] for c in cases})!=20:issues.append('independent_case_count')
    if sum(c['kind']=='HISTORICAL_MODEL_QUESTION' for c in cases)!=16:issues.append('model_denominator')
    for c in cases:
        if c['current']['actually_sent_to_model'] is not False:issues.append('fabricated_current_sent')
        if c['current']['actual_prompt']!='NOT_BUILT_BY_FORMAL_EVIDENCE_FIRST_ENTRY':issues.append('fabricated_current_prompt')
        if c['kind']=='HISTORICAL_MODEL_QUESTION' and c['current_prompt_comparison_status']!='NOT_COMPARABLE_NO_CURRENT_LLM_PROMPT':issues.append('contract_comparability')
        if c['current']['budget_trace']['used_chunks']>20 or c['current']['budget_trace']['used_chars']>39739:issues.append('budget_exceeded')
        for w in c['current']['packed_windows']:
            src=canonical.get(w['chunk_id'])
            if src is None or src['source_id'] not in SCOPE[c['scope']]:issues.append('foreign_or_unknown_source');continue
            if w['quote']!=src['content'][w['start']:w['end']]:issues.append('quote_identity')
            if w['content_sha256']!=src['content_sha256']:issues.append('hash_identity')
            if w['source_id']!=src['source_id'] or w['revision']!=src['revision']:issues.append('source_identity')
        if not all(m['exact_content_metadata_match'] for m in c['historical']['actual_sent_mapping']):issues.append('old_sent_unresolved')
        if c['case_key'] in ['P01','P02','P03','P04','P05','SHORT']:
            b=c['historical'].get('alias_binding')
            if not b or not all(b.get(k) is True for k in ['request_sha_verified','messages_wire_sha_verified','original_prepared_sha_verified','all_sent_exact']):issues.append('native_alias_binding_missing')
            elif len(b['aliases'])!=20:issues.append('native_alias_count')
        for stage,roles in c['roles'].items():
            for role in roles:
                if role.get('source_role_retained') and not role['retained']:
                    proof=role.get('independent_source_equivalence')
                    if not proof:issues.append('unproved_source_equivalence');continue
                    rp=proof['review_ref']
                    if hashlib.sha256(Path(rp['path']).read_bytes()).hexdigest()!=rp['sha256']:issues.append('review_identity')
                    for s in proof['support_spans']:
                        src=canonical.get(s['chunk_id'])
                        if not src or src['content'][s['start']:s['end']]!=s['quote']:issues.append('equivalence_span_identity')
    return sorted(set(issues))
def main():
    d=load('qa-attr-02-evidence-diff.json');issues=inspect(d);assert not issues,issues
    mutations=[]
    for name,change,expected in [
        ('current_prompt_false_claim',lambda x:x['cases'][0]['current'].update(actually_sent_to_model=True),'fabricated_current_sent'),
        ('wrong_revision',lambda x:x['cases'][0]['current']['packed_windows'][0].update(revision='9.9'),'source_identity'),
        ('quote_number_corruption',lambda x:x['cases'][0]['current']['packed_windows'][0].update(quote='PORT_POWER | Port | 9'),'quote_identity'),
        ('source_hash_corruption',lambda x:x['cases'][0]['current']['packed_windows'][0].update(content_sha256='0'*64),'hash_identity'),
        ('duplicate_question_weight',lambda x:x['cases'].__setitem__(1,copy.deepcopy(x['cases'][0])),'independent_case_count'),
        ('budget_widened',lambda x:x['cases'][0]['current']['budget_trace'].update(used_chunks=21),'budget_exceeded'),
        ('retrieval_control_as_model',lambda x:x['cases'][-1].update(kind='HISTORICAL_MODEL_QUESTION'),'model_denominator'),
        ('false_equivalence_quote',lambda x:next(c for c in x['cases'] if c['case_key']=='ENUM')['roles']['current_packed_preview'][0]['independent_source_equivalence']['support_spans'][0].update(quote='fabricated source text'),'equivalence_span_identity'),
        ('SHORT_sidecar_omission_regression',lambda x:next(c for c in x['cases'] if c['case_key']=='SHORT')['historical'].update(alias_binding=None),'native_alias_binding_missing')]:
        m=copy.deepcopy(d);change(m);got=inspect(m);assert expected in got,(name,got);mutations.append({'mutation':name,'expected_rejection':expected,'observed':got,'pass':True})
    controls=[]
    q=next(c for c in d['cases'] if c['case_key']=='Q005')
    assert q['missing_old_critical_roles']==['1558','1559'] and q['missing_new_critical_roles']==[]
    controls.append('Q005 old lacks continuedcaption/row while current owns both')
    assert all(all(r['retained'] for r in c['roles']) for c in q['historical_within_question_controls'])
    controls.append('Q005 A1,B,reconnect same-question controls all retain required source witnesses')
    assert load('corpus-identity-bridge.json')['matches_saved_native'] is True
    controls.append('Native fingerprint independently bridges canonical corpus')
    native=[c for c in d['cases'] if c['case_key'] in ['P01','P02','P03','P04','P05','SHORT']]
    assert len(native)==6 and sum(len(c['historical']['alias_binding']['aliases']) for c in native)==120
    controls.append('Six native requests including prepared-sidecar SHORT bind all120 aliases/request/wire/originalprepared')
    for c in d['cases']:
        p=O/'replays'/f"{c['case_key']}.json";r=json.loads(p.read_text())['formal_result']
        assert r['models_loaded']==r['generations']==0 and r['answer'] is None
        assert hashlib.sha256(p.read_bytes()).hexdigest()==c['current']['replay']['sha256']
    controls.append('20 actual replay receipts zero generation/answer and bound by hash')
    for path,h in d['sources_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
    controls.append('All cited historical source files unchanged')
    result={'status':'PASS','positive_invariant_groups':len(controls),'positive_controls':controls,'negative_mutations':mutations,
        'scope':'Report correspondence and safety guards; not USB answer correctness or product qualification.'}
    (O/'artifact-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS',len(controls),'invariant groups;',len(mutations),'negative controls')
if __name__=='__main__':main()
