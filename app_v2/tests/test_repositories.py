from __future__ import annotations

from pathlib import Path

from app_v2.app.db.connection import connect, init_db
from app_v2.app.db.repositories.analyses import create_analysis, delete_analysis, get_analysis, list_analyses
from app_v2.app.db.repositories.events import list_events
from app_v2.app.db.repositories.files import discover_dxd_files, get_analysis_file, list_analysis_files


def test_create_and_get_analysis(tmp_path: Path):
    db_path = tmp_path / "test.sqlite"
    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis(
            conn,
            name="Campagne DXD",
            kind="campaign",
            source_dxd_dir="/tmp/acquisitions",
            config={"target_hz": 100},
        )
        conn.commit()

        loaded = get_analysis(conn, analysis["analysis_id"])
        assert loaded is not None
        assert loaded["name"] == "Campagne DXD"
        assert loaded["kind"] == "campaign"
        assert loaded["status"] == "active"
        assert loaded["source_dxd_dir"] == "/tmp/acquisitions"
        assert loaded["config"] == {"target_hz": 100}
        assert loaded["summary"] == {}

        items = list_analyses(conn)
        assert [item["analysis_id"] for item in items] == [analysis["analysis_id"]]


def test_discover_dxd_files_is_analysis_scoped_and_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.sqlite"
    dxd_dir = tmp_path / "dxd"
    dxd_dir.mkdir()
    (dxd_dir / "run_001.dxd").write_bytes(b"one")
    (dxd_dir / "run_002.DXD").write_bytes(b"two")
    (dxd_dir / "ignore.txt").write_text("no", encoding="utf-8")

    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis(conn, name="Campagne", source_dxd_dir=str(dxd_dir))
        analysis_id = analysis["analysis_id"]

        first = discover_dxd_files(conn, analysis_id=analysis_id, dxd_dir=dxd_dir)
        conn.commit()
        assert first["discovered_files"] == 2
        assert first["inserted_files"] == 2
        assert first["updated_files"] == 0

        files = list_analysis_files(conn, analysis_id)
        assert [item["source_dxd_name"] for item in files] == ["run_001.dxd", "run_002.DXD"]
        assert all(item["analysis_id"] == analysis_id for item in files)
        assert all(item["status"] == "discovered" for item in files)

        loaded_file = get_analysis_file(conn, analysis_id, files[0]["file_id"])
        assert loaded_file is not None
        assert loaded_file["source_dxd_name"] == "run_001.dxd"
        assert loaded_file["metadata"]["size_bytes"] == 3

        second = discover_dxd_files(conn, analysis_id=analysis_id, dxd_dir=dxd_dir)
        conn.commit()
        assert second["discovered_files"] == 2
        assert second["inserted_files"] == 0
        assert second["updated_files"] == 2
        assert len(list_analysis_files(conn, analysis_id)) == 2

        events = list_events(conn, analysis_id)
        assert events[0]["event_type"] == "dxd_discovery_finished"
        assert events[0]["payload"]["discovered_files"] == 2


def test_recursive_discovery(tmp_path: Path):
    db_path = tmp_path / "test.sqlite"
    dxd_dir = tmp_path / "dxd"
    nested = dxd_dir / "nested"
    nested.mkdir(parents=True)
    (nested / "nested_run.dxd").write_bytes(b"dxd")

    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis(conn, name="Recursive")

        non_recursive = discover_dxd_files(conn, analysis_id=analysis["analysis_id"], dxd_dir=dxd_dir)
        assert non_recursive["discovered_files"] == 0

        recursive = discover_dxd_files(
            conn,
            analysis_id=analysis["analysis_id"],
            dxd_dir=dxd_dir,
            recursive=True,
        )
        assert recursive["discovered_files"] == 1
        assert list_analysis_files(conn, analysis["analysis_id"])[0]["source_dxd_name"] == "nested_run.dxd"


def test_delete_analysis_cascades_related_rows(tmp_path: Path):
    db_path = tmp_path / "test.sqlite"
    dxd_dir = tmp_path / "dxd"
    dxd_dir.mkdir()
    (dxd_dir / "run_001.dxd").write_bytes(b"one")

    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis(conn, name="A supprimer")
        analysis_id = analysis["analysis_id"]
        discover_dxd_files(conn, analysis_id=analysis_id, dxd_dir=dxd_dir)
        conn.execute(
            """
            INSERT INTO channel_structures(
              analysis_id, preset_name, normalize_names, min_frequency,
              target_channels_json, recurrent_channels_json, summary_json,
              status, created_at, updated_at
            )
            VALUES (?, 'minimum', 1, 0.8, '[]', '[]', '{}', 'finished', 'now', 'now')
            """,
            (analysis_id,),
        )
        assert get_analysis(conn, analysis_id) is not None
        assert list_analysis_files(conn, analysis_id)

        assert delete_analysis(conn, analysis_id) is True
        assert get_analysis(conn, analysis_id) is None
        assert list_analysis_files(conn, analysis_id) == []
        assert conn.execute(
            "SELECT COUNT(*) FROM channel_structures WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone()[0] == 0
        assert list_events(conn, analysis_id) == []
        assert delete_analysis(conn, analysis_id) is False
