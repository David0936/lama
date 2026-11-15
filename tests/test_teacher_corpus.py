import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('teacher_corpus', Path(__file__).resolve().parents[1] / 'scripts/teacher_corpus.py')
corpus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus)


class CorpusTests(unittest.TestCase):
    def test_html_excludes_navigation_and_scripts(self):
        html = '<nav>wrong person</nav><div id="maintext"><p>Real <em>teaching</em><br/>next line</p><script>bad()</script></div><footer>wrong author</footer>'
        lines = corpus.paragraphs(html, 'maintext')
        self.assertEqual(lines, ['Real teaching', 'next line'])
        with self.assertRaises(ValueError):
            corpus.paragraphs('<html>Login required</html>', 'maintext')

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
