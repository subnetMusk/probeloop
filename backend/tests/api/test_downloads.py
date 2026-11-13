from __future__ import annotations

from datetime import UTC, datetime

from probeloop.api.downloads import file_headers, subject_filename, timestamped_filename

MOMENT = datetime(2026, 11, 13, 9, 5, 7, tzinfo=UTC).timestamp()


def test_subject_files_are_named_after_the_subject_and_its_creation_day() -> None:
    assert (
        subject_filename("interview", "0123456789abcdef", MOMENT, "report-v2.pdf")
        == "probeloop-interview-20261113-01234567-report-v2.pdf"
    )
    assert (
        subject_filename("cv-check", "fedcba9876543210", 0.0, "report-v1.json")
        == "probeloop-cv-check-19700101-fedcba98-report-v1.json"
    )


def test_data_files_are_named_after_the_moment_in_utc() -> None:
    assert timestamped_filename("backup", MOMENT, "zip") == "probeloop-backup-20261113-090507.zip"


def test_headers_carry_an_ascii_fallback_and_the_utf8_name() -> None:
    headers = file_headers('Esito "finale" è.md', inline=True)
    assert headers["Content-Disposition"] == (
        'inline; filename="Esito _finale_ _.md"; '
        "filename*=UTF-8''Esito%20%22finale%22%20%C3%A8.md"
    )
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert file_headers("a.zip", inline=False)["Content-Disposition"].startswith("attachment;")
