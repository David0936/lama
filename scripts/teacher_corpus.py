"""Local public-text retrieval with person isolation and verifiable citations."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'agents/teachers/sources.json'
CACHE = ROOT / '.teacher-corpus'
PEOPLE = ('mentso', 'jigme-phuntsok', 'sodargye', 'danzeng-gyatso')
EXCERPTS = ROOT / 'agents/teachers/reviewed-excerpts.json'


def norm(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', value)).casefold()


def quote_norm(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', value))


def digest(data):
    return hashlib.sha256(data).hexdigest()


class BodyText(HTMLParser):
    def __init__(self, element_id=None):
        super().__init__()
        self.element_id = element_id
        self.depth = 0
        self.suppressed = 0
        self.parts = []
        self.found = element_id is None

    def handle_starttag(self, tag, attrs):
        void = tag in ('br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'source')
        if self.depth:
            if not void:
                self.depth += 1
        elif self.element_id is None or dict(attrs).get('id') == self.element_id:
            self.depth = 1
            self.found = True
        if self.depth:
            if tag in ('script', 'style'):
                self.suppressed += 1
            if tag in ('p', 'div', 'h1', 'h2', 'h3', 'li', 'br'):
                self.parts.append('\n')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'source'):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.depth:
            if tag in ('script', 'style'):
                self.suppressed = max(0, self.suppressed - 1)
            if tag in ('p', 'div', 'h1', 'h2', 'h3', 'li'):
                self.parts.append('\n')
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.suppressed:
            self.parts.append(data)


def flight_body(raw):
    chunks = []
    for match in re.findall(r'self\.__next_f\.push\((.*?)\)</script>', raw, re.S):
        value = json.loads(match)
        if len(value) > 1 and isinstance(value[1], str):
            chunks.append(value[1])
    flight = ''.join(chunks)
    field = re.search(r'"bodyHtml":', flight)
    if not field:
        raise ValueError('Missing bodyHtml')
    value, _ = json.JSONDecoder().raw_decode(flight[field.end():])
    if value.startswith('$'):
        record = re.search(r'(?:^|\n)' + re.escape(value[1:]) + r':T([0-9a-f]+),', flight)
        if not record:
            raise ValueError('Missing body record')
        value = flight[record.end():].encode()[:int(record[1], 16)].decode()
    if not value.rstrip().endswith('>'):
        raise ValueError('Truncated body HTML')
    return value


def paragraphs(raw, element_id=None):
    parser = BodyText(element_id)
    parser.feed(raw)
    if not parser.found:
        raise ValueError('Missing expected element: ' + str(element_id))
    return [x.strip() for x in ''.join(parser.parts).splitlines() if x.strip()]


def prepare(source, refresh=False, mentso_root=None):
    folder = CACHE / source['id']
    if (folder / 'record.json').exists() and not refresh:
        record = json.loads((folder / 'record.json').read_text())
        raw_path = folder / 'source.bin'
        texts = folder / 'segments.json'
        if digest(raw_path.read_bytes()) != record['sha256'] or digest(texts.read_bytes()) != record['text_sha256']:
            raise ValueError('Cached checksum mismatch; review before refresh')
        return record
    acquisition = 'public_url'
    if mentso_root and source.get('local_mirror'):
        raw = (Path(mentso_root) / source['local_mirror']).read_bytes()
        final_url = source['url']
        acquisition = 'local_mirror_unverified_against_live_source'
        text_blocks = raw.decode('utf-8').splitlines()
        units = [(None, x.strip()) for x in text_blocks if x.strip()]
    else:
        with urllib.request.urlopen(source['url'], timeout=40) as response:
            raw = response.read()
            final_url = response.geturl()
        if source['format'] == 'pdf':
            if not raw.startswith(b'%PDF'):
                raise ValueError('Expected PDF, received another content type')
            from io import BytesIO
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(raw))
            start, end = source['pdf_pages']
            if not 1 <= start <= end <= len(reader.pages):
                raise ValueError('PDF page range out of bounds')
            units = [(i + 1, (reader.pages[i].extract_text() or '').strip()) for i in range(start - 1, end)]
        else:
            html = raw.decode('utf-8')
            if source['format'] == 'flight':
                html = flight_body(html)
            units = [(None, x) for x in paragraphs(html, source.get('element_id'))]
    if sum(len(t) for _, t in units) < 100:
        raise ValueError('Body too short; review extraction')
    segments = []
    for number, (page, text) in enumerate(units, 1):
        if not text:
            continue
        segments.append({'segment': number, 'pdf_page': page, 'text': text})
    encoded = (json.dumps(segments, ensure_ascii=False, indent=2) + '\n').encode()
    record = dict(source, fetched_at=datetime.now(timezone.utc).isoformat(), final_url=final_url,
                  acquisition=acquisition, sha256=digest(raw), text_sha256=digest(encoded),
                  segments=len(segments), characters=sum(len(x['text']) for x in segments))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'source.bin').write_bytes(raw)
    (folder / 'segments.json').write_bytes(encoded)
    (folder / 'record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return record


def load_segments(person, sources):
    result = []
    if EXCERPTS.exists():
        for item in json.loads(EXCERPTS.read_text(encoding='utf-8')):
            if item['person'] == person:
                result.append(dict(item, source_id=item['id'], segment=1, pdf_page=None,
                                   text_sha256=digest(item['text'].encode('utf-8')),
                                   quote_allowed=True, text_role='reviewed_excerpt',
                                   corpus_kind='reviewed_excerpt_not_fulltext'))
    for source in sources:
        if source['person'] != person or not source.get('enabled', True):
            continue
        folder = CACHE / source['id']
        if not (folder / 'record.json').exists():
            continue
        record = json.loads((folder / 'record.json').read_text())
        if record['url'] != source['url']:
            raise ValueError('Source URL changed; review and refresh cache: ' + source['id'])
        data = (folder / 'segments.json').read_bytes()
        if digest(data) != record['text_sha256']:
            raise ValueError('Cached text checksum mismatch: ' + source['id'])
        segments = json.loads(data)
        start, end = 0, len(segments)
        for field in ('quote_start', 'quote_end'):
            if source.get(field):
                found = next((i for i, s in enumerate(segments) if re.search(source[field], s['text'])), None)
                if found is None:
                    raise ValueError('Missing expected quote boundary: ' + source['id'] + ':' + field)
                if field == 'quote_start':
                    start = found
                else:
                    end = found
        if end <= start:
            raise ValueError('Invalid quote boundaries: ' + source['id'])
        for index, segment in enumerate(segments):
            result.append(dict(source_id=source['id'], person=person, title=source['title'],
                               author=source['author'], translator=source.get('translator'),
                               role=source['role'], language=source['language'], url=source['url'],
                               fetched_at=record['fetched_at'], acquisition=record['acquisition'],
                               final_url=record['final_url'], source_sha256=record['sha256'],
                               quote_allowed=start <= index < end,
                               text_role='author_text' if start <= index < end else 'paratext_not_author_quote',
                               text_sha256=record['text_sha256'], corpus_kind='local_text', **segment))
    return result


def search(rows, terms, limit=5):
    ranked = []
    for row in rows:
        score = sum(norm(row['text']).count(norm(t)) for t in terms if norm(t))
        if score:
            ranked.append(dict(row, hits=score))
    return sorted(ranked, key=lambda x: (-x['hits'], x['source_id'], x['segment']))[:limit]


def emit(value):
    print(json.dumps(value, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--person', choices=PEOPLE)
    prep.add_argument('--refresh', action='store_true')
    prep.add_argument('--mentso-root', type=Path)
    sub.add_parser('status')
    for command in ('search', 'verify', 'export', 'read'):
        child = sub.add_parser(command)
        child.add_argument('--person', choices=PEOPLE, required=True)
        if command == 'search':
            child.add_argument('terms', nargs='+')
            child.add_argument('--limit', type=int, default=5)
        if command == 'verify':
            child.add_argument('--quote', required=True)
        if command == 'read':
            child.add_argument('--source', required=True)
            child.add_argument('--segment', type=int, required=True)
            child.add_argument('--context', type=int, default=2)
    args = parser.parse_args()
    sources = json.loads(CONFIG.read_text(encoding='utf-8'))
    if args.command == 'prepare':
        outcomes = []
        for source in sources:
            if args.person and source['person'] != args.person:
                continue
            if not source.get('enabled', True):
                outcomes.append({'id': source['id'], 'status': 'disabled', 'reason': source['disabled_reason']})
                continue
            try:
                record = prepare(source, args.refresh, args.mentso_root)
                outcomes.append({'id': source['id'], 'status': 'ready', 'record': record})
            except Exception as exc:
                outcomes.append({'id': source['id'], 'status': 'error', 'error': str(exc)})
            emit({k: v for k, v in outcomes[-1].items() if k != 'record'})
        CACHE.mkdir(exist_ok=True)
        (CACHE / 'manifest.json').write_text(json.dumps(outcomes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return int(any(x['status'] == 'error' for x in outcomes))
    if args.command == 'status':
        for person in PEOPLE:
            rows = load_segments(person, sources)
            emit({'person': person, 'available_segments': len(rows),
                  'local_text_segments': sum(r['corpus_kind'] == 'local_text' for r in rows),
                  'reviewed_excerpts': sum(r['corpus_kind'] == 'reviewed_excerpt_not_fulltext' for r in rows),
                  'sources': [{'id': s['id'], 'enabled': s.get('enabled', True),
                               'cached': (CACHE / s['id'] / 'record.json').exists(),
                               'reason': s.get('disabled_reason')} for s in sources if s['person'] == person]})
        return 0
    rows = load_segments(args.person, sources)
    if args.command == 'read':
        if args.context < 0 or args.context > 20:
            parser.error('--context must be between 0 and 20')
        matches = [r for r in rows if r['source_id'] == args.source and abs(r['segment'] - args.segment) <= args.context]
        emit({'person': args.person, 'matches': matches})
        return 0 if any(r['segment'] == args.segment for r in matches) else 2
    if args.command == 'export':
        destination = CACHE / ('export-' + args.person + '.jsonl')
        CACHE.mkdir(exist_ok=True)
        destination.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        emit({'file': str(destination), 'segments': len(rows)})
        return 0 if rows else 2
    if args.command == 'verify':
        matches = [r for r in rows if r['quote_allowed'] and quote_norm(args.quote) and quote_norm(args.quote) in quote_norm(r['text'])]
        emit({'verified': bool(matches), 'scope': 'registered_text_match_only_not_author_authentication',
              'normalization': 'NFC and whitespace removal only', 'matches': matches})
        return 0 if matches else 2
    if args.limit < 1:
        parser.error('--limit must be positive')
    matches = search(rows, args.terms, args.limit)
    emit({'person': args.person, 'matches': matches, 'status': 'found' if matches else 'no_match',
          'available_segments': len(rows)})
    return 0 if matches else 2


if __name__ == '__main__':
    sys.exit(main())
