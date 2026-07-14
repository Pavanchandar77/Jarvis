"""Storage package round-trip."""

from services.semantic_twin.service import SemanticTwinService


def test_storage_roundtrip(sample_app_root, twin_storage, sample_manifest):
    svc = SemanticTwinService(twin_storage)
    twin = svc.generate(sample_app_root, sample_manifest, application_id="store-app")
    h1 = twin.content_hash
    loaded = svc.load(twin.twin_id)
    assert loaded.content_hash == h1
    assert len(loaded.nodes) == len(twin.nodes)
    listing = svc.list()
    assert any(t["twin_id"] == twin.twin_id for t in listing)
    svc.delete(twin.twin_id)
    listing2 = svc.list()
    assert not any(t["twin_id"] == twin.twin_id for t in listing2)
