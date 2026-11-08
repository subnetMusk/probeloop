from __future__ import annotations

import itertools
from dataclasses import replace
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from probeloop.ai.fake import FakeChatModel
from probeloop.context.application.analysis import ContextAnalyser
from probeloop.context.application.ports import ExtractedText
from probeloop.context.application.snapshots import snapshot_of
from probeloop.context.domain.model import JobMode, Profile, Review
from probeloop.storage.database import sessionmaker
from probeloop.storage.sql_context import SqlContextStore
from tests.context.conftest import cv, offer, scripted_analysis
from tests.context.test_preparation import in_review


async def test_context_roundtrip_keeps_reviews_and_immutable_snapshots(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    store = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    p = in_review()
    for document in p.documents:
        await store.add_document(document)
    await store.save_preparation(p)
    loaded = await store.preparation(p.id)
    assert loaded == p
    assert loaded is not None
    loaded.review_fact("f2", Review.EXCLUDED)
    snapshot = snapshot_of(loaded, "s1", 1)
    await store.save_snapshot(snapshot)
    loaded.approve(snapshot.id)
    await store.save_preparation(loaded)
    assert await store.snapshot("s1") == snapshot
    assert await store.snapshot_by_hash(snapshot.content_hash) == snapshot
    assert (await store.preparation(p.id)) == loaded
    # Further changes to the in-memory preparation cannot alter the frozen snapshot.
    loaded.facts.clear()
    assert await store.snapshot("s1") == snapshot


async def test_profiles_keep_resource_order_and_can_be_overwritten(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    from probeloop.context.domain.model import DocumentKind

    store = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    a = replace(cv(), id="a", kind=DocumentKind.RESOURCE, title="Routing notes")
    b = replace(offer(), id="b", kind=DocumentKind.RESOURCE, title="README")
    for document in (a, b):
        await store.add_document(document)
    profile = Profile("p1", "Backend", (b, a), 1, 1)
    await store.save_profile(profile)
    assert await store.profile("p1") == profile
    updated = replace(profile, resources=(a,), updated_at=2)
    await store.save_profile(updated)
    assert await store.profiles() == [updated]
    with_documents = replace(updated, cv=cv(), job_offer=offer(), updated_at=3)
    for document in (cv(), offer()):
        await store.add_document(document)
    await store.save_profile(with_documents)
    assert await store.profile("p1") == with_documents
    assert await store.delete_profile("p1")
    assert await store.profiles() == []


async def test_fact_extractions_are_reused_after_reopening_the_store(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    model = FakeChatModel([scripted_analysis()])
    store = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    analyser = ContextAnalyser(model, cache=store)
    first = await analyser.analyse([cv(), offer()], JobMode.OFFER, "it")
    assert len(model.requests) == 3
    reopened = SqlContextStore(sessionmaker(engine), tmp_path / "blobs")
    second = await ContextAnalyser(model, cache=reopened).analyse(
        [cv(), offer()], JobMode.OFFER, "it"
    )
    assert len(model.requests) == 3  # extraction and matching both survive a restart
    assert [f.statement for f in first.facts] == [f.statement for f in second.facts]
    # Output language is part of the cache key.
    await analyser.analyse([cv(), offer()], JobMode.OFFER, "en")
    assert len(model.requests) == 6


async def test_upload_parsing_is_reused_but_document_titles_are_independent(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    from probeloop.context.application.service import ContextService
    from probeloop.context.domain.model import DocumentKind

    class Extractor:
        calls = 0

        async def extract(self, data: bytes, filename: str) -> ExtractedText:
            self.calls += 1
            return ExtractedText(data.decode(), "text/plain", ("warning",))

    async def unused_submit(kind: str, subject: str) -> None:
        raise AssertionError("upload does not queue analysis")

    ids = (f"{n:032x}" for n in itertools.count(1))
    extractor = Extractor()
    service = ContextService(
        store=SqlContextStore(sessionmaker(engine), tmp_path / "blobs"),
        analyser=ContextAnalyser(FakeChatModel([])),
        extractor=extractor,
        submit=unused_submit,  # type: ignore[arg-type]
        now=lambda: 1,
        new_id=lambda: next(ids),
    )
    first = await service.upload(DocumentKind.CV, "CV", "first.txt", b"Synthetic CV")
    second = await service.upload(DocumentKind.RESOURCE, "Notes", "second.txt", b"Synthetic CV")
    assert extractor.calls == 1
    assert first.id != second.id
    assert second.title == "Notes"
    assert first.warnings == second.warnings == ("warning",)
