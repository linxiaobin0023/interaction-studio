from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

EXPECTED_TABLES = {
    "alembic_version",
    "attempts",
    "cases",
    "dataset_manifests",
    "dataset_runs",
    "evidence_manifests",
    "formal_runs",
    "gate_results",
    "gate_threshold_versions",
    "operation_events",
    "outputs",
    "projects",
    "qc_results",
    "studio_drafts",
    "studio_events",
    "studio_templates",
    "studio_jobs",
    "studio_job_outputs",
    "studio_reviews",
    "studio_users",
    "studio_sessions",
    "studio_security_events",
}


def migrate_database(database_path: Path) -> tuple[Config, object]:
    project_root = Path(__file__).parents[3]
    config = Config(project_root / "alembic.ini")
    database_url = f"sqlite:///{database_path}"
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return config, create_engine(database_url)


def seed_attempt_dependencies(connection) -> None:
    connection.execute(text("INSERT INTO projects (id, name) VALUES ('p1', 'test')"))
    connection.execute(
        text(
            "INSERT INTO dataset_manifests "
            "(id, project_id, dataset_kind, manifest_sha256, case_count, distribution, custodian) "
            "VALUES ('d1', 'p1', 'DEVELOPMENT', :sha, 1, '{}', 'tester')"
        ),
        {"sha": "a" * 64},
    )
    connection.execute(
        text(
            "INSERT INTO cases "
            "(id, dataset_manifest_id, external_case_id, interaction_kind, pose_zone, "
            "case_base_sha256, build_id, frozen) "
            "VALUES ('c1', 'd1', 'case-1', 'MOUTH', 'GREEN', :sha, 'build-1', 0)"
        ),
        {"sha": "b" * 64},
    )
    connection.execute(
        text(
            "INSERT INTO dataset_runs "
            "(id, dataset_manifest_id, build_id, state, resource_version) "
            "VALUES ('run-1', 'd1', 'build-1', 'DRAFT', 1)"
        )
    )


def test_initial_migration_up_and_down(tmp_path: Path) -> None:
    config, engine = migrate_database(tmp_path / "migration.db")

    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]


def test_migration_matches_orm_metadata(tmp_path: Path) -> None:
    config, _ = migrate_database(tmp_path / "metadata-check.db")

    command.check(config)


def test_attempt_requires_exactly_one_run(tmp_path: Path) -> None:
    _, engine = migrate_database(tmp_path / "run-check.db")

    with engine.begin() as connection:
        seed_attempt_dependencies(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO attempts "
                    "(id, formal_run_id, dataset_run_id, case_id, business_attempt_no, state, "
                    "request_hash, idempotency_key, resource_version, infra_retry_count) "
                    "VALUES ('a1', NULL, NULL, 'c1', 1, 'CREATED', :sha, 'idem-1', 1, 0)"
                ),
                {"sha": "c" * 64},
            )


def test_attempt_business_number_and_retry_budget_are_bounded(tmp_path: Path) -> None:
    _, engine = migrate_database(tmp_path / "budget-check.db")

    with engine.begin() as connection:
        seed_attempt_dependencies(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO attempts "
                    "(id, formal_run_id, dataset_run_id, case_id, business_attempt_no, state, "
                    "request_hash, idempotency_key, resource_version, infra_retry_count) "
                    "VALUES ('a1', NULL, 'run-1', 'c1', 3, 'CREATED', :sha, 'idem-1', 1, 3)"
                ),
                {"sha": "c" * 64},
            )


def test_database_rejects_unknown_attempt_state(tmp_path: Path) -> None:
    _, engine = migrate_database(tmp_path / "state-check.db")

    with engine.begin() as connection:
        seed_attempt_dependencies(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO attempts "
                    "(id, formal_run_id, dataset_run_id, case_id, business_attempt_no, state, "
                    "request_hash, idempotency_key, resource_version, infra_retry_count) "
                    "VALUES ('a1', NULL, 'run-1', 'c1', 1, 'MADE_UP', :sha, 'idem-1', 1, 0)"
                ),
                {"sha": "c" * 64},
            )


def test_ready_evidence_requires_verified_object_lock(tmp_path: Path) -> None:
    _, engine = migrate_database(tmp_path / "evidence-check.db")

    with engine.begin() as connection:
        seed_attempt_dependencies(connection)
        connection.execute(
            text(
                "INSERT INTO formal_runs "
                "(id, dataset_manifest_id, build_id, qc_protocol_version, analysis_spec_sha256, "
                "state, resource_version) "
                "VALUES ('f1', 'd1', 'build-1', 'qc-1', :sha, 'DRAFT', 1)"
            ),
            {"sha": "d" * 64},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO evidence_manifests "
                    "(id, formal_run_id, case_id, manifest_sha256, chain_head_sha256, status, "
                    "object_refs, object_lock_verified) "
                    "VALUES ('e1', 'f1', 'c1', :manifest_sha, :chain_sha, 'READY', '[]', 0)"
                ),
                {"manifest_sha": "e" * 64, "chain_sha": "f" * 64},
            )
