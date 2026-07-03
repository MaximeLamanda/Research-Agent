from app.models.config import Config
from app.models.project import Project
from app.models.project_merge import ProjectMerge


def test_config_defaults(db_session):
    config = Config(departments=["69", "38"])
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    assert config.sectors == ["industriel", "logistique", "retail"]


def test_project_siren_fields(db_session):
    project = Project(
        name="Entrepôt Test",
        match_key="test|lyon",
        siren="123456789",
        company_legal_name="TEST SAS",
        naf_code="52.10B",
    )
    db_session.add(project)
    db_session.commit()

    saved = db_session.query(Project).one()
    assert saved.siren == "123456789"
    assert saved.company_legal_name == "TEST SAS"
    assert saved.naf_code == "52.10B"


def test_project_merge_model(db_session):
    import uuid

    from app.models.run import Run

    run = Run(status="completed")
    kept = Project(name="Projet A", match_key="a|lyon")
    absorbed = Project(name="Projet B", match_key="b|lyon")
    db_session.add_all([run, kept, absorbed])
    db_session.flush()

    merge = ProjectMerge(
        run_id=run.id,
        kept_project_id=kept.id,
        absorbed_project_id=absorbed.id,
        method="match_key",
        snapshot={"kept": {"name": "Projet A"}, "absorbed": {"name": "Projet B"}},
    )
    db_session.add(merge)
    db_session.commit()

    db_session.refresh(merge)
    assert merge.method == "match_key"
    assert merge.kept_project_id == kept.id


def test_dedup_decision_roundtrip(db_session):
    from app.models import DedupDecision, Run

    run = Run(status="in_progress")
    project_a = Project(name="A", match_key="a|x")
    project_b = Project(name="B", match_key="b|x")
    db_session.add_all([run, project_a, project_b])
    db_session.flush()

    decision = DedupDecision(
        project_a_id=min(project_a.id, project_b.id, key=str),
        project_b_id=max(project_a.id, project_b.id, key=str),
        same_project=False,
        reason="Sites distincts",
        pair_fingerprint="abc123",
        run_id=run.id,
    )
    db_session.add(decision)
    db_session.commit()

    stored = db_session.query(DedupDecision).one()
    assert stored.same_project is False
    assert stored.reason == "Sites distincts"
    assert stored.pair_fingerprint == "abc123"
