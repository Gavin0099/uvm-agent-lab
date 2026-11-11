"""Bounded, network-disabled EvidenceService replay; outputs outside repository."""
from pathlib import Path
import sys, json, hashlib, collections, socket, subprocess, time

R=Path('/Users/sw1/Desktop/uvm-agent-lab')
O=Path(__file__).parent
I=Path('/Users/sw1/gv100h-poc/qa-attr-01-20261111/historical-qa-inventory.json')
H=R/'artifacts/evidence/test-results'
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(name,data):
    p=O/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
inv=json.loads(I.read_text());cases=inv['cases'];byid={c['case_id']:c for c in cases}
full=[c for c in cases if c['prompt']['status']=='COMPLETE_SAVED_PROMPT']
groups=collections.defaultdict(list)
for c in cases:
    # Exact original text grouping is reproducible; explicit semantic aliases below
    # are preserved as related questions, never silently declared equivalent.
    key=c['question_text'] or 'MISSING_WORDING/'+c['case_id']
    groups[key].append(c)
def compact(c):
    p=c['prompt']
    return {'case_id':c['case_id'],'question_id':c['question_id'],'family':c['family'],
        'prompt_status':p['status'],'prompt_message_hashes':p.get('message_content_sha256'),
        'corpus_identity_recorded':{k:v for k,v in c['source_binding_recorded'].items() if k!='sent_source_metadata'},
        'experiment_identity':c['rag_prompt_version_recorded'],'record':c['record']}

selected=[]
def pick(cid,key,scope,tags,related=()):
    c=byid[cid]
    assert c in full
    selected.append({'case_key':key,'kind':'HISTORICAL_MODEL_QUESTION','scope':scope,
        'question':c['question_text'],'selection_tags':tags,'primary_record_id':cid,
        'exact_question_record_ids':[z['case_id'] for z in groups[c['question_text']]],
        'within_question_control_record_ids':list(related),'dedup_weight':1})
base='typed-claim-seven-live3-20261002-01/'
pick(base+'6','Q005','usb20',['historical_justified_refusal','table_relation','mandatory_control'],[
    'HTTP/typed-claim-q005-ab-live-20261003/A1','HTTP/typed-claim-q005-ab-live-20261003/B','RECONNECT_20261111/Q005'])
for n,key,scope,tags in [(0,'Q002','usb20',['historical_success','optional_stage','cross_chunk']),
 (1,'Q007','usb20',['historical_success','multiple_conditions']),
 (2,'Q010','usb32',['historical_success','state_conditions']),
 (3,'Q006','usb20',['historical_success','table_units_conditions']),
 (4,'Q012','superspeed_hub_lvs',['historical_success','timer_conditions']),
 (5,'Q011','usb32',['contract_failure','cross_page','source_allowlist_dispute'])]:pick(base+str(n),key,scope,tags)
for n in range(1,6):pick(f'model-27b-controlled-qa-live-r2-20261022/P0{n}-27b',f'P0{n}','usb20',
    ['historical_success' if n<=2 else 'historical_quality_failure','multi_conditions'])
pick('model-27b-cli-metric-v2-20261021/01-short-27b','SHORT','usb20',['historical_coverage_failure','cross_section'])
for marker,key,tags in [('enumeration-full','ENUM',['historical_success_control','cross_section']),
 ('wakeup-full','WAKE',['historical_quality_failure','conditions']),('speed-full','SPEED',['success_control','simple_numeric'])]:
    c=next(c for c in full if c['family']=='spec-qa-performance-ab-live-20261016' and '/'+marker+'/' in c['case_id'])
    pick(c['case_id'],key,'usb20',tags)
gold=json.loads((H/'evidence-first-poc01/AIQUAL01-20261028/gold/questions.json').read_text())
for c in gold['cases']:
    if c['case_id'].split('AIQUAL01-')[-1] in ['U20-03','U20-04','U32-04','LVS-03']:
        selected.append({'case_key':c['case_id'],'kind':'RETRIEVAL_ONLY_CONTROL','scope':c['scope'],
            'question':c['question'],'selection_tags':['requested_gap_control','not_a_model_failure'],
            'historical_receipt':str(H/'evidence-first-poc01/AIQUAL01-20261028/search'/f"{c['case_id']}.receipt.json"),
            'dedup_weight':0,'boundary':'Separate retrieval-only appendix, excluded from historical model-question denominator'})
assert len(selected)==20 and len({c['question'] for c in selected})==20
selection={'slice':'QA-ATTR-02','inventory':{'path':str(I),'sha256':sha(I.read_bytes())},
    'counts':{'completion_records':len(cases),'complete_prompt_records':len(full),
        'complete_prompt_exact_question_groups':len({c['question_text'] for c in full}),
        'all_exact_wording_groups_excluding_missing':len({c['question_text'] for c in cases if c['question_text']}),
        'selected_independent_questions':20,'historical_model_questions':16,'retrieval_only_controls':4},
    'grouping_policy':'Exact original question text; repeated runs remain experimental observations with weight one per selected question. Related wording is not assumed equivalent. No pooled model accuracy.',
    'grouping':[{'question':q,'records':[compact(c) for c in cs]} for q,cs in groups.items()],
    'selected_cases':selected,
    'exclusion_policy':'57 incomplete Prompt records cannot establish old actual-sent completeness; errors/adapter-only/other models remain outside selected historical answer cohort.',
    'selection_boundary':'Purposive representative cases, not random/generalization accuracy sample; controls and successful cases included before replay outcomes.'}
save('qa-attr-02-case-selection.json',selection)

def deny(*a,**k):raise RuntimeError('QA-ATTR-02 network/process forbidden')
socket.socket.connect=deny;socket.create_connection=deny
subprocess.Popen=deny
sys.path.insert(0,str(R))
from gv100h.spec_qa.evidence_first.service import EvidenceService
service=EvidenceService()
chunks=[c.model_dump(mode='json') for c in service.search.corpus.chunks]
save('current-corpus-readonly.json',{'corpus_sha256':service.search.corpus.corpus_sha256,'chunks':chunks})
for c in selected:
    start=time.perf_counter();result=service.query(c['question'],scope=c['scope'])
    assert result['models_loaded']==0 and result['generations']==0 and result['answer'] is None
    # Diagnostic all-rank view uses the exact production retrieval_query after
    # selection. It is never fed back to the service or used to change the bundle.
    trace=result.get('retrieval_trace',{});ranks=[]
    if trace.get('retriever_called'):
        retriever=service.search._retriever(c['scope'])
        hits=retriever.query(trace['retrieval_query'],top_k=len(retriever))
        ranks=[{'rank':i,'chunk_id':h.chunk.chunk_id,'score':h.score} for i,h in enumerate(hits,1)]
    save('replays/'+c['case_key']+'.json',{'case_key':c['case_key'],'formal_result':result,
        'post_selection_readonly_all_rank_diagnostic':ranks,'wall_seconds':time.perf_counter()-start,
        'LLM_prompt_status':'NOT_BUILT_BY_THIS_ENTRYPOINT','LLM_sent':False,
        'budget':{'max_chunks':20,'max_serialized_evidence_chars':39739,'evidence_tokens':'NOT_MEASURED'},
        'no_network_process_guard':True})
    print(c['case_key'],result['status'],len(result['evidence']),result.get('bundle',{}).get('status'),flush=True)
save('replay-execution.json',{'formal_queries':len(selected),'post_selection_rank_diagnostics':sum(bool(json.loads((O/'replays'/f"{c['case_key']}.json").read_text())['post_selection_readonly_all_rank_diagnostic']) for c in selected),
    'models_loaded':0,'generations':0,'Apple_calls':0,'downloads':0,'network_and_subprocess_blocked':True,
    'loaded_inference_modules':[x for x in sys.modules if x.startswith(('mlx','torch','transformers','ollama'))],
    'entrypoint':'EvidenceService.query (unchanged formal Evidence-first service)',
    'current_llm_prompt':'NOT_BUILT; no synthetic connection to old LLM adapter',
    'selected_bundle_is_not_sent_prompt':True})
