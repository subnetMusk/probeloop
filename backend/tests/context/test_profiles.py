"""Profiles of reusable documents and revisions of edited documents."""

from __future__ import annotations

import pytest

from probeloop.context.domain.model import (
    ContextError,
    Document,
    DocumentKind,
    DocumentOrigin,
    JobMode,
    Profile,
)


def document(kind: DocumentKind, origin: DocumentOrigin = DocumentOrigin.TYPED) -> Document:
    upload = origin in (DocumentOrigin.UPLOAD, DocumentOrigin.EDITED)
    return Document(
        id=f"{kind.value}-{origin.value}",
        kind=kind,
        title="Titolo",
        origin=origin,
        text="Testo sintetico.",
        created_at=0,
        media_type="application/pdf" if upload else "text/plain",
        filename="file.pdf" if upload else None,
        sha256="a" * 64 if upload else None,
        warnings=("hidden text removed",) if upload else (),
    )


def test_a_profile_holds_a_cv_a_job_offer_and_resources() -> None:
    cv = document(DocumentKind.CV, DocumentOrigin.UPLOAD)
    resource = document(DocumentKind.RESOURCE)
    profile = Profile("p", "Backend", (resource,), 0, 0, cv=cv)
    assert profile.job_mode is JobMode.NONE
    offer = document(DocumentKind.JOB_OFFER)
    assert Profile("p", "Backend", (), 0, 0, job_offer=offer).job_mode is JobMode.OFFER
    generated = document(DocumentKind.JOB_OFFER, DocumentOrigin.GENERATED)
    assert Profile("p", "Backend", (), 0, 0, job_offer=generated).job_mode is JobMode.GENERATED


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"cv": document(DocumentKind.RESOURCE)}, "CV document"),
        ({"job_offer": document(DocumentKind.CV)}, "job offer document"),
        ({"resources": (document(DocumentKind.CV),)}, "resource documents"),
    ],
)
def test_each_profile_slot_takes_its_own_kind(fields: dict[str, object], message: str) -> None:
    arguments: dict[str, object] = {"resources": ()} | fields
    with pytest.raises(ContextError, match=message):
        Profile("p", "Backend", created_at=0, updated_at=0, **arguments)  # type: ignore[arg-type]


def test_renaming_keeps_the_documents() -> None:
    cv = document(DocumentKind.CV)
    renamed = Profile("p", "Backend", (), 0, 0, cv=cv).renamed("  Ruoli backend ", 5)
    assert (renamed.name, renamed.updated_at, renamed.cv) == ("Ruoli backend", 5, cv)
    with pytest.raises(ContextError, match="profile name"):
        Profile("p", "Backend", (), 0, 0).renamed(" ", 5)


def test_editing_an_uploaded_file_keeps_its_original() -> None:
    uploaded = document(DocumentKind.CV, DocumentOrigin.UPLOAD)
    edited = uploaded.revised("d2", " Testo corretto. ", None, 9)
    assert edited.origin is DocumentOrigin.EDITED
    assert (edited.filename, edited.sha256, edited.media_type) == (
        uploaded.filename,
        uploaded.sha256,
        uploaded.media_type,
    )
    assert (edited.id, edited.text, edited.created_at, edited.warnings) == (
        "d2",
        "Testo corretto.",
        9,
        (),
    )
    assert edited.has_original
    assert edited.revised("d3", "Ancora.", "Nuovo titolo", 10).origin is DocumentOrigin.EDITED


@pytest.mark.parametrize("origin", [DocumentOrigin.TYPED, DocumentOrigin.GENERATED])
def test_editing_typed_or_generated_text_keeps_its_origin(origin: DocumentOrigin) -> None:
    edited = document(DocumentKind.JOB_OFFER, origin).revised("d2", "Altro testo.", None, 1)
    assert edited.origin is origin
    assert not edited.has_original
