"""Apply independently cited equivalence decisions; preserve literal diagnostics."""
from pathlib import Path
import json,hashlib,collections
O=Path(__file__).parent
R=Path('/Users/sw1/Desktop/uvm-agent-lab');H=R/'artifacts/evidence/test-results'
load=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,j):(O/name).write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
d=load(O/'qa-attr-02-evidence-diff.json');selection=load(O/'qa-attr-02-case-selection.json')
reviewpath=O/'review-source-pass.json'
if not reviewpath.exists():raise RuntimeError('Independent source-equivalence record required')
review=load(reviewpath)
# Explicit records are prepared by the independent reviewer, not inferred by
# this finalizer. Each review item has stage/role and canonical exact spans.
decisions=review['equivalence_decisions']
corpus={c['chunk_id']:c for c in load(O/'current-corpus-readonly.json')['chunks']}
for decision in decisions:
    c=next(c for c in d['cases'] if c['case_key']==decision['case_key'])
    stage=decision['stage'];role=next(r for r in c['roles'][stage] if r['role_id']==decision['role_id'])
    for s in decision['support_spans']:
        src=corpus[s['chunk_id']];assert src['content'][s['start']:s['end']]==s['quote']
        if stage=='current_packed_preview':
            assert any(w['chunk_id']==s['chunk_id'] and w['start']<=s['start'] and w['end']>=s['end'] for w in c['current']['packed_windows'])
        elif stage=='old_actual_sent_or_control_preview':
            assert any(e['chunk_id']==s['chunk_id'] for e in c['historical']['actual_sent_sources'])
    role['literal_witness_retained']=role['retained'];role['source_role_retained']=decision['retained']
    role['independent_source_equivalence']={**decision,'review_ref':{'path':str(reviewpath),'sha256':sha(reviewpath)}}
    if stage=='current_packed_preview':
        for other in ['current_owned_candidates','current_frozen_corpus']:
            parent=next(r for r in c['roles'][other] if r['role_id']==decision['role_id'])
            parent['source_role_retained']=decision['retained']
            parent['independent_source_equivalence']=role['independent_source_equivalence']

scorerpath=H/'quality-loop-20261104/scorer_candidate_eval.json';scorer=load(scorerpath)
pdf=load(O/'official-pdf-check.json')
quality={
 'Q005':'JUSTIFIED_RETRIEVAL_ABSTENTION in primary; A1 separate contradicted-absence refusal control',
 'Q002':'DIRECT_SUPPORT; original parser/evaluator PASS','Q007':'DIRECT_SUPPORT; original parser/evaluator PASS',
 'Q010':'DIRECT_SUPPORT; original parser/evaluator PASS','Q006':'DIRECT_SUPPORT; original parser/evaluator PASS',
 'Q012':'DIRECT_SUPPORT_AS_TEST_PROCEDURE; original parser/evaluator PASS',
 'Q011':'Original frozen citation-policy/parser FAIL despite joint source support; not a proved input gap',
 'P01':'Original fully_qualified true','P02':'Original fully_qualified true',
 'P03':'Original semantic FAIL, coverage PASS; per-claim selected-quotation composition, USB falsehood not established',
 'P04':'Original citation/semantic/coverage FAIL; preserve quote and frame/speed qualification findings',
 'P05':'Original schema/semantic/coverage FAIL; preserve original negative-determination source review',
 'SHORT':'Original semantic PASS, strict chosen-quotation coverage FAIL; necessary source available in sent E2',
 'ENUM':'Original semantic PASS, coverage COMPLETE; selected success control',
 'WAKE':'Original semantic FAIL, coverage PARTIAL; platform-outcome overstatement and unsupported causal explanation',
 'SPEED':'Original semantic PASS, coverage COMPLETE'}
for c in d['cases']:
    old=c['roles']['old_actual_sent_or_control_preview'];new=c['roles']['current_packed_preview']
    for rs in c['roles'].values():
        for r in rs:r.setdefault('source_role_retained',r['retained'])
    c['literal_missing_old_critical_roles']=c.get('literal_missing_old_critical_roles',c['missing_old_critical_roles']);c['literal_missing_new_critical_roles']=c.get('literal_missing_new_critical_roles',c['missing_new_critical_roles'])
    mo=[r['role_id'] for r in old if r['critical'] and not r['source_role_retained']]
    mn=[r['role_id'] for r in new if r['critical'] and not r['source_role_retained']]
    added=[r for r in mo if r not in mn];lost=[r for r in mn if r not in mo]
    c.update(missing_old_critical_roles=mo,missing_new_critical_roles=mn,critical_roles_added=added,critical_roles_lost=lost)
    c['literal_evidence_change_status']=c.get('literal_evidence_change_status',c['evidence_change_status'])
    c['evidence_change_status']='EVIDENCE_REGRESSED' if lost else 'EVIDENCE_IMPROVED' if added else 'EVIDENCE_UNCHANGED_INCOMPLETE' if mn else 'EVIDENCE_UNCHANGED_COMPLETE'
    c['classification_level']='SOURCE_ROLE_CORRESPONDENCE with independent equivalent-source adjudication; preview only, no answer scoring'
    c['official_evidence_check']={'status':'PRESENT_IN_PINNED_OFFICIAL_PDF','check':str(O/'official-pdf-check.json'),
        'visual_check':str(O/'pdf-visual-review.json'),'boundary':'Question-stated unknown platform/device facts remain unknown; no human expert certification.'}
    if c['case_key'] in quality:c['historical']['primary_quality_summary']=quality[c['case_key']]
    c['suspected_fault_layers']=[x for x in c['suspected_fault_layers'] if x['role_id'] in mn]
    replay=load(O/'replays'/f"{c['case_key']}.json")
    ranks={x['chunk_id']:x['rank'] for x in replay['post_selection_readonly_all_rank_diagnostic']}
    c['remaining_gap_rank_diagnostics']=[]
    for role in c['roles']['current_frozen_corpus']:
        if role['role_id'] not in mn:continue
        c['remaining_gap_rank_diagnostics'].append({'role_id':role['role_id'],
            'witness_chunk_ranks':[{'chunk_id':cid,'primary_diagnostic_rank':ranks.get(cid)} for f in role['fragments'] for cid in f['chunk_ids']],
            'boundary':'Diagnostic all-rank query after selection; not actual formal selected candidates and never fed back.'})
    if c['case_key']=='AIQUAL01-U32-04':
        c['pdf_supplement_boundary']='Pinned validated PDF grid projects all six columns, including wValue Zero/wLength Two. It is separate PDF-derived display evidence; unchanged frozen text still incomplete, and no LLM Prompt receives it.'
    if c['case_key']=='AIQUAL01-U20-04':
        c['acceptance_gap']='Original AI Gold packed_fields role does not fully resolve Table8-3 transfer-type mapping. Keep versioned errata proposal separate; four-role retention is not complete answer qualification.'
    if c['case_key'] in ['AIQUAL01-U20-03','AIQUAL01-U20-04']:
        c['prior_candidate_scorer_annotation']={'source':str(scorerpath),'sha256':sha(scorerpath),
            'original_baseline':scorer['baseline'],'candidate_only':scorer['candidate'],
            'changed_roles':[r for r in scorer['changed_roles'] if r['case_id']==c['case_key']],
            'not_applied_as_current_formal_score':True}
    c['relevance_review']={'foreign_or_wrong_revision_sources_new':0,
        'scope':'Each selected source is bound to selected scope and pinned revision; relevance is distinct from correctness.',
        'nonessential_example':'ENUM contains seven endpoint-descriptor chunks9.6.6; these are lower priority than general enumeration, but do not remove core role support. No full topical precision metric.' if c['case_key']=='ENUM' else 'No exhaustive semantic ranking of every background chunk; no unsupported claim of zero irrelevant evidence.'}

models=[c for c in d['cases'] if c['kind']=='HISTORICAL_MODEL_QUESTION'];controls=[c for c in d['cases'] if c not in models]
d['summary_counts']={'historical_model_questions':16,'retrieval_only_controls':4,
    'historical_primary_missing_necessary_evidence':sum(bool(c['missing_old_critical_roles']) for c in models),
    'current_preview_fully_closes_primary_gaps':sum(bool(c['missing_old_critical_roles']) and not c['missing_new_critical_roles'] for c in models),
    'current_actual_llm_prompt_gap_closure_verified':0,
    'current_preview_critical_regression_cases':sum(bool(c['critical_roles_lost']) for c in d['cases']),
    'model_question_evidence_statuses':dict(collections.Counter(c['evidence_change_status'] for c in models)),
    'retrieval_control_evidence_statuses':dict(collections.Counter(c['evidence_change_status'] for c in controls)),
    'primary_quality_failure_with_complete_sent_evidence':['Q011','P03','P04','P05','SHORT','WAKE'],
    'additional_same_question_complete_input_refusal_control':'Q005 A1; not an extra independent sample',
    'formal_current_prompt_not_comparable_cases':16}
d['readiness']={'QA_ATTR_03_data_sufficient':True,'scope':'Known-case source/contract/claim-quotation attribution; not general accuracy or current LLM reconnection qualification.',
    'remaining_limits':['No new current LLM Prompt exists in Evidence-first entry.','Old pre-packer retrieval pools generally not saved.','U20-04 Gold mapping incomplete; U32-04 frozen table and LVS-03 retained-source gaps persist.'],
    'QA_ATTR_03_executed':False,'new_model_test_authorized_or_started':False}
d['sources_sha256'][str(reviewpath)]=sha(reviewpath)
d['sources_sha256'][str(scorerpath)]=sha(scorerpath)
d['status']='ANALYSIS_COMPLETE_PENDING_FULL_INDEPENDENT_REVIEW'
save('qa-attr-02-evidence-diff.json',d)
lines=['# QA-ATTR-02：歷史與目前 RAG 證據比較','',
'已完成20個獨立問題的唯讀重放：16個歷史27B問題，另列4個retrieval-only控制。165筆完成紀錄中108筆完整Prompt只對應39種精確問句；本輪不把重複實驗當獨立樣本，也不計合併答題正確率。','',
'**結論：選定16題的歷史主基準，只有Q005可確認缺必要證據；目前Evidence-first預覽已補齊。其餘15題主基準的必要來源角色原本就已具備，其中6題仍曾有品質／引用／契約失敗。這批失敗不能一概繼續歸咎於RAG找不到原文。**','',
'**比較界線：目前正式Evidence-first服務只回傳證據預覽，沒有建立或送出LLM Prompt。以下IMPROVED／COMPLETE全部指來源角色與預覽證據；16題的正式新舊LLM Prompt比較均為NOT_COMPARABLE_NO_CURRENT_LLM_PROMPT。未證明目前27B答得更好，亦未證明純檢索演算法造成改善。**','',
'| 摘要問題 | 實際結果 |','|---|---|',
'| A. 歷史主基準真正缺必要證據 | 1/16：Q005 early seven-live3；其當時拒答有依據 |',
'| B. 目前補齊幾題 | 預覽1/1補齊；實際新LLM Prompt補齊尚未驗證 |',
'| C. 新Critical回歸 | 20題範圍內0個來源角色回歸；不等於所有材料／格式完全保留 |',
'| D. 完整輸入仍失敗 | 6個主案例Q011、P03、P04、P05、SHORT、WAKE；另Q005 A1為同題完整輸入仍拒答控制 |',
'| E. 能否進入03 | 有足夠資料做這批已知案例的分層歸因；本輪沒有啟動03 |','',
'## 每題來源角色比較','',
'| 問題 | 舊必要來源缺口 | 新預覽缺口 | 證據變化 |','|---|---|---|---|']
for c in d['cases']:lines.append('| '+c['case_key']+' | '+(', '.join(c['missing_old_critical_roles']) or '無')+' | '+(', '.join(c['missing_new_critical_roles']) or '無')+' | '+c['evidence_change_status']+' |')
lines+=['','## 判讀與未解決缺口','',
'- Q005：舊主基準沒有p450續表標題與PORT_POWER/Port/8列，目前二者均選入。歷史主基準混入USB3.2，目前限定usb20；來源資格與選取條件已改，不能歸因為單一演算法提升。A1則原本就收到完整列／關聯，當時缺證據的拒答理由已被原Review反駁。B與Reconnect成功仍是另條件觀察。',
'- Q011：來源角色完整，不表示Frozen citation allowlist／Parser接受；原額外p485引用與顯示限定條件問題保留。P03則原coverage PASS、semantic FAIL，主要發現是個別claim引用沒有覆蓋其複合主張；未證明USB事實錯誤。SHORT原必要S-payload在輸入內，但沒有被答案選為引用。',
'- P04／P05與WAKE：保留原始quote、schema、規範限定／平台結果強度問題，不重跑或覆寫原評分。新版證據完整也不證明答案會改善。ENUM與SPEED是歷史成功控制。',
'- Enumeration：原9.1.2段落未入選，但9.2.1、9.1.1.4、9.4.3及GET_DESCRIPTOR表共同支持原核心，獨立來源Review排除字面比對造成的假回歸。額外端點描述符片段屬較低優先背景，不聲稱整包零無關資料。',
'- U20-03：舊GET_INTERFACE表列與currently selected alternate setting段落已有等價支持，為UNCHANGED_COMPLETE。Nov4的31/35→33/35只是候選scorer差異，未變成正式新分數。',
'- U20-04：目前選入原缺的periodic endpoint排除條件；原packed_fields scorer爭議另列。原AI Gold仍未完整涵蓋Table8-3 transfer-type mapping，因此四角色齊備不等於整題正式合格。',
'- U32-04：目前補回count/reset段，但Frozen Corpus request表仍缺欄位；官方PDF六欄完整，已驗證的PDF grid補充另列，不能當作Frozen Chunk或已送入LLM的內容。',
'- LVS-03：UFP兩種enabled條件的完整分支與tiered deadline仍未全部選入；必要原文存在Corpus，保留來源選取／字元預算線索，未確認新根因或修復。','',
'## 重放與來源身份','',
'本輪以目前工作樹的EvidenceService.query入口在隔離程序中重放，保留HEAD與程式SHA；未核實既有Tunnel程序載入的是同一份程式，也未向其發請求、重啟或變更。正式入口本身未修改；20個查詢沿用max20chunks／39,739 serialized-evidence字元預算。原始候選、baseline windows、保守packer bundle、PDF補充及額外all-rank診斷分開保存；all-rank在選取後執行，不回饋或放寬正式預算。舊版未保存的pre-packer候選池明標未知，不能從實際sent文字倒推全部retrieval候選。','',
'目前Corpus為4330 chunks／8aef81aa…；Native六份歷史請求的120筆E1等alias逐題以sidecar、request SHA、messages wire SHA及原prepared綁定解回canonical來源，文字／位置完全相符。以原projection fingerprint算法獨立重算得4d8eec32…，確認不同hash namespace對應同一Corpus，而非以字串不同猜測換版。','',
'3份本機官方PDF雜湊核對、32個完整頁面文字核對及4頁圖像檢視；Q006表格逐欄閱讀確認，未把文字抽取交錯誤當官方缺資料。所有來源、頁碼、ChunkID、SHA、角色引文／offset、原始評分與候選差異均在JSON。這是AI來源審核，未冒稱人工USB工程師核准。','',
'歷史總Prompt tokens沿用保存紀錄，Evidence-only tokens多數未單獨保存，明標缺口；本輪不呼叫Tokenizer補算。新預覽只量測各來源／bundle字元與真實budget trace，沒有可供計算的新LLM Prompt。','',
'## 驗證與交付邊界','',
'artifact-integrity.json包含6組真實資料不變式與9種負向污染控制（含SHORT sidecar遺漏回歸）；另有來源雜湊與工作樹保存檢查。這些驗證報告可信度，不代表USB回答合格。Scoped Independent Review見qa-attr-02-review.md。','',
'0 LLM／Apple／下載；未修改Frozen Corpus、Gold、Digest、Prompt、Parser、Evaluator、正式Retrieval／Packer或AI Governance。未Commit／Push／Deploy，未操作服務、Tunnel或Access Code。僅追加本Slice必要PLAN／canonical memory記錄。','',
'建議下一步是對上述完整輸入仍失敗的已知案例做QA-ATTR-03分層歸因；目前資料不支持先擴張RAG或投入SAG2，也不支持立即重跑27B。此建議不構成下一Slice或模型呼叫授權。']
(O/'qa-attr-02-summary.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(d['summary_counts'],ensure_ascii=False))
