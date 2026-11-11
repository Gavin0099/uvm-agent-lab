"""Evidence-only CLI; opt-in and CPU-only, no generation path."""
import argparse
import json
import os
import sys

from .search import SCOPES
from .service import EvidenceService


def format_text(result):
    lines = ['USB 規格證據查詢', result['notice'], *result['unconfirmed'],
             '問題：' + result['question'], '來源範圍：' + result['scope'],
             'Request：' + result['request_id'], 'Corpus SHA-256：' + result['corpus_sha256']]
    if result.get('bundle'):
        lines.append('證據包：' + result['bundle']['status'] + '；語意未覆核、充分性未判定')
    if result.get('plan'):
        lines.extend('問題面向候選：' + n['label'] + ' [' + n['status'] + ']'
                     for n in result['plan']['needs'])
    if not result['evidence']:
        lines.append('目前未取得可供判斷的來源證據：' + result['reason'])
    displays = result.get('section_display') or {}
    for i, window in enumerate(result['evidence'], 1):
        section = displays.get(window['chunk_id'], '未確認章節')
        lines.extend(['', f"[{i}] {window['document']} / {window['revision']} / §{section} / {window['page_or_anchor']}",
            f"chunk: {window['chunk_id']} · SHA-256: {window['content_sha256']}",
            f"Unicode [{window['start']},{window['end']}) · UTF-8 [{window['byte_start']},{window['byte_end']})",
            window['quote']])
        attachments = [a for a in (result.get('conditions') or {}).get('attachments', ())
                       if a['parent_evidence_id'] == window['evidence_id']]
        if attachments:
            lines.append('條件／例外候選（未覆核）：')
            lines.extend('  ' + ', '.join(a['roles']) + ': ' + a['span']['quote'] for a in attachments)
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='真實既有 Retriever 的 USB 規格證據查詢；不呼叫模型。')
    parser.add_argument('--question')
    parser.add_argument('--serve', action='store_true', help='明確啟動僅限127.0.0.1的只讀預覽')
    parser.add_argument('--port', type=int, default=8769)
    parser.add_argument('--public-host', help='對外網域（需 HTTPS 前端）；存取碼只從環境變數 EVIDENCE_ACCESS_CODE 讀取')
    parser.add_argument('--audit-log', help='查詢稽核 JSONL 路徑；只記錄長度與 SHA-256，不記錄問題原文')
    parser.add_argument('--scope', choices=tuple(SCOPES), default='usb20')
    parser.add_argument('--format', choices=('json', 'text'), default='text')
    args = parser.parse_args(argv)
    if args.serve:
        if args.question is not None:
            parser.error('--serve and --question are separate entry modes')
        from .web import serve, validate_public_settings
        access_code = os.environ.get('EVIDENCE_ACCESS_CODE')
        try:
            validate_public_settings(args.public_host, access_code)
        except ValueError as exc:
            parser.error(str(exc))
        try:
            serve(port=args.port, public_host=args.public_host, access_code=access_code, audit_log=args.audit_log)
        except (OSError, ValueError, RuntimeError, KeyError):
            print('Evidence-only local preview unavailable', file=sys.stderr)
            return 2
        return 0
    if args.question is None:
        parser.error('--question is required unless --serve is explicitly selected')
    try:
        result = EvidenceService().query(args.question, scope=args.scope)
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        # Do not expose private paths/tracebacks when source verification fails.
        print(json.dumps({'status': 'error', 'reason': 'input_or_source_verification_failed',
                          'exception_type': type(exc).__name__, 'answer': None}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == 'json' else format_text(result))
    return 0
