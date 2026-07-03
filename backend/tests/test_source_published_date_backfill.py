from datetime import date

from app.data.source_published_date_backfill import (
    backfill_source_published_dates,
    build_published_dates_from_run_steps,
)
from app.models.project import Project
from app.models.run import Run
from app.models.run_step import RunStep
from app.models.source import Source


def _add_source(db_session, *, url: str, published_at=None, extracted_data=None):
    project = Project(name="Test", match_key=f"key-{url}")
    db_session.add(project)
    db_session.flush()
    source = Source(
        project_id=project.id,
        url=url,
        published_at=published_at,
        extracted_data=extracted_data,
    )
    db_session.add(source)
    db_session.commit()
    return source


def test_build_published_dates_from_run_steps(db_session):
    run = Run(status="completed")
    db_session.add(run)
    db_session.flush()

    db_session.add_all(
        [
            RunStep(
                run_id=run.id,
                step_type="extracting",
                data={"url": "https://a.com", "published_at": "2025-03-01"},
            ),
            RunStep(
                run_id=run.id,
                step_type="exa_fetch_done",
                data={
                    "articles": [
                        {"url": "https://b.com", "published_at": "2025-04-15T10:00:00.000Z"}
                    ]
                },
            ),
            RunStep(
                run_id=run.id,
                step_type="exa_search_done",
                data={"results": [{"url": "https://c.com", "published_at": "2025-05-20"}]},
            ),
        ]
    )
    db_session.commit()

    dates = build_published_dates_from_run_steps(db_session)

    assert dates == {
        "https://a.com": date(2025, 3, 1),
        "https://b.com": date(2025, 4, 15),
        "https://c.com": date(2025, 5, 20),
    }


def test_backfill_from_extracted_data(db_session):
    _add_source(
        db_session,
        url="https://extracted.com",
        extracted_data={"published_at": "2025-01-10", "name": "Warehouse"},
    )

    report = backfill_source_published_dates(db_session)

    source = db_session.query(Source).one()
    assert report.total_missing == 1
    assert report.from_extracted_data == 1
    assert report.updated == 1
    assert source.published_at == date(2025, 1, 10)
    assert source.extracted_data["published_at"] == "2025-01-10"


def test_backfill_from_run_steps(db_session):
    _add_source(db_session, url="https://run-step.com")
    run = Run(status="completed")
    db_session.add(run)
    db_session.flush()
    db_session.add(
        RunStep(
            run_id=run.id,
            step_type="extracting",
            data={"url": "https://run-step.com", "published_at": "2025-02-02"},
        )
    )
    db_session.commit()

    report = backfill_source_published_dates(db_session)

    source = db_session.query(Source).one()
    assert report.from_run_steps == 1
    assert report.updated == 1
    assert source.published_at == date(2025, 2, 2)


def test_backfill_dry_run_does_not_persist(db_session):
    _add_source(
        db_session,
        url="https://dry-run.com",
        extracted_data={"published_at": "2025-06-06"},
    )

    report = backfill_source_published_dates(db_session, dry_run=True)

    source = db_session.query(Source).one()
    assert report.from_extracted_data == 1
    assert report.updated == 0
    assert source.published_at is None


def test_backfill_skips_sources_with_existing_date(db_session):
    _add_source(
        db_session,
        url="https://already.com",
        published_at=date(2024, 12, 1),
    )

    report = backfill_source_published_dates(db_session)

    assert report.total_missing == 0
    assert report.updated == 0
