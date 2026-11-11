"""Evidence-only correspondence, not an answer evaluator or new Gold."""
from pathlib import Path
import json, hashlib, re, collections
R=Path('/Users/sw1/Desktop/uvm-agent-lab');O=Path(__file__).parent;H=R/'artifacts/evidence/test-results'
load=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,j):(O/name).write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
selection=load(O/'qa-attr-02-case-selection.json');inv=load('/Users/sw1/gv100h-poc/qa-attr-01-20261111/historical-qa-inventory.json')
bycase={c['case_id']:c for c in inv['cases']};corpus=load(O/'current-corpus-readonly.json');chunks=corpus['chunks'];byid={c['chunk_id']:c for c in chunks};order={c['chunk_id']:i for i,c in enumerate(chunks)}
bycontent=collections.defaultdict(list)
for c in chunks:bycontent[c['content']].append(c)
refs={}
def ref(p,pointer=''):
    p=Path(p);refs[str(p)]=sha(p);return {'path':str(p),'sha256':sha(p),'json_pointer':pointer}
roles=collections.defaultdict(list)
def add(key,rid,meaning,quotes,source,critical=True,boundary=False):
    roles[key].append({'role_id':rid,'critical':critical,'meaning':meaning,'all_required_fragments':quotes,'acceptance_source':source,'boundary_only':boundary})
def frag(cid,text):
    c=byid[cid];assert text in c['content'],(cid,text)
    return {'quote':text,'source_id':c['source_id'],'revision':c['revision'],'section':c['section'],'page_or_anchor':c['page_or_anchor'],'illustrative_chunk_id':cid,'content_sha256':c['content_sha256'],'start':c['content'].index(text),'end':c['content'].index(text)+len(text)}
def find(source,section,page):return next(c for c in chunks if c['source_id']==source and c['section']==section and c['page_or_anchor']==f'p.{page}')
def f(source,section,page,start,end=None):
    c=next(c for c in chunks if c['source_id']==source and c['section']==section and c['page_or_anchor']==f'p.{page}' and start in c['content'])
    i=c['content'].index(start);j=c['content'].index(end,i)+len(end) if end else len(c['content'])
    return frag(c['chunk_id'],c['content'][i:j])
sem=ref(H/'typed-claim-seven-live3-20261002-01/semantic-review.json')
add('Q002','ordered_optional_stages','Setup/Status minimum; optional Data in between',[f('usb20_fw','8.5.3',253,'Control transfers minimally','Status stages.')],sem)
add('Q002','status_final_direction','Status final, opposite preceding Data; no-Data IN',[f('usb20_fw','8.5.3',254,'The Status stage',None)],sem)
add('Q002','status_information_flow','Status information function-to-host',[f('usb20_fw','8.5.3.1',255,'The Status stage',None)],sem)
add('Q007','rise_fall_scope_units','Hub/A and detachable device/B, 10-90%, >=500 ps',[f('usb20_se','7.1.2.2',167,'For a hub,','(respectively).')],sem)
add('Q010','address_zero','Address returns zero',[f('usb32','9.4.2',365,'Address state:','shall be returned.')],sem)
add('Q010','configured_current','Configured non-zero current configuration',[f('usb32','9.4.2',365,'Configured state:','returned.')],sem)
add('Q006','contact_capacitance_row','Contact Capacitance maximum2pF unmated per contact',[f('usb20_se','6.7',135,'Contact Capacitance','contact.')],sem)
add('Q012','timer_start_set','Clear starts timer; Set within80ms',[f('superspeed_hub_lvs','12',18,'c. LVSh sends ClearPortFeature','for DFP.')],sem)
add('Q012','after120_PP1','GetPortStatus after120ms verifies PP1',[f('superspeed_hub_lvs','12',18,'d. After max tReset','PP = 1.')],sem)
add('Q011','PLS_current_complete','Current link; transition complete before reflected',[f('usb32','10.16.2.6.1',477,'5-8 Port Link State','transition to that state is complete.')],sem)
add('Q011','disabled_request','SetPortFeature(PORT_LINK_STATE)eSS.Disabled',[f('usb32','10.3.1.9',420,'A port transitions',None)],sem)
# The requested state is explicit in question. Value4 prose is a source-supported
# alternative/extra, not an additional obligation beyond this question's request.
q005ref=ref(H/'typed-claim-q005-ab-live-20261003/A1/source-review.json')
for ix,meaning in [(1556,'base table caption'),(1558,'continued table caption'),(1559,'Recipient/Value header and PORT_POWER Port8 row')]:
    c=next(c for c in chunks if c['source_id']=='usb20_fw' and c['chunk_id'].split(':')[-2]==str(ix))
    if ix==1559:
        lines=c['content'].splitlines();text='\n'.join(lines[:2])
        # Preserve header identity and the exact row as independent required fragments.
        qs=[frag(c['chunk_id'],lines[0]),frag(c['chunk_id'],next(z for z in lines if z.startswith('PORT_POWER')))]
    else:qs=[frag(c['chunk_id'],next(z for z in c['content'].splitlines() if 'Table 11-17.' in z))]
    add('Q005',str(ix),meaning,qs,q005ref)

pcpath=H/'model-27b-controlled-qa-pilot-20261021/quality-contract-candidate.json';pc=load(pcpath)
for ci,c in enumerate(pc['cases']):
    for ri,r in enumerate(c['minimum_core']):
        if r.get('basis_kind')=='question_stated_missing_observation':
            add(c['id'],r['id'],r['expected_meaning'],[],ref(pcpath,f'/cases/{ci}/minimum_core/{ri}'),boundary=True);continue
        qs=[frag(e['chunk_id'],e['quote']) for e in r['illustrative_support']]
        add(c['id'],r['id'],r['expected_meaning'],qs,ref(pcpath,f'/cases/{ci}/minimum_core/{ri}'))

ppath=H/'spec-qa-performance-ab-live-20261016/source-preflight-review.json';pf=load(ppath);spans={e['span_id']:e for e in pf['evidence_spans']}
clar=ref(H/'spec-qa-performance-ab-live-20261016/rubric-scope-clarification.json')
for q in pf['questions']:
    key={'speed':'SPEED','enumeration':'ENUM','remote_wakeup':'WAKE'}[q['question_key']]
    must={'SPEED':['S1','S2'],'ENUM':['E1','E2','E3','E4','E5'],'WAKE':['R1','R2','R3','R4','R5','R9']}[key]
    for r in q['rubric']:
        if r['criterion_id'] not in must:continue
        # Question/core boundary needs no mythical PDF statement about an
        # actual unobserved platform outcome. Recorded supporting request facts remain.
        ids=r['evidence_span_ids']
        if key=='WAKE' and r['criterion_id']=='R3':ids=['RW_OPTIONAL_RESET']
        if key=='ENUM' and r['criterion_id']=='E4':ids=['ENUM_ADDRESS']
        qs=[frag(spans[i]['chunk_id'],spans[i]['quote']) for i in ids]
        add(key,r['criterion_id'],r['criterion'],qs,ref(ppath))
        roles[key][-1]['scope_clarification']=clar

short=next(c for c in chunks if c['source_id']=='usb20_fw' and c['section']=='5.8.3' and c['page_or_anchor']=='p.81' and 'When a bulk transfer is complete' in c['content'])
sref=ref(H/'model-27b-cli-metric-v2-20261021/runs/01-short-27b/source-review.json')
for rid,a,b,meaning in [('S-payload',339,538,'Maximum packet-size context'),('S-complete',1687,1913,'Completion alternatives'),('S-next',1914,2021,'Retire current IRP, advance next')]:add('SHORT',rid,meaning,[frag(short['chunk_id'],short['content'][a:b])],sref)

gpath=H/'evidence-first-poc01/AIQUAL01-20261028/gold/gold.json';gold=load(gpath)
for ci,c in enumerate(gold['cases']):
    if c['case_id'] not in {c['case_key'] for c in selection['selected_cases']}:continue
    for ri,r in enumerate(c['required_roles']):
        qs=[{'quote':e['exact_quote'],'source_id':{'usb20':'usb20_fw','usb32':'usb32','superspeed_hub_lvs':'superspeed_hub_lvs'}[c['scope']],
            'revision':c['document']['revision'],'section':r['section'],'page_or_anchor':f"p.{e['physical_page_1based']}"} for e in r['evidence']]
        add(c['case_id'],r['role_id'],r['claim'],qs,ref(gpath,f'/cases/{ci}/required_roles/{ri}'),r['critical'])
save('role-witnesses.json',dict(roles))

def norm(t):return ''.join(t.split()).replace('|','')
def canonicalize(es):
    out=[];mapping=[]
    for e in es:
        text=e.get('content',e.get('quote',''));known=byid.get(e['chunk_id'])
        if known is None:
            matches=[c for c in bycontent.get(text,[]) if c['section']==e['section'] and c['page_or_anchor']==e['page_or_anchor']]
            known=matches[0] if len(matches)==1 else None
        valid=bool(known and (known['content']==text or text in known['content']))
        mapping.append({'saved_id':e['chunk_id'],'canonical_id':known['chunk_id'] if valid else None,'exact_content_metadata_match':valid,'saved_content_sha256':hashlib.sha256(text.encode()).hexdigest()})
        if valid:out.append({**known,'content':text})
    return out,mapping
def witness(q,es):
    scoped=[e for e in es if e['source_id']==q['source_id'] and e['revision']==q['revision']]
    # Match the exact illustrative text anywhere within the same owned source,
    # not a fixed ID. This is a witness check, not general semantic equivalence.
    found=[e for e in scoped if norm(q['quote']) in norm(e['content'])]
    if found:return {'retained':True,'mode':'ONE_CHUNK_CONTIGUOUS_WHITESPACE_TABLE_SEPARATOR_ONLY','chunk_ids':[e['chunk_id'] for e in found]}
    # Cross-chunk support is allowed only if consecutive canonical source chunks
    # are all selected. Do not concatenate a hidden gap or across source/revision.
    ordered=sorted(scoped,key=lambda e:order[e['chunk_id']]);runs=[]
    for e in ordered:
        if runs and order[e['chunk_id']]==order[runs[-1][-1]['chunk_id']]+1:runs[-1].append(e)
        else:runs.append([e])
    for run in runs:
        if len(run)>1 and norm(q['quote']) in norm(''.join(e['content'] for e in run)):
            return {'retained':True,'mode':'SOURCE_CONSECUTIVE_CHUNKS_NO_HIDDEN_GAP','chunk_ids':[e['chunk_id'] for e in run]}
    return {'retained':False,'mode':'NO_LITERAL_WITNESS; semantic_equivalence_not_inferred','chunk_ids':[]}
def assess(rs,es):
    out=[]
    for r in rs:
        fs=[{'witness':q,**witness(q,es)} for q in r['all_required_fragments']]
        retained=all(f['retained'] for f in fs)
        out.append({'role_id':r['role_id'],'critical':r['critical'],'boundary_only':r['boundary_only'],
            'retained':retained,'fragments':fs,'acceptance_source':r['acceptance_source']})
    return out
def meta(es):return [{k:e.get(k) for k in ['chunk_id','source_id','document','revision','section','page_or_anchor','chunk_kind','content_sha256']} for e in es]
results=[]
for case in selection['selected_cases']:
    key=case['case_key'];rp=O/'replays'/f'{key}.json';replay=load(rp);current=replay['formal_result'];rs=roles[key]
    newes,newmap=canonicalize(current['evidence']);pool=current['original_sources'];pool=[{**c,'content':c.get('content','')} for c in pool]
    oldcase=bycase.get(case.get('primary_record_id'));historic_ref=None
    if oldcase:
        oldraw=oldcase['prompt']['sent_evidence'];alias_binding=None
        request_path=Path(oldcase['prompt']['source']['path'])
        sidepath=request_path.parent/'sidecar.json';bindpath=request_path.parent/'prepared-binding.json'
        if not sidepath.exists():sidepath=request_path.parent/'prepared-sidecar.json'
        if sidepath.exists() and bindpath.exists():
            side=load(sidepath);binding=load(bindpath)
            assert binding['request_sha256']==sha(request_path)
            messages=load(request_path)['messages']
            wire=hashlib.sha256(json.dumps(messages,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
            assert binding['sidecar_wire_sha256']==wire
            prepared_sha=binding.get('source_prepared_sha256',binding.get('same_frozen_N1_packet_sha256'))
            assert prepared_sha==sha(request_path.parent/'original-prepared.json')
            canonicalraw=[]
            for e in oldraw:
                cid=side['aliases'][e['chunk_id']];c=byid[cid]
                assert c['content']==e['content'] and c['section']==e['section'] and c['page_or_anchor']==e['page_or_anchor']
                canonicalraw.append({**e,'chunk_id':cid})
            alias_binding={'request':ref(request_path),'sidecar':ref(sidepath),'binding':ref(bindpath),
                'original_prepared':ref(request_path.parent/'original-prepared.json'),
                'request_sha_verified':True,'messages_wire_sha_verified':True,'original_prepared_sha_verified':True,
                'aliases':side['aliases'],'all_sent_exact':True}
            oldes,oldmap=canonicalize(canonicalraw)
            for e,m in zip(oldraw,oldmap):m['saved_id']=e['chunk_id']
        else:oldes,oldmap=canonicalize(oldraw)
        historical={'record_id':oldcase['case_id'],'actual_prompt':oldcase['prompt']['source'],
            'raw_response':oldcase['raw_response'],'original_evaluations':oldcase['original_evaluations'],'later_annotations':oldcase['later_annotations'],
            'timing_recorded':oldcase['timing_recorded'],'source_binding_recorded':oldcase['source_binding_recorded'],
            'prompt_chars':sum(len(m['content']) for m in oldcase['prompt']['messages']),
            'evidence_content_chars':sum(len(e['content']) for e in oldraw),
            'serialized_evidence_chars_standard_json':len(json.dumps(oldraw,ensure_ascii=False)),
            'evidence_tokens':'NOT_SEPARATELY_RECORDED','old_pre_packer_candidate_pool':'NOT_RECORDED; actual-sent contents do not prove everything retrieved',
            'actual_sent_mapping':oldmap,'actual_sent_sources':meta(oldes),'alias_binding':alias_binding}
        refs[oldcase['prompt']['source']['path']]=sha(oldcase['prompt']['source']['path'])
    else:
        receipt=Path(case['historical_receipt']);raw=receipt.with_name(receipt.name.replace('.receipt.json','.response.raw.json'))
        old=load(raw);oldes,oldmap=canonicalize(old['evidence']);historic_ref=ref(raw)
        historical={'record_kind':'RETRIEVAL_ONLY_NO_MODEL_PROMPT','receipt':ref(receipt),'preview':historic_ref,
            'old_pre_packer_candidate_pool':'old original_sources separate from delivered preview',
            'actual_sent':'NOT_APPLICABLE_NO_MODEL','source_binding_recorded':{'corpus_sha256':old['corpus_sha256']},
            'actual_sent_mapping':oldmap,'actual_sent_sources':meta(oldes),'evidence_content_chars':sum(len(e['content']) for e in oldes),'evidence_tokens':'NOT_MEASURED'}
    oldroles=assess(rs,oldes);newroles=assess(rs,newes);corpusroles=assess(rs,chunks);poolroles=assess(rs,pool)
    historical['actual_sent_or_control_preview_evidence']=oldraw if oldcase else old['evidence']
    oldids={e['chunk_id'] for e in oldes};newids={e['chunk_id'] for e in newes}
    missingold=[r['role_id'] for r in oldroles if not r['retained'] and r['critical']]
    missingnew=[r['role_id'] for r in newroles if not r['retained'] and r['critical']]
    added=[r for r in missingold if r not in missingnew];lost=[r for r in missingnew if r not in missingold]
    knownidentity=all(m['exact_content_metadata_match'] for m in oldmap)
    # A known different answer contract/source scope prevents a controlled
    # end-to-end causal comparison. Evidence correspondence is explicitly narrower.
    status=('NOT_COMPARABLE' if not knownidentity else 'EVIDENCE_REGRESSED' if lost else
        'EVIDENCE_IMPROVED' if added else 'EVIDENCE_UNCHANGED_INCOMPLETE' if missingnew else 'EVIDENCE_UNCHANGED_COMPLETE')
    layers=[]
    if missingnew:
        for r in newroles:
            if not r['critical'] or r['retained']:continue
            cr=next(x for x in corpusroles if x['role_id']==r['role_id']);pr=next(x for x in poolroles if x['role_id']==r['role_id'])
            layers.append({'role_id':r['role_id'],'suspected_layer':'CORPUS_OR_LITERAL_REPRESENTATION_GAP' if not cr['retained'] else 'CURRENT_SELECTION_NOT_RETAINED' if not pr['retained'] else 'CURRENT_WINDOW_OR_PACKER_DROPPED','causal_certainty':'SOURCE_CHECK_REQUIRED; no model root cause assigned'})
    controls=[]
    for cid in case.get('within_question_control_record_ids',[]):
        c=bycase[cid];es,mp=canonicalize(c['prompt']['sent_evidence']);ar=assess(rs,es)
        controls.append({'record_id':cid,'prompt':c['prompt']['source'],'actual_sent_sources':meta(es),'source_mapping':mp,'roles':ar,'original_evaluations':c['original_evaluations'],'count_as_independent_question':False})
    results.append({'case_key':key,'kind':case['kind'],'question':case['question'],'scope':case['scope'],
        'evidence_change_status':status,'classification_level':'EXACT_SOURCE_WITNESS_CORRESPONDENCE; not end-to-end LLM comparison',
        'current_prompt_comparison_status':'NOT_COMPARABLE_NO_CURRENT_LLM_PROMPT' if oldcase else 'NOT_APPLICABLE_RETRIEVAL_ONLY',
        'controlled_algorithm_improvement':'NOT_ESTABLISHED','answer_contract_comparable':False,
        'confounders':['Old typed/free-answer contract vs current evidence-only contract; current entry builds/sends no Prompt.',
            'Old global source pool may include multiple specifications; current explicit scope differs.'] if oldcase else ['Retrieval-only control; no 27B answer exists.'],
        'full_old_corpus_identity':'RECORDED_MATCH' if oldcase and corpus['corpus_sha256'] in str(oldcase['source_binding_recorded']) else 'FINGERPRINT_NAMESPACE_BRIDGED_EXACT_MATCH' if oldcase and alias_binding and load(O/'corpus-identity-bridge.json')['matches_saved_native'] else 'CONTROL_CORPUS_SHA_MATCH' if not oldcase and old['corpus_sha256']==corpus['corpus_sha256'] else 'FULL_CORPUS_EQUIVALENCE_NOT_ESTABLISHED; sent chunks mapped individually',
        'official_evidence_check':'PENDING_DIRECT_PDF_CHECK',
        'historical':historical,'historical_within_question_controls':controls,
        'current':{'replay':ref(rp),'retrieval_trace':current['retrieval_trace'],'candidate_pool_sources':meta(pool),
            'packed_sources':meta(newes),'packed_windows':current['evidence'],
            'pdf_projection':current['pdf_layout'],'bundle_status':current['bundle']['status'],
            'actual_prompt':'NOT_BUILT_BY_FORMAL_EVIDENCE_FIRST_ENTRY','actually_sent_to_model':False,
            'max_chunks':20,'max_serialized_evidence_chars':39739,'budget_trace':current['retrieval_trace']['budget'],
            'bundle_content_chars':sum(len(e['quote']) for e in current['evidence']),
            'LLM_tokens':None,'token_boundary':'No tokenizer/model called; no actual current LLM Prompt to count.'},
        'roles':{'old_actual_sent_or_control_preview':oldroles,'current_owned_candidates':poolroles,'current_packed_preview':newroles,'current_frozen_corpus':corpusroles},
        'missing_old_critical_roles':missingold,'missing_new_critical_roles':missingnew,'critical_roles_added':added,'critical_roles_lost':lost,
        'source_delta':{'added_canonical_ids':sorted(newids-oldids),'dropped_canonical_ids':sorted(oldids-newids),
            'historical_source_counts':dict(collections.Counter(e['source_id'] for e in oldes)),
            'current_source_counts':dict(collections.Counter(e['source_id'] for e in newes)),
            'foreign_sources_current':[]},
        'suspected_fault_layers':layers,'failure_cause':'NOT_ASSIGNED_IN_QA_ATTR_02','irrelevance':'NO_NEW_FOREIGN_SOURCE_ALLOWED; topical relevance not equated with completeness'})
save('qa-attr-02-evidence-diff.json',{'slice':'QA-ATTR-02','status':'DRAFT_PENDING_INDEPENDENT_REVIEW','new_model_calls':0,'Apple_calls':0,'downloads':0,
    'classification_policy':'Literal, source-bound witness retention. Missing witness is conservative and requires manual equivalence review; no new model answer scoring. Status is evidence-plane only. End-to-end contract changes remain NOT_COMPARABLE.',
    'counts':{'selected':len(results),'historical_model_questions':16,'retrieval_only_controls':4},'cases':results,'sources_sha256':refs,
    'old_scores_overwritten':False,'new_evaluator_run':False,'QA_ATTR_03_started':False})
for c in results:print(c['case_key'],c['evidence_change_status'],'oldmissing',c['missing_old_critical_roles'],'newmissing',c['missing_new_critical_roles'])
