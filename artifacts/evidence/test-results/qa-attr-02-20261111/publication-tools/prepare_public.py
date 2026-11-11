from pathlib import Path
import json, hashlib, shutil

ROOT=Path('/Users/sw1/Desktop/uvm-agent-lab')
OLD=Path('/Users/sw1/gv100h-poc/qa-attr-02-20261111')
PRIVATE=Path(__file__).parent/'private-review-bundle'
WORK=Path('/Users/sw1/gv100h-poc/qa-attr-02-publish-worktree')
OUT=WORK/'artifacts/evidence/test-results/qa-attr-02-20261111'
OUT.mkdir(exist_ok=True,parents=True)
REPO='https://github.com/Gavin0099/uvm-agent-lab.git'
sha=lambda b:hashlib.sha256(b).hexdigest()
RAW_KEYS={'quote','exact_quote','original_quote','original_text','raw_text','content','messages','text','content_utf8','original_content','caption_lines','source_text','source_excerpt','tables'}
def withheld(value):
    raw=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,separators=(',',':'))
    return {'withheld':True,'sha256_utf8':sha(raw.encode()),'unicode_chars':len(raw),
        'reason':'Original evidence text retained in private staging; this public projection cannot reverify its semantics.'}
def project(value,key=''):
    if key in RAW_KEYS and value is not None:return withheld(value)
    if isinstance(value,str) and len(value)>240:return withheld(value)
    if isinstance(value,dict):return {k:project(v,k) for k,v in value.items()}
    if isinstance(value,list):return [project(v,key) for v in value]
    return value
published={}
def public_json(source,name):
    raw=Path(source).read_bytes();data=project(json.loads(raw))
    envelope={'schema':'qa-attr-02-public-projection.v1','repository':REPO,
        'original_path':str(source),'original_file_sha256':sha(raw),
        'projection_boundary':'Public metadata only; evidence text and long captured strings withheld. Original reports are unchanged in private staging.',
        'data':data}
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+'\n')
    published[str(source)]={'public_path':name,'original_file_sha256':sha(raw),'projection_file_sha256':sha(p.read_bytes())}

for n in ['qa-attr-02-case-selection.json','qa-attr-02-evidence-diff.json','review.json','review-source-pass.json',
 'artifact-integrity.json','replay-execution.json','corpus-identity-bridge.json','delivery-preservation.json']:
    public_json(OLD/n,n)
for n in ['qa-attr-02-summary.md','qa-attr-02-review.md']:
    banner='> 公開審查副本：本機原始報告未改。此分支的 JSON 已去除原文；原報告所稱完整引文、Prompt／wire 與 PDF 核對指私人原始資料。公開版可審查方法與元資料，不能獨立重做原文語意驗證。原始 SHA 見 publication-provenance.json。\n\n'
    (OUT/n).write_text(banner+(OLD/n).read_text())
    published[str(OLD/n)]={'public_path':n,'original_file_sha256':sha((OLD/n).read_bytes()),'exact_original_bytes':False,'projection':'Original report plus explicit public-evidence boundary banner.'}
for p in (OLD/'replays').glob('*.json'):public_json(p,'replays/'+p.name)
for p in OLD.glob('*.py'):
    dest=OUT/'analysis-tools'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
    published[str(p)]={'public_path':str(dest.relative_to(OUT)),'original_file_sha256':sha(p.read_bytes()),'exact_original_bytes':True}
corpus=json.loads((OLD/'current-corpus-readonly.json').read_text())
index={'schema':'qa-attr-02-public-corpus-index.v1','repository':REPO,'original_corpus_sha256':corpus['corpus_sha256'],
 'original_file_sha256':sha((OLD/'current-corpus-readonly.json').read_bytes()),
 'boundary':'Metadata index, not a reconstruction of the official corpus; no raw official text is published.',
 'chunks':[{k:v for k,v in c.items() if k!='content'}|{'content_chars':len(c['content'])} for c in corpus['chunks']]}
(OUT/'corpus-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
# Inert source snapshots establish which dirty-worktree implementation ran;
# they never replace the actual product files on this publication branch.
for p in (PRIVATE/'source-snapshots').rglob('*'):
    if p.is_file() and p.suffix=='.py':
        dest=OUT/p.relative_to(PRIVATE);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)

(OUT/'publication-provenance.json').write_text(json.dumps({'schema':'qa-attr-02-publication.v1','repository':REPO,
 'analysis_base_commit':'873c2061836fb39059e5d8289a4ecda4c820a2ee',
 'publication_base_commit':'71aeb028f95d814505f66be262ae404f22d9ed96',
 'owner_authority':'2026-11-11 Owner: 推上去才能給別的agent review; authorizes scoped commit/push, superseding earlier no-commit/push for delivery only.',
 'source_policy':'PLAN section0: official raw bytes remain in operator-controlled private staging and are not committed to this public repository.',
 'original_artifacts':published,
 'withheld':['Official PDF bytes/page text/rendered page images','Full corpus contents','Raw prompts/completions and source files with official evidence text','Credentials and unrelated dirty working-tree files'],
 'remote_review_can_verify':['Analysis implementation','Question grouping/denominators','Metadata/source identity consistency','Recorded budgets and no-model-call receipts','Claim boundaries and existing review findings'],
 'remote_review_cannot_reverify':['Verbatim source fidelity','Meaning of withheld official evidence','Original complete request/wire bytes','A fresh RAG run or improved LLM answers'],
 'new_model_calls':0,'Apple_calls':0,'new_retrieval_queries':0,'semantic_rereview_claimed':False},ensure_ascii=False,indent=2)+'\n')
print('Public review projection:',len(list(OUT.rglob('*'))),'entries;',sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),'bytes')
