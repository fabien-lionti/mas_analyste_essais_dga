from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app_v2.app.api.routes.analyses import (
    CreateAnalysisRequest,
    UpdateAnalysisConfigRequest,
    create_analysis_endpoint,
    delete_analysis_endpoint,
    get_analysis_endpoint,
    list_analysis_events_endpoint,
    list_analyses_endpoint,
    update_analysis_config_endpoint,
)
from app_v2.app.api.routes.files import (
    DiscoverDxdRequest,
    discover_dxd_endpoint,
    get_file_endpoint,
    list_files_endpoint,
)
from app_v2.app.api.routes.exploration import exploration_parametric_endpoint
from app_v2.app.db.connection import connect, init_db
from app_v2.app.db.repositories.files import update_file_resampled_json


def test_analysis_api_and_dxd_discovery(tmp_path: Path):
    db_path = tmp_path / "api.sqlite"
    dxd_dir = tmp_path / "campaign"
    dxd_dir.mkdir()
    (dxd_dir / "a.dxd").write_bytes(b"a")
    (dxd_dir / "b.dxd").write_bytes(b"bb")

    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis_endpoint(
            CreateAnalysisRequest(
                name="Analyse test",
                kind="campaign",
                source_dxd_dir=str(dxd_dir),
                config={"note": "unit"},
            ),
            conn,
        )
        analysis_id = analysis["analysis_id"]
        assert analysis["name"] == "Analyse test"

        assert get_analysis_endpoint(analysis_id, conn)["analysis_id"] == analysis_id
        assert list_analyses_endpoint(limit=100, conn=conn)["items"][0]["analysis_id"] == analysis_id
        updated = update_analysis_config_endpoint(
            analysis_id,
            UpdateAnalysisConfigRequest(config={"sampling": {"target_frequency_hz": 100}}),
            conn,
        )
        assert updated["config"]["sampling"]["target_frequency_hz"] == 100

        discovery = discover_dxd_endpoint(
            analysis_id,
            DiscoverDxdRequest(dxd_dir=str(dxd_dir)),
            conn,
        )
        assert discovery["discovered_files"] == 2

        files = list_files_endpoint(analysis_id, limit=1000, conn=conn)["items"]
        assert [item["source_dxd_name"] for item in files] == ["a.dxd", "b.dxd"]

        loaded_file = get_file_endpoint(analysis_id, files[0]["file_id"], conn)
        assert loaded_file["source_dxd_name"] == "a.dxd"

        events = list_analysis_events_endpoint(analysis_id, limit=200, conn=conn)["items"]
        assert events[0]["event_type"] == "dxd_discovery_finished"


def test_missing_analysis_returns_404(tmp_path: Path):
    with connect(tmp_path / "api.sqlite") as conn:
        init_db(conn)
        with pytest.raises(HTTPException) as exc:
            list_files_endpoint("missing", limit=1000, conn=conn)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Analysis not found"


def test_discover_requires_existing_directory(tmp_path: Path):
    with connect(tmp_path / "api.sqlite") as conn:
        init_db(conn)
        analysis = create_analysis_endpoint(CreateAnalysisRequest(name="Analyse"), conn)
        with pytest.raises(HTTPException) as exc:
            discover_dxd_endpoint(
                analysis["analysis_id"],
                DiscoverDxdRequest(dxd_dir=str(tmp_path / "missing")),
                conn,
            )
        assert exc.value.status_code == 400
        assert exc.value.detail == "DXD directory does not exist"


def test_delete_analysis_endpoint(tmp_path: Path):
    with connect(tmp_path / "api.sqlite") as conn:
        init_db(conn)
        analysis = create_analysis_endpoint(CreateAnalysisRequest(name="Analyse"), conn)
        response = delete_analysis_endpoint(analysis["analysis_id"], conn)
        assert response == {"status": "ok", "deleted": analysis["analysis_id"]}
        with pytest.raises(HTTPException) as exc:
            get_analysis_endpoint(analysis["analysis_id"], conn)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            delete_analysis_endpoint(analysis["analysis_id"], conn)
        assert exc.value.status_code == 404


def test_parametric_exploration_returns_current_and_filtered_points(tmp_path: Path):
    db_path = tmp_path / "api.sqlite"
    dxd_dir = tmp_path / "campaign"
    json_dir = tmp_path / "json"
    dxd_dir.mkdir()
    json_dir.mkdir()
    (dxd_dir / "a.dxd").write_bytes(b"a")
    json_path = json_dir / "a.json"
    json_path.write_text(
        """
        {
          "timebase": {"time": [0, 1, 2]},
          "channels": {
            "resampled": {
              "vehicle.ax": {"values": [1, 2, 3], "unit": "m/s^2"},
              "vehicle.ay": {"values": [4, 5, 6], "unit": "m/s^2"}
            }
          }
        }
        """,
        encoding="utf-8",
    )

    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis_endpoint(
            CreateAnalysisRequest(name="Parametric", source_dxd_dir=str(dxd_dir)),
            conn,
        )
        analysis_id = analysis["analysis_id"]
        discover_dxd_endpoint(analysis_id, DiscoverDxdRequest(dxd_dir=str(dxd_dir)), conn)
        file_row = list_files_endpoint(analysis_id, limit=1000, conn=conn)["items"][0]
        conn.execute(
            "UPDATE analysis_files SET recorded_at = ? WHERE file_id = ?",
            ("2025-04-24T10:00:00+00:00", file_row["file_id"]),
        )
        update_file_resampled_json(
            conn,
            analysis_id=analysis_id,
            file_id=file_row["file_id"],
            json_path=json_path,
        )
        conn.commit()

        current = exploration_parametric_endpoint(
            analysis_id,
            x_channel="vehicle.ax",
            y_channel="vehicle.ay",
            scope="current",
            file_id=file_row["file_id"],
            max_points=8000,
            conn=conn,
        )
        assert current["file_count"] == 1
        assert current["point_count"] == 3
        assert current["items"][0]["x"] == 1
        assert current["items"][0]["y"] == 4
        limited = exploration_parametric_endpoint(
            analysis_id,
            x_channel="vehicle.ax",
            y_channel="vehicle.ay",
            scope="current",
            file_id=file_row["file_id"],
            max_points=2,
            conn=conn,
        )
        assert limited["point_count"] == 3
        assert limited["returned_point_count"] == 2

        filtered = exploration_parametric_endpoint(
            analysis_id,
            x_channel="vehicle.ax",
            y_channel="vehicle.ay",
            scope="filtered",
            date_from="2025-04-24",
            date_to="2025-04-24",
            max_points=8000,
            conn=conn,
        )
        assert filtered["file_count"] == 1
        assert filtered["point_count"] == 3
