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
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'agents/teachers/sources.json'
CACHE = ROOT / '.teacher-corpus'
PEOPLE = ('mentso', 'jigme-phuntsok', 'sodargye', 'danzeng-gyatso')
EXCERPTS = ROOT / 'agents/teachers/reviewed-excerpts.json'
TOPICS = ROOT / 'agents/teachers/topics.json'
READING_NOTES = ROOT / 'agents/teachers/reading-notes.json'
try:
    from opencc import OpenCC
    SCRIPT_CONVERTER = OpenCC('t2s')
except ImportError:
    SCRIPT_CONVERTER = None


def norm(value):
    text = re.sub(r'\s+', '', unicodedata.normalize('NFC', value)).replace('༌', '་').casefold()
    return SCRIPT_CONVERTER.convert(text) if SCRIPT_CONVERTER else text


def quote_norm(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', value))


def digest(data):
    return hashlib.sha256(data).hexdigest()


class BodyText(HTMLParser):
    def __init__(self, element_id=None, element_class=None):
        super().__init__()
        self.element_id = element_id
        self.element_class = element_class
        self.root_tag = None
        self.depth = 0
        self.suppressed = 0
        self.parts = []
        self.found = element_id is None and element_class is None
        self.whole_document = self.found
        if self.whole_document:
            self.depth = 1

    def handle_starttag(self, tag, attrs):
        void = tag in ('br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'source')
        if self.depth:
            if tag == self.root_tag and not void:
                self.depth += 1
        elif ((self.element_id is not None and dict(attrs).get('id') == self.element_id)
              or (self.element_class is not None and self.element_class in dict(attrs).get('class', '').split())):
            self.depth = 1
            self.root_tag = tag
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
            if not self.whole_document and tag == self.root_tag:
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


def paragraphs(raw, element_id=None, element_class=None):
    parser = BodyText(element_id, element_class)
    parser.feed(raw)
    if not parser.found:
        raise ValueError('Missing expected element: ' + str(element_id))
    return [x.strip() for x in ''.join(parser.parts).splitlines() if x.strip()]


def qa_segments(pages):
    """Preserve each question with its answer, including page continuations."""
    rows, current, mode = [], None, None

    def finish():
        if current is None:
            return
        question = '\n'.join(current['question']).strip()
        answer = '\n'.join(current['answer']).strip()
        rows.append({'segment': len(rows) + 1, 'pdf_page': current['pages'][0],
                     'pdf_pages': current['pages'], 'question': question, 'answer': answer,
                     'text': '问：' + question + '\n堪布：' + answer,
                     'quote_text': answer, 'speaker': '索达吉堪布' if answer else None,
                     'quote_allowed': bool(answer), 'text_role': 'question_and_speaker_answer',
                     'parse_status': 'parsed' if answer else 'answer_not_identified',
                     'attribution_note': '问答记录；回答可能引用他人，不据此认作原创格言。'})

    for page, text in pages:
        for line in text.splitlines():
            line = line.strip()
            if not line or re.fullmatch(r'\d{1,3}', line):
                continue
            question = re.match(r'^(?:⊙\s*)?问\s*[：:]\s*(.*)', line)
            answer = re.match(r'^堪\s*布\s*[：:]\s*(.*)', line)
            if question:
                finish()
                current = {'question': [question[1]], 'answer': [], 'pages': [page]}
                mode = 'question'
            elif answer and current is not None:
                mode = 'answer'
                current['answer'].append(answer[1])
            elif current is not None:
                current[mode].append(line)
            if current is not None and page not in current['pages']:
                current['pages'].append(page)
    finish()
    if not rows or not any(r['answer'] for r in rows):
        raise ValueError('No question/answer pairs identified; review PDF extraction')
    for index, row in enumerate(rows):
        row['previous_segment'] = rows[index - 1]['segment'] if index else None
        row['next_segment'] = rows[index + 1]['segment'] if index + 1 < len(rows) else None
        row['read_adjacent_turns'] = True
    return rows


def speaker_segments(units, target_speaker, speakers):
    """Classify explicit speaker paragraphs; leave headings/narration unquoted."""
    if target_speaker not in speakers:
        raise ValueError('Target speaker missing from speaker list')
    pattern = re.compile(r'^(' + '|'.join(re.escape(s) for s in sorted(speakers, key=len, reverse=True)) + r')\s*[：:]\s*(.*)', re.S)
    rows = []
    for index, (page, text) in enumerate(units, 1):
        match = pattern.match(text)
        speaker = match[1] if match else None
        body = match[2] if match else ''
        allowed = speaker == target_speaker and bool(body.strip())
        rows.append({'segment':index, 'pdf_page':page, 'text':text, 'speaker':speaker,
                     'quote_text':body, 'quote_allowed':allowed,
                     'text_role':'target_speaker_statement' if allowed else ('other_speaker_statement' if match else 'editorial_not_speech'),
                     'previous_segment':index-1 if index>1 else None,
                     'next_segment':index+1 if index<len(units) else None,
                     'attribution_note':'按公开实录的显式讲者标签归属，未与音视频对听；段内引语不自动认作原创。'})
    if not any(r['quote_allowed'] for r in rows):
        raise ValueError('No explicit target-speaker paragraphs found')
    return rows


def quote_flags(source, segments):
    ranges = source.get('quote_ranges') or [{'start':source.get('quote_start'),'end':source.get('quote_end')}]
    flags = [False] * len(segments)
    for interval in ranges:
        start, end = 0, len(segments)
        for field in ('start','end'):
            if interval.get(field):
                found = next((i for i,s in enumerate(segments) if i>=start and re.search(interval[field],s['text'])),None)
                if found is None:
                    raise ValueError('Missing expected quote boundary: ' + source['id'] + ':' + field)
                if field=='start':start=found
                else:end=found
        if end<=start:
            raise ValueError('Invalid quote boundaries: ' + source['id'])
        for i in range(start,end):flags[i]=True
    return flags


def prepare(source, refresh=False, mentso_root=None, reextract=False):
    folder = CACHE / source['id']
    if (folder / 'record.json').exists() and not refresh and not reextract:
        record = json.loads((folder / 'record.json').read_text())
        raw_path = folder / 'source.bin'
        texts = folder / 'segments.json'
        if digest(raw_path.read_bytes()) != record['sha256'] or digest(texts.read_bytes()) != record['text_sha256']:
            raise ValueError('Cached checksum mismatch; review before refresh')
        return record
    acquisition = 'public_url'
    fetched_at = datetime.now(timezone.utc).isoformat()
    if mentso_root and source.get('local_mirror'):
        raw = (Path(mentso_root) / source['local_mirror']).read_bytes()
        final_url = source['url']
        acquisition = 'local_mirror_unverified_against_live_source'
        text_blocks = raw.decode('utf-8').splitlines()
        units = [(None, x.strip()) for x in text_blocks if x.strip()]
    else:
        if reextract:
            prior = json.loads((folder / 'record.json').read_text())
            raw = (folder / 'source.bin').read_bytes()
            if digest(raw) != prior['sha256'] or source['url'] != prior['url']:
                raise ValueError('Cannot reextract changed original or changed URL')
            fetched_at, acquisition = prior['fetched_at'], prior['acquisition']
            final_url = prior['final_url']
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
            units = [(None, x) for x in paragraphs(html, source.get('element_id'), source.get('element_class'))]
    if sum(len(t) for _, t in units) < 100:
        raise ValueError('Body too short; review extraction')
    segments = []
    if source.get('segmentation') == 'qa':
        segments = qa_segments(units)
    elif source.get('segmentation') == 'speaker_turns':
        segments = speaker_segments(units,source['target_speaker'],source['speakers'])
    else:
        for number, (page, text) in enumerate(units, 1):
            if not text:
                continue
            segments.append({'segment': number, 'pdf_page': page, 'text': text})
    encoded = (json.dumps(segments, ensure_ascii=False, indent=2) + '\n').encode()
    record = dict(source, fetched_at=fetched_at, extracted_at=datetime.now(timezone.utc).isoformat(), final_url=final_url,
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
        flags = quote_flags(source,segments)
        for index, segment in enumerate(segments):
            row = dict(source_id=source['id'], person=person, title=source['title'],
                               author=source['author'], translator=source.get('translator'),
                               role=source['role'], language=source['language'], url=source['url'],
                               version_note=source.get('version_note'),
                               fetched_at=record['fetched_at'], acquisition=record['acquisition'],
                               final_url=record['final_url'], source_sha256=record['sha256'],
                               quote_allowed=flags[index],
                               text_role='author_text' if flags[index] else 'paratext_not_author_quote',
                               text_sha256=record['text_sha256'], corpus_kind='local_text')
            row.update(segment)
            figures = source.get('nested_attributions',{}).get(str(row['segment']))
            if figures:
                row['nested_attributions'] = figures
                row['quotation_warning'] = '本段含他人经历或引语，须按段内姓名归属，不能将每句认作本文作者亲历或原创。'
                row['quote_allowed'] = False
                row['text_role'] = 'nested_attribution_not_author_quote'
            result.append(row)
    for row in result:
        row['citation_markdown'] = citation(row)
    return result


def citation(row):
    """Format an existing source locator; never invent a page or a URL."""
    parsed = urlsplit(row['url'])
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('Citation requires a registered HTTP(S) source URL')
    pages = row.get('pdf_pages') or ([row['pdf_page']] if row.get('pdf_page') else [])
    title = row['title'].replace('[', '［').replace(']', '］').replace('\n', ' ')
    if pages:
        if any(not isinstance(p, int) or p < 1 for p in pages):
            raise ValueError('Invalid PDF file page')
        location = '文件第' + str(pages[0]) + ('–' + str(pages[-1]) if pages[-1] != pages[0] else '') + '页'
        parsed = parsed._replace(fragment='page=' + str(pages[0]))
    else:
        location = row.get('locator') or '当前提取段' + str(row['segment'])
    return '[' + title + '，' + location + '](' + urlunsplit(parsed) + ')'


def related_notes(person, matches, terms=()):
    if not READING_NOTES.exists():
        return []
    notes = json.loads(READING_NOTES.read_text(encoding='utf-8'))
    return [n for n in notes if n['person'] == person and (
        any(norm(trigger) in norm(term) for trigger in n['triggers'] for term in terms)
        or any(r['source_id'] == n['source_id'] and r['segment'] in n['segments'] for r in matches))]


def search(rows, terms, limit=5):
    ranked = []
    for row in rows:
        score = sum(norm(row['text']).count(norm(t)) for t in terms if norm(t))
        if score:
            ranked.append(dict(row, hits=score))
    return sorted(ranked, key=lambda x: (-x['hits'], x['source_id'], x['segment']))[:limit]


def verify_quote(rows, quote, source_id=None, segment=None):
    return [r for r in rows if r['quote_allowed'] and quote_norm(quote)
            and (source_id is None or r['source_id'] == source_id)
            and (segment is None or r['segment'] == segment)
            and quote_norm(quote) in quote_norm(r.get('quote_text', r['text']))]


def excluded_quote_matches(rows, quote, accepted, source_id=None, segment=None):
    accepted_ids = {(r['source_id'],r['segment']) for r in accepted}
    excluded = []
    for row in rows:
        if (source_id is not None and row['source_id']!=source_id) or (segment is not None and row['segment']!=segment):
            continue
        if (row['source_id'],row['segment']) in accepted_ids or not quote_norm(quote):
            continue
        if quote_norm(quote) in quote_norm(row['text']):
            excluded.append({'source_id':row['source_id'],'segment':row['segment'],
                             'reason':'not_author_quote' if not row['quote_allowed'] else 'outside_author_span',
                             'text_role':row.get('text_role'),'speaker':row.get('speaker'),
                             'nested_attributions':row.get('nested_attributions'),
                             'citation_markdown':row.get('citation_markdown')})
    return excluded


def topic_routes(person, sources, topic_id=None, limit=3):
    topics = json.loads(TOPICS.read_text(encoding='utf-8'))
    selected = [t for t in topics if t['person'] == person and (topic_id is None or t['id'] == topic_id)]
    rows = load_segments(person, sources)
    result = []
    for topic in selected:
        eligible = [r for r in rows if r['source_id'] in topic['source_ids'] and r['quote_allowed']]
        matches = search(eligible, topic['keywords'], limit)
        result.append(dict(topic, matches=matches, reading_notes=related_notes(person,matches,topic['keywords']),
                           status='found' if matches else 'no_match'))
    return result


def emit(value):
    print(json.dumps(value, ensure_ascii=False))


def save_outcomes(outcomes):
    CACHE.mkdir(exist_ok=True)
    manifest = CACHE / 'manifest.json'
    previous = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
    combined = {r['id']: r for r in previous}
    stamp = datetime.now(timezone.utc).isoformat()
    with (CACHE / 'fetch-history.jsonl').open('a', encoding='utf-8') as history:
        for item in outcomes:
            attempt = dict(item, attempted_at=stamp)
            combined[item['id']] = attempt
            history.write(json.dumps(attempt, ensure_ascii=False) + '\n')
    manifest.write_text(json.dumps(list(combined.values()), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--person', choices=PEOPLE)
    prep.add_argument('--source', action='append', help='Prepare only named source IDs; repeatable')
    prep.add_argument('--refresh', action='store_true')
    prep.add_argument('--reextract', action='store_true', help='Reparse verified cached originals without network')
    prep.add_argument('--mentso-root', type=Path)
    sub.add_parser('status')
    for command in ('search', 'verify', 'export', 'read', 'topics', 'cite'):
        child = sub.add_parser(command)
        child.add_argument('--person', choices=PEOPLE, required=True)
        if command == 'search':
            child.add_argument('terms', nargs='+')
            child.add_argument('--limit', type=int, default=5)
        if command == 'verify':
            child.add_argument('--quote', required=True)
            child.add_argument('--source')
            child.add_argument('--segment', type=int)
        if command == 'read':
            child.add_argument('--source', required=True)
            child.add_argument('--segment', type=int, required=True)
            child.add_argument('--context', type=int, default=2)
        if command == 'cite':
            child.add_argument('--source', required=True)
            child.add_argument('--segment', type=int, required=True)
        if command == 'topics':
            child.add_argument('--topic')
            child.add_argument('--limit', type=int, default=3)
    args = parser.parse_args()
    if args.command == 'prepare' and args.refresh and args.reextract:
        parser.error('--refresh and --reextract are mutually exclusive')
    sources = json.loads(CONFIG.read_text(encoding='utf-8'))
    if args.command == 'prepare':
        outcomes = []
        if args.source and set(args.source) - {s['id'] for s in sources}:
            parser.error('Unknown source ID')
        for source in sources:
            if args.person and source['person'] != args.person:
                continue
            if args.source and source['id'] not in args.source:
                continue
            if not source.get('enabled', True):
                outcomes.append({'id': source['id'], 'status': 'disabled', 'reason': source['disabled_reason']})
                emit(outcomes[-1])
                continue
            try:
                record = prepare(source, args.refresh, args.mentso_root, args.reextract)
                outcomes.append({'id': source['id'], 'status': 'ready', 'record': record})
            except Exception as exc:
                outcomes.append({'id': source['id'], 'status': 'error', 'error': str(exc)})
            emit({k: v for k, v in outcomes[-1].items() if k != 'record'})
        save_outcomes(outcomes)
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
    if args.command == 'topics':
        if args.limit < 1:
            parser.error('--limit must be positive')
        result = topic_routes(args.person, sources, args.topic, args.limit)
        emit({'person': args.person, 'topics': result})
        return 0 if result and all(t['matches'] for t in result) else 2
    rows = load_segments(args.person, sources)
    if args.command == 'cite':
        matches = [r for r in rows if r['source_id'] == args.source and r['segment'] == args.segment]
        emit({'citation_markdown': matches[0]['citation_markdown'] if matches else None,
              'source_id': args.source, 'segment': args.segment,
              'quote_allowed': matches[0]['quote_allowed'] if matches else False,
              'scope': 'source_locator_not_quote_verification'})
        return 0 if matches else 2
    if args.command == 'read':
        if args.context < 0 or args.context > 20:
            parser.error('--context must be between 0 and 20')
        matches = [r for r in rows if r['source_id'] == args.source and abs(r['segment'] - args.segment) <= args.context]
        emit({'person': args.person, 'matches': matches, 'reading_notes': related_notes(args.person,matches)})
        return 0 if any(r['segment'] == args.segment for r in matches) else 2
    if args.command == 'export':
        destination = CACHE / ('export-' + args.person + '.jsonl')
        CACHE.mkdir(exist_ok=True)
        destination.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        emit({'file': str(destination), 'segments': len(rows)})
        return 0 if rows else 2
    if args.command == 'verify':
        if args.segment is not None and not args.source:
            parser.error('--segment requires --source for verification')
        matches = verify_quote(rows, args.quote, args.source, args.segment)
        excluded = excluded_quote_matches(rows,args.quote,matches,args.source,args.segment)
        emit({'verified': bool(matches), 'scope': 'registered_text_match_only_not_author_authentication',
              'status':'verified' if matches else ('excluded_context_match' if excluded else 'no_registered_match'),
              'excluded_matches':excluded,
              'requested_source': args.source, 'requested_segment': args.segment,
              'normalization': 'NFC and whitespace removal only', 'matches': matches,
              'reading_notes': related_notes(args.person,matches,[args.quote])})
        return 0 if matches else 2
    if args.limit < 1:
        parser.error('--limit must be positive')
    matches = search(rows, args.terms, args.limit)
    emit({'person': args.person, 'matches': matches, 'status': 'found' if matches else 'no_match',
          'reading_notes': related_notes(args.person,matches,args.terms),
          'script_folding': 'OpenCC t2s' if SCRIPT_CONVERTER else 'not_installed',
          'available_segments': len(rows)})
    return 0 if matches else 2


if __name__ == '__main__':
    sys.exit(main())
