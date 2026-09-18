import pytest

from helix.projects import ProjectStore


def test_project_create_import_retrieve_delete(tmp_path):
    store = ProjectStore(tmp_path / "projects.sqlite3")
    project = store.create("Helix test")

    store.add_file(
        project["id"],
        "src/app.py",
        "def route_request():\n    return 'engineer'\n",
    )
    store.add_file(
        project["id"],
        "README.md",
        "# Helix\nLocal AI command center.\n",
    )

    loaded = store.get(project["id"])
    assert loaded is not None
    assert loaded["file_count"] == 2

    files = store.list_files(project["id"])
    assert [item["path"] for item in files] == ["README.md", "src/app.py"]

    hits = store.retrieve(project["id"], "Where is route_request implemented?")
    assert hits
    assert hits[0]["path"] == "src/app.py"
    assert "route_request" in hits[0]["excerpt"]

    assert store.delete(project["id"]) is True
    assert store.get(project["id"]) is None


def test_project_file_upsert(tmp_path):
    store = ProjectStore(tmp_path / "projects.sqlite3")
    project = store.create("Upsert")
    first = store.add_file(project["id"], "src/app.ts", "export const n = 1;")
    second = store.add_file(project["id"], "src/app.ts", "export const n = 2;")

    assert first["id"] == second["id"]
    assert store.get(project["id"])["file_count"] == 1
    hits = store.retrieve(project["id"], "export const n")
    assert "2" in hits[0]["excerpt"]


@pytest.mark.parametrize("path,content", [
    ("assets/logo.png", "binary-ish"),
    ("../secret.py", "print('no')"),
    ("nested/../../secret.ts", "export default 1"),
])
def test_project_rejects_unsupported_or_unsafe_paths(tmp_path,path,content):
    store = ProjectStore(tmp_path / "projects.sqlite3")
    project = store.create("Unsafe")

    with pytest.raises(ValueError):
        store.add_file(project["id"], path, content)
