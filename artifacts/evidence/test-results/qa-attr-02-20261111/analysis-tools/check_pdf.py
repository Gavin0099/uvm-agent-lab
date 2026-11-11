"""Verify local official PDF pins and complete pages; no downloads or corpus edits."""
from pathlib import Path
import json, hashlib, re, socket, subprocess
import pdfplumber
O=Path(__file__).parent;H=Path('/Users/sw1/Desktop/uvm-agent-lab/artifacts/evidence/test-results')
def deny(*a,**k):raise RuntimeError('Network/process forbidden in PDF read')
socket.socket.connect=deny;socket.create_connection=deny;subprocess.Popen=deny
def norm(t):return ''.join(t.split()).replace('|','')
g=json.loads((H/'evidence-first-poc01/AIQUAL01-20261028/gold/gold.json').read_text())
sources={};pages={};out=[]
for scope,d in g['documents'].items():
    p=Path(d['pdf_path']);actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==d['pdf_sha256']
    sources[scope]={'path':str(p),'sha256':actual,'revision':d['revision']}
    pages[scope]={}
roles=json.loads((O/'role-witnesses.json').read_text())
for scope,d in sources.items():
    wanted=set()
    for rs in roles.values():
        for r in rs:
            for q in r['all_required_fragments']:
                s='usb20' if q['source_id'] in ('usb20_fw','usb20_se') else q['source_id']
                if s==scope:wanted.add(int(q['page_or_anchor'].split('.')[-1]))
    with pdfplumber.open(d['path']) as pdf:
        for n in sorted(wanted):
            text=pdf.pages[n-1].extract_text() or '';pages[scope][n]=text
            folder=O/'pdf-pages';folder.mkdir(exist_ok=True)
            (folder/f'{scope}-page-{n}.txt').write_text(text+'\n')
for key,rs in roles.items():
    for r in rs:
        checked=[]
        for q in r['all_required_fragments']:
            scope='usb20' if q['source_id'] in ('usb20_fw','usb20_se') else q['source_id'];n=int(q['page_or_anchor'].split('.')[-1]);text=pages[scope][n]
            checked.append({'quote':q['quote'],'source_id':q['source_id'],'pdf':sources[scope],'physical_page_1based':n,
                'full_page_text':str(O/'pdf-pages'/f'{scope}-page-{n}.txt'),
                'text_sha256':hashlib.sha256((text+'\n').encode()).hexdigest(),
                'contiguous_whitespace_separator_match':norm(q['quote']) in norm(text),
                'boundary':'Text extraction alone does not prove table column semantics; table rows require visual/geometry review.'})
        out.append({'case_key':key,'role_id':r['role_id'],'fragments':checked,'all_text_witnesses':all(x['contiguous_whitespace_separator_match'] for x in checked)})
(O/'official-pdf-check.json').write_text(json.dumps({'sources':sources,'pages_read':sum(len(p) for p in pages.values()),'role_checks':out},ensure_ascii=False,indent=2)+'\n')
print('pages',sum(len(p) for p in pages.values()),'roles',len(out),'literal mismatch',[(r['case_key'],r['role_id']) for r in out if not r['all_text_witnesses']])
