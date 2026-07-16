import pytest
from app.agent.dedup_agent import run_dedup_pass
from app.models.project import Project
from app.models.run import Run


@pytest.mark.asyncio
async def test_dedup_pass_filters_by_country_not_department_prefix(db_session):
    run = Run(status="completed", mode="full")
    ie_project = Project(
        name="Dublin Warehouse",
        city="Dublin",
        department="LE - Leinster",
        country="IE",
        match_key="wh|dublin",
    )
    mislabeled = Project(
        name="Dublin Copy",
        city="Dublin",
        department="LE - Leinster",
        country="FR",
        match_key="wh|dublin2",
    )
    db_session.add_all([run, ie_project, mislabeled])
    db_session.commit()

    events = await run_dedup_pass(db_session, run, ["LE"], country="IE")

    assert events == []
    assert ie_project.merged_into_id is None
    assert mislabeled.merged_into_id is None
