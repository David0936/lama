import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import teacher_corpus as corpus
import package_teacher_skills as packages


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.saved = (corpus.CACHE, corpus.CONFIG, corpus.EXCERPTS, corpus.TOPICS, packages.DATA)
        corpus.CACHE = self.base / 'cache'
        data = self.base / 'data'
        data.mkdir()
        corpus.CONFIG = data / 'sources.json'
        corpus.EXCERPTS = data / 'reviewed-excerpts.json'
        corpus.TOPICS = data / 'topics.json'
        packages.DATA = data
        profiles = json.loads((ROOT / 'agents/teachers/profiles.json').read_text())
        packages.write_json(data / 'profiles.json', profiles)
        packages.write_json(data / 'person-facts.json', [
            {'id': 'fixture-bio', 'person': 'sodargye', 'statement': '测试传记记录',
             'checked_at': '2026-11-15', 'source_title': 'Fixture biography',
             'url': 'https://example.org/bio', 'locator': 'Biography',
             'nature': 'fixture_metadata', 'limits': '仅为测试，不是原话。'}])
        packages.write_json(data / 'quote-attributions.json', [
            {'id': 'fixture-attribution', 'relevant_people': ['mentso', 'sodargye'],
             'scope': 'cross_person_attribution_only', 'author': 'mentso',
             'translator': 'sodargye', 'quote': '跨人物署名测试'}])
        sources = []
        topics = []
        mirror = self.base / 'mirror'
        mirror.mkdir()
        for person in corpus.PEOPLE:
            text = ('只属于' + person + '的测试正文。') * 20
            (mirror / (person + '.txt')).write_text(text)
            source = dict(id=person + '-source', person=person, title='Fixture', author=person,
                          translator=None, role='authored_teaching', language='zh',
                          url='https://example.org/' + person, format='flight', local_mirror=person + '.txt')
            sources.append(source)
            topics.append(dict(id='fixture', person=person, title='Fixture', keywords=['测试正文'], source_ids=[source['id']], use='fixture'))
            corpus.prepare(source, mentso_root=mirror)
        packages.write_json(corpus.CONFIG, sources)
        packages.write_json(corpus.EXCERPTS, [])
        packages.write_json(corpus.TOPICS, topics)
        packages.write_json(data / 'quote-cards.json', [
            {'id': 'fixture-card', 'person': 'sodargye', 'topic': '学习',
             'source_id': 'sodargye-source', 'segment': 1, 'quote': '测试正文',
             'context_segments': [1], 'context_note': '测试上下文',
             'application_boundary': '测试编者说明'}])

    def tearDown(self):
        corpus.CACHE, corpus.CONFIG, corpus.EXCERPTS, corpus.TOPICS, packages.DATA = self.saved
        self.temporary.cleanup()

    def test_standalone_package_isolation_and_archive(self):
        out = self.base / 'release'
        result = packages.build_release(out, ['mentso'], include_corpus=True)
        self.assertEqual(len(result), 1)
        folder = out / result[0]['folder']
        manifest = packages.verify_package(folder)
        self.assertEqual(manifest['cached_sources'], ['mentso-source'])
        sources = json.loads((folder / 'agents/teachers/sources.json').read_text())
        self.assertEqual({s['person'] for s in sources}, {'mentso'})
        self.assertFalse((folder / '.teacher-corpus/sodargye-source').exists())
        process = subprocess.run([sys.executable, str(folder / 'scripts/teacher_corpus.py'), 'search', '--person', 'mentso', '测试正文'], cwd=self.base, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['matches'][0]['source_id'], 'mentso-source')
        with zipfile.ZipFile(out / result[0]['archive']) as archive:
            self.assertIsNone(archive.testzip())
            self.assertTrue(any(n.endswith('/SKILL.md') for n in archive.namelist()))
        (folder / 'scripts/teacher_corpus.py').write_text('tampered')
        with self.assertRaises(ValueError):
            packages.verify_package(folder)

    def test_metadata_only_and_existing_destination(self):
        out = self.base / 'metadata'
        result = packages.build_release(out, ['sodargye'])
        folder = out / result[0]['folder']
        self.assertFalse((folder / '.teacher-corpus').exists())
        self.assertFalse(packages.verify_package(folder)['include_corpus'])
        with self.assertRaises(FileExistsError):
            packages.build_release(out, ['sodargye'])

    def test_attribution_reference_does_not_merge_teacher_corpus(self):
        out = self.base / 'attribution'
        result = packages.build_release(out, ['sodargye', 'danzeng-gyatso', 'jigme-phuntsok'], include_corpus=True)
        folders = {r['person']: out / r['folder'] for r in result}
        sd = folders['sodargye']
        card = json.loads((sd / 'references/quote-attributions.json').read_text())
        self.assertEqual(card[0]['author'], 'mentso')
        self.assertFalse((sd / '.teacher-corpus/mentso-source').exists())
        process = subprocess.run([sys.executable, str(sd / 'scripts/teacher_corpus.py'),
                                  'verify', '--person', 'sodargye', '--quote', '跨人物署名测试'],
                                 cwd=self.base, capture_output=True, text=True)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertFalse(json.loads(process.stdout)['verified'])
        self.assertEqual(json.loads((folders['danzeng-gyatso'] / 'references/quote-attributions.json').read_text()), [])
        profile = (folders['jigme-phuntsok'] / 'references/person-profile.md').read_text()
        self.assertIn('2004', profile)
        self.assertIn('https://www.lotsawahouse.org/tibetan-masters/khenpo-jigme-phuntsok/', profile)

    def test_missing_cache_leaves_no_release(self):
        shutil.rmtree(corpus.CACHE / 'danzeng-gyatso-source')
        out = self.base / 'failure'
        with self.assertRaises(ValueError):
            packages.build_release(out, ['danzeng-gyatso'], include_corpus=True)
        self.assertFalse(out.exists())

    def test_quote_cards_verify_text_and_keep_editor_notes_separate(self):
        sources = json.loads(corpus.CONFIG.read_text())
        cards = packages.quote_cards('sodargye', sources, verify_text=True)
        self.assertEqual(cards[0]['author'], 'sodargye')
        self.assertIn('citation_markdown', cards[0])
        self.assertEqual(packages.quote_cards('mentso', sources, True), [])
        self.assertEqual(packages.quote_cards('sodargye', sources)[0]['verification'],
                         'not_rechecked_in_metadata_build')
        cards[0]['quote'] = '伪造测试句'
        packages.write_json(packages.DATA / 'quote-cards.json', cards)
        with self.assertRaisesRegex(ValueError, 'text or context mismatch'):
            packages.build_release(self.base / 'bad-card', ['sodargye'], include_corpus=True)
        self.assertFalse((self.base / 'bad-card').exists())

    def test_biographical_facts_are_person_scoped_and_keep_evidence_limits(self):
        result = packages.build_release(self.base / 'bios', ['sodargye', 'mentso', 'jigme-phuntsok'])
        folders = {r['person']: self.base / 'bios' / r['folder'] for r in result}
        facts = json.loads((folders['sodargye'] / 'references/person-facts.json').read_text())
        self.assertEqual([f['id'] for f in facts], ['fixture-bio'])
        rendered = (folders['sodargye'] / 'references/person-profile.md').read_text()
        self.assertIn('https://example.org/bio', rendered)
        self.assertIn('fixture_metadata', rendered)
        self.assertIn('仅为测试，不是原话。', rendered)
        self.assertEqual(json.loads((folders['mentso'] / 'references/person-facts.json').read_text()), [])
        legacy = json.loads((folders['jigme-phuntsok'] / 'references/person-facts.json').read_text())
        self.assertEqual(len(legacy), 1)
        self.assertIn('2004', legacy[0]['statement'])

    def test_topics_stay_with_their_person_and_source(self):
        routes = corpus.topic_routes('mentso', json.loads(corpus.CONFIG.read_text()))
        self.assertEqual(len(routes), 1)
        self.assertTrue(routes[0]['matches'])
        self.assertTrue(all(r['person'] == 'mentso' for r in routes[0]['matches']))
        self.assertEqual(corpus.topic_routes('mentso', json.loads(corpus.CONFIG.read_text()), 'unknown-topic'), [])


if __name__ == '__main__':
    unittest.main()
