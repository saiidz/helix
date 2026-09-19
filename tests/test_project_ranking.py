import pytest

from helix.projects import MAX_CONTEXT_CHARS, ProjectStore


@pytest.mark.parametrize('overview', ['README.md', 'package.json', 'pyproject.toml', 'requirements.txt'])
def test_symbol_match_beats_overview_bonus(tmp_path, overview):
    store = ProjectStore(tmp_path / 'projects.sqlite3')
    project = store.create('Ranking')['id']
    store.add_file(project, 'src/worker.py', 'def worker_symbol():\n    return 1\n')
    store.add_file(project, overview, 'General introduction to the app.')
    hits = store.retrieve(project, 'Where is worker_symbol implemented?', limit=1)
    assert hits[0]['path'] == 'src/worker.py'


def test_generic_overview_and_specific_path_both_work(tmp_path):
    store = ProjectStore(tmp_path / 'projects.sqlite3')
    project = store.create('Ranking')['id']
    store.add_file(project, 'README.md', 'Welcome to this workspace.')
    store.add_file(project, 'src/worker.py', 'value = 1')
    assert store.retrieve(project, 'Explain the project')[0]['path'] == 'README.md'
    assert store.retrieve(project, 'Explain src/worker.py')[0]['path'] == 'src/worker.py'


def test_ranking_does_not_expand_scope_or_context_budget(tmp_path):
    store = ProjectStore(tmp_path / 'projects.sqlite3')
    project = store.create('Selected')['id']
    other = store.create('Not selected')['id']
    store.add_file(other, 'private.py', 'needle needle secret')
    for index in range(8):
        store.add_file(project, f'src/worker{index}.py', 'needle\n' * 2000)
    hits = store.retrieve(project, 'Find needle', limit=10)
    assert sum(len(hit['excerpt']) for hit in hits) <= MAX_CONTEXT_CHARS
    assert all(hit['path'].startswith('src/') for hit in hits)
