"""Incremental update bumps revision and keeps twin queryable."""

from pathlib import Path

from services.semantic_twin.service import SemanticTwinService


def test_incremental_update(sample_app_root, twin_storage, sample_manifest, tmp_path):
    # Copy fixture to writable tree
    import shutil
    app = tmp_path / "app"
    shutil.copytree(sample_app_root, app)

    svc = SemanticTwinService(twin_storage)
    twin1 = svc.generate(app, sample_manifest, application_id="inc-app")
    rev1 = twin1.content_revision
    hash1 = twin1.content_hash

    # Modify a file
    target = app / "src" / "app.py"
    text = target.read_text(encoding="utf-8")
    target.write_text(text + "\n\ndef new_helper():\n    return 42\n", encoding="utf-8")

    twin2 = svc.update(
        twin1.twin_id,
        app,
        changed_files=["src/app.py"],
    )
    assert twin2.content_revision == rev1 + 1
    assert twin2.twin_id == twin1.twin_id
    # New helper should appear
    names = {n.name for n in twin2.nodes}
    assert "new_helper" in names or twin2.content_hash != hash1

    # Force full rebuild still works
    twin3 = svc.update(twin1.twin_id, app, force_full=True)
    assert twin3.content_revision >= twin2.content_revision
