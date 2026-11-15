import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('teacher_corpus', Path(__file__).resolve().parents[1] / 'scripts/teacher_corpus.py')
corpus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus)


class CorpusTests(unittest.TestCase):
    def test_reading_notes_are_not_author_quotes_or_other_people(self):
        notes=corpus.related_notes('mentso',[],['人规法'])
        self.assertEqual(len(notes),1)
        self.assertEqual(notes[0]['kind'],'editorial_reading_note_not_teacher_quote')
        self.assertEqual(corpus.related_notes('sodargye',[],['人规法']),[])
        self.assertEqual(corpus.related_notes('mentso',[{'source_id':'MT-HOUSEHOLDERS','segment':29}])[0]['id'],'MT-REN-GUI')

    def test_citations_use_file_pages_and_registered_url(self):
        row = dict(title='书名', url='https://example.org/book.pdf?version=2#old', pdf_pages=[6,7], segment=2)
        self.assertEqual(corpus.citation(row), '[书名，文件第6–7页](https://example.org/book.pdf?version=2#page=6)')
        html = dict(title='文[题]',url='https://example.org/article',segment=19)
        self.assertEqual(corpus.citation(html), '[文［题］，当前提取段19](https://example.org/article)')
        with self.assertRaises(ValueError):
            corpus.citation(dict(html,url='javascript:bad'))

    def test_html_excludes_navigation_and_scripts(self):
        html = '<nav>wrong person</nav><div id="maintext"><p>Real <em>teaching</em><br/>next line</p><script>bad()</script></div><footer>wrong author</footer>'
        lines = corpus.paragraphs(html, 'maintext')
        self.assertEqual(lines, ['Real teaching', 'next line'])
        with self.assertRaises(ValueError):
            corpus.paragraphs('<html>Login required</html>', 'maintext')
        self.assertEqual(corpus.paragraphs('<div class="zwzw"><p><p>正文</p></div><footer>推荐</footer>', element_class='zwzw'), ['正文'])

    def test_qa_cross_page_and_speaker_whitespace(self):
        rows = corpus.qa_segments([(5, '001\n⊙ 问：怎样\n学习？\n堪 布 ：先阅读。'),
                                  (6, '002\n然后思考。\n⊙ 问：后续问题\n堪布：后续回答。')])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['pdf_pages'], [5, 6])
        self.assertEqual(rows[0]['answer'], '先阅读。\n然后思考。')
        self.assertNotIn('怎样', rows[0]['quote_text'])
        self.assertEqual(rows[0]['next_segment'], 2)
        self.assertEqual(rows[1]['previous_segment'], 1)
        incomplete = corpus.qa_segments([(1, '问：没有直接答复\n问：下一问\n堪布：下一答')])
        self.assertFalse(incomplete[0]['quote_allowed'])
        self.assertEqual(incomplete[0]['parse_status'], 'answer_not_identified')

    def test_search_folds_script_without_altering_quotes(self):
        if corpus.SCRIPT_CONVERTER is None:
            self.skipTest('Install requirements-teachers.txt for OpenCC checks')
        rows = [{'source_id':'test', 'segment':1, 'text':'傾聽苦難經歷。'}]
        found = corpus.search(rows, ['倾听'])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['text'], '傾聽苦難經歷。')
        self.assertNotEqual(corpus.quote_norm('傾聽'), corpus.quote_norm('倾听'))

    def test_attempt_history_preserves_unselected_sources(self):
        before = corpus.CACHE
        with tempfile.TemporaryDirectory() as temporary:
            corpus.CACHE = Path(temporary)
            try:
                corpus.save_outcomes([{'id':'A','status':'ready'}])
                corpus.save_outcomes([{'id':'B','status':'error','error':'403'}])
                latest = json.loads((corpus.CACHE / 'manifest.json').read_text())
                self.assertEqual({r['id'] for r in latest}, {'A','B'})
                corpus.save_outcomes([{'id':'B','status':'ready'}])
                history = [json.loads(line) for line in (corpus.CACHE / 'fetch-history.jsonl').read_text().splitlines()]
                self.assertEqual([r['status'] for r in history], ['ready','error','ready'])
            finally:
                corpus.CACHE = before

    def test_scoped_verify_cannot_substitute_another_segment(self):
        rows = [dict(source_id='book', segment=1, text='相同标题', quote_allowed=False),
                dict(source_id='book', segment=2, text='相同标题', quote_allowed=True),
                dict(source_id='qa', segment=1, text='问：提问内容\n答：本人回答', quote_text='本人回答', quote_allowed=True)]
        self.assertTrue(corpus.verify_quote(rows, '相同标题'))
        self.assertFalse(corpus.verify_quote(rows, '相同标题', 'book', 1))
        self.assertTrue(corpus.verify_quote(rows, '相同标题', 'book', 2))
        self.assertFalse(corpus.verify_quote(rows, '提问内容', 'qa', 1))

    def test_person_isolation_provenance_and_tamper(self):
        before, before_excerpts = corpus.CACHE, corpus.EXCERPTS
        with tempfile.TemporaryDirectory() as temporary:
            corpus.CACHE = Path(temporary) / 'cache'
            corpus.EXCERPTS = Path(temporary) / 'missing-excerpts.json'
            mirror = Path(temporary) / 'mirror'
            mirror.mkdir()
            (mirror / 'text.txt').write_text('量入为出当知足，自心常乐乃首富。\n' * 15)
            base = dict(title='Test', author='门措', translator='索达吉', role='authored_teaching', language='zh', url='https://example.org', format='flight', local_mirror='text.txt')
            mt = dict(base, id='MT', person='mentso')
            other = dict(base, id='DG', person='danzeng-gyatso')
            try:
                corpus.prepare(mt, mentso_root=mirror)
                corpus.prepare(other, mentso_root=mirror)
                rows = corpus.load_segments('mentso', [mt, other])
                self.assertTrue(rows)
                self.assertTrue(all(row['source_id'] == 'MT' for row in rows))
                self.assertEqual(rows[0]['translator'], '索达吉')
                self.assertTrue(corpus.search(rows, ['量入为出']))
                self.assertFalse(corpus.search(rows, ['每天和AI聊天就能开悟']))
                self.assertEqual(corpus.load_segments('sodargye', [mt, other]), [])
                (corpus.CACHE / 'MT' / 'segments.json').write_text('[]')
                with self.assertRaises(ValueError):
                    corpus.load_segments('mentso', [mt, other])
            finally:
                corpus.CACHE = before
                corpus.EXCERPTS = before_excerpts

    def test_tibetan_unicode(self):
        self.assertEqual(corpus.norm('é \n བོད་'), corpus.norm('e\u0301བོད་'))
        self.assertNotEqual(corpus.quote_norm('Teaching'), corpus.quote_norm('teaching'))

    def test_registry_roles_and_unique_ids(self):
        sources = json.loads(corpus.CONFIG.read_text())
        self.assertEqual(len(sources), len({s['id'] for s in sources}))
        self.assertEqual({s['person'] for s in sources}, set(corpus.PEOPLE))
        self.assertFalse(next(s for s in sources if s['id'] == 'SD-MIND-TRAINING')['enabled'])
        self.assertEqual(next(s for s in sources if s['id'] == 'MT-HOUSEHOLDERS')['author'], '门措空行母')

    def test_quote_boundaries_and_changed_source_url(self):
        before, before_excerpts = corpus.CACHE, corpus.EXCERPTS
        with tempfile.TemporaryDirectory() as temporary:
            corpus.CACHE = Path(temporary) / 'cache'
            corpus.EXCERPTS = Path(temporary) / 'missing.json'
            mirror = Path(temporary) / 'mirror'
            mirror.mkdir()
            (mirror / 'body.txt').write_text('标题与译者\n开始正文' + '学习与思考。' * 30 + '\n题记：编辑写作\n')
            source = dict(id='TEST', person='mentso', title='Example', author='作者', language='zh',
                          role='authored_teaching', url='https://example.org/original', format='flight',
                          local_mirror='body.txt', quote_start='^开始正文', quote_end='^题记')
            try:
                corpus.prepare(source, mentso_root=mirror)
                rows = corpus.load_segments('mentso', [source])
                self.assertEqual([r['quote_allowed'] for r in rows], [False, True, False])
                self.assertEqual(rows[2]['text_role'], 'paratext_not_author_quote')
                with self.assertRaises(ValueError):
                    corpus.load_segments('mentso', [dict(source, url='https://example.org/changed')])
            finally:
                corpus.CACHE, corpus.EXCERPTS = before, before_excerpts


if __name__ == '__main__':
    unittest.main()
