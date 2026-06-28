import pytest
from sqlalchemy.exc import IntegrityError

from src.models import Chunk, ChunkEmbedding, Collection, Document, PipelineVersion


def test_collection_has_pipeline_versions(session):
    collection = Collection(name="test")
    version = PipelineVersion(collection=collection, config={}, status="active")
    session.add(collection)
    session.flush()

    assert version in collection.pipeline_versions


def test_chunk_version_id_isolation(session):
    collection = Collection(name="iso")
    v1 = PipelineVersion(collection=collection, config={}, status="active")
    v2 = PipelineVersion(collection=collection, config={}, status="staging")
    doc = Document(collection=collection, filename="f.txt", raw_content="x")
    c1 = Chunk(document=doc, version=v1, content="a", strategy="fixed", chunk_index=0)
    c2 = Chunk(document=doc, version=v2, content="b", strategy="fixed", chunk_index=0)
    session.add_all([collection, v1, v2, doc, c1, c2])
    session.flush()

    result = session.query(Chunk).filter_by(version_id=v1.id).all()
    assert result == [c1]


def test_chunk_embedding_relationship(session):
    collection = Collection(name="emb")
    version = PipelineVersion(collection=collection, config={}, status="active")
    doc = Document(collection=collection, filename="g.txt", raw_content="y")
    chunk = Chunk(document=doc, version=version, content="c", strategy="fixed", chunk_index=0)
    emb = ChunkEmbedding(chunk=chunk, embedding=[0.1] * 768, model_name="nomic")
    session.add_all([collection, version, doc, chunk, emb])
    session.flush()

    assert chunk.embedding.model_name == "nomic"


def test_pipeline_version_status_rejects_invalid_value(session):
    collection = Collection(name="status-invalid")
    version = PipelineVersion(collection=collection, config={}, status="banana")
    session.add_all([collection, version])
    with pytest.raises(IntegrityError):
        session.flush()


def test_pipeline_version_status_accepts_valid_values(session):
    collection = Collection(name="status-valid")
    session.add(collection)
    session.flush()
    for status in ("active", "staging", "archived", "deleted"):
        version = PipelineVersion(collection=collection, config={}, status=status)
        session.add(version)
    session.flush()
