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
from app_v2.app.api.routes.annotations import (
    AnnotationUpdateRequest,
    AnnotationWriteRequest,
    ManagedAnnotationLabelRequest,
    RenameAnnotationLabelRequest,
    create_annotation_endpoint,
    create_managed_annotation_label_endpoint,
    delete_annotation_endpoint,
    delete_annotation_label_endpoint,
    delete_managed_annotation_label_endpoint,
    list_annotation_labels_endpoint,
    list_annotation_sets_endpoint,
    list_managed_annotation_labels_endpoint,
    list_annotation_versions_endpoint,
    list_annotations_endpoint,
    rename_annotation_label_endpoint,
    summarize_annotation_labels_endpoint,
    update_managed_annotation_label_endpoint,
    update_annotation_endpoint,
)
from app_v2.app.api.routes.dynamic_analysis import (
    DynamicAnalysisDefinitionRequest,
    DynamicContextRequest,
    DynamicPredictionCorrectionRequest,
    DynamicPredictionRequest,
    DynamicPromptRequest,
    DynamicRunVersionRequest,
    build_context_endpoint,
    create_dynamic_analysis_endpoint,
    create_dynamic_prediction_correction_endpoint,
    create_dynamic_predictions_endpoint,
    create_prompt_endpoint,
    create_run_endpoint,
    create_run_version_endpoint,
    list_dynamic_predictions_endpoint,
    list_dynamic_analyses_endpoint,
    list_runs_endpoint,
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


def test_annotation_api_creates_updates_and_deletes_segment(tmp_path: Path):
    db_path = tmp_path / "api.sqlite"
    dxd_dir = tmp_path / "campaign"
    dxd_dir.mkdir()
    (dxd_dir / "a.dxd").write_bytes(b"a")

    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis_endpoint(
            CreateAnalysisRequest(name="Annotations", source_dxd_dir=str(dxd_dir)),
            conn,
        )
        analysis_id = analysis["analysis_id"]
        discover_dxd_endpoint(analysis_id, DiscoverDxdRequest(dxd_dir=str(dxd_dir)), conn)
        file_row = list_files_endpoint(analysis_id, limit=1000, conn=conn)["items"][0]

        sets = list_annotation_sets_endpoint(analysis_id, conn=conn)["items"]
        assert sets[0]["name"] == "Annotations manuelles"
        label = create_managed_annotation_label_endpoint(
            analysis_id,
            ManagedAnnotationLabelRequest(name="freinage", color="#1368ce"),
            conn=conn,
        )
        assert label["name"] == "freinage"
        assert list_managed_annotation_labels_endpoint(analysis_id, conn=conn)["items"][0]["name"] == "freinage"

        created = create_annotation_endpoint(
            analysis_id,
            AnnotationWriteRequest(
                file_id=file_row["file_id"],
                start_time_sec=1.0,
                end_time_sec=2.5,
                label="freinage",
                confidence=0.9,
                comment="segment net",
            ),
            conn,
        )
        assert created["label"] == "freinage"
        assert created["version_number"] == 1

        items = list_annotations_endpoint(analysis_id, file_id=file_row["file_id"], conn=conn)["items"]
        assert [item["annotation_id"] for item in items] == [created["annotation_id"]]
        assert list_annotation_labels_endpoint(analysis_id, conn=conn)["items"] == ["freinage"]
        summary = summarize_annotation_labels_endpoint(analysis_id, conn=conn)["items"]
        assert summary[0]["label"] == "freinage"
        assert summary[0]["annotation_count"] == 1

        create_managed_annotation_label_endpoint(
            analysis_id,
            ManagedAnnotationLabelRequest(name="virage", color="#15803d"),
            conn=conn,
        )
        updated = update_annotation_endpoint(
            analysis_id,
            created["annotation_id"],
            AnnotationUpdateRequest(
                start_time_sec=1.2,
                end_time_sec=3.0,
                label="virage",
                confidence=1.0,
                comment="corrige",
            ),
            conn,
        )
        assert updated["label"] == "virage"
        assert updated["version_number"] == 2
        versions = list_annotation_versions_endpoint(analysis_id, created["annotation_id"], conn=conn)["items"]
        assert [item["label"] for item in versions] == ["freinage", "virage"]

        managed_virage = [
            item for item in list_managed_annotation_labels_endpoint(analysis_id, conn=conn)["items"]
            if item["name"] == "virage"
        ][0]
        renamed_managed = update_managed_annotation_label_endpoint(
            analysis_id,
            managed_virage["label_id"],
            ManagedAnnotationLabelRequest(name="courbe", color="#15803d"),
            conn=conn,
        )
        assert renamed_managed["name"] == "courbe"
        assert list_annotation_labels_endpoint(analysis_id, conn=conn)["items"] == ["courbe", "freinage"]

        with pytest.raises(HTTPException) as exc:
            delete_managed_annotation_label_endpoint(
                analysis_id,
                renamed_managed["label_id"],
                delete_annotations=False,
                conn=conn,
            )
        assert exc.value.status_code == 409
        deleted_label = delete_managed_annotation_label_endpoint(
            analysis_id,
            renamed_managed["label_id"],
            delete_annotations=True,
            conn=conn,
        )
        assert deleted_label["deleted_annotations"] == 1
        assert list_annotations_endpoint(analysis_id, file_id=file_row["file_id"], conn=conn)["items"] == []


def test_dynamic_analysis_context_run_and_version(tmp_path: Path):
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
          "timebase": {"time": [0, 1, 2, 3]},
          "channels": {
            "resampled": {
              "vehicle.ax": {"values": [1, 2, 3, 4], "unit": "m/s^2"},
              "vehicle.ay": {"values": [4, 3, 2, 1], "unit": "m/s^2"}
            }
          }
        }
        """,
        encoding="utf-8",
    )

    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis_endpoint(
            CreateAnalysisRequest(name="Dynamique", source_dxd_dir=str(dxd_dir)),
            conn,
        )
        analysis_id = analysis["analysis_id"]
        discover_dxd_endpoint(analysis_id, DiscoverDxdRequest(dxd_dir=str(dxd_dir)), conn)
        file_row = list_files_endpoint(analysis_id, limit=1000, conn=conn)["items"][0]
        update_file_resampled_json(conn, analysis_id=analysis_id, file_id=file_row["file_id"], json_path=json_path)
        create_managed_annotation_label_endpoint(
            analysis_id,
            ManagedAnnotationLabelRequest(name="freinage"),
            conn=conn,
        )
        create_annotation_endpoint(
            analysis_id,
            AnnotationWriteRequest(
                file_id=file_row["file_id"],
                start_time_sec=1,
                end_time_sec=2,
                label="freinage",
            ),
            conn,
        )
        prompt = create_prompt_endpoint(
            analysis_id,
            DynamicPromptRequest(
                name="Protocole",
                system_prompt="Expert dynamique.",
                user_prompt="Analyse les segments.",
            ),
            conn,
        )
        request = DynamicContextRequest(
            name="Run test",
            prompt_id=prompt["prompt_id"],
            user_prompt="Analyse les segments.",
            channels=["vehicle.ax", "vehicle.ay"],
            labels=["freinage"],
            max_segments=10,
            max_points_per_segment=20,
        )
        context = build_context_endpoint(analysis_id, request, conn)
        assert context["summary"]["segment_count"] == 1
        assert context["segments"][0]["signal_context"]["channels"]["vehicle.ax"]["stats"]["count"] == 4

        run = create_run_endpoint(analysis_id, request, conn)
        assert run["status"] == "dry_run"
        assert list_runs_endpoint(analysis_id, conn)["items"][0]["run_id"] == run["run_id"]
        version = create_run_version_endpoint(
            analysis_id,
            run["run_id"],
            DynamicRunVersionRequest(
                response_markdown="Correction validée",
                confidence="haute",
                validated_for_dataset=True,
            ),
            conn,
        )
        assert version["version_number"] == 2
        assert version["validated_for_dataset"] is True


def test_dynamic_analysis_definition_prediction_and_correction(tmp_path: Path):
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
          "timebase": {"time": [0, 1, 2, 3]},
          "channels": {
            "resampled": {
              "vehicle.ax": {"values": [1, 2, 5, 4], "unit": "m/s^2"},
              "vehicle.ay": {"values": [0, 1, 0, -1], "unit": "m/s^2"}
            }
          }
        }
        """,
        encoding="utf-8",
    )

    with connect(db_path) as conn:
        init_db(conn)
        analysis = create_analysis_endpoint(
            CreateAnalysisRequest(name="Dynamique", source_dxd_dir=str(dxd_dir)),
            conn,
        )
        analysis_id = analysis["analysis_id"]
        discover_dxd_endpoint(analysis_id, DiscoverDxdRequest(dxd_dir=str(dxd_dir)), conn)
        file_row = list_files_endpoint(analysis_id, limit=1000, conn=conn)["items"][0]
        update_file_resampled_json(conn, analysis_id=analysis_id, file_id=file_row["file_id"], json_path=json_path)
        create_managed_annotation_label_endpoint(
            analysis_id,
            ManagedAnnotationLabelRequest(name="freinage"),
            conn=conn,
        )
        annotation = create_annotation_endpoint(
            analysis_id,
            AnnotationWriteRequest(
                file_id=file_row["file_id"],
                start_time_sec=1,
                end_time_sec=2,
                label="freinage",
            ),
            conn,
        )
        dynamic_analysis = create_dynamic_analysis_endpoint(
            analysis_id,
            DynamicAnalysisDefinitionRequest(
                name="Analyse freinage",
                system_prompt="Expert dynamique.",
                selected_channels=["vehicle.ax", "vehicle.ay"],
                indicators=[{"name": "peak_abs"}],
                label_category="freinage",
                output_schema={"synthese": "string"},
            ),
            conn,
        )
        assert dynamic_analysis["analysis_id"] == analysis_id
        assert dynamic_analysis["label_category"] == "freinage"
        assert list_dynamic_analyses_endpoint(analysis_id, conn)["items"][0]["dynamic_analysis_id"] == dynamic_analysis["dynamic_analysis_id"]

        predictions = create_dynamic_predictions_endpoint(
            analysis_id,
            dynamic_analysis["dynamic_analysis_id"],
            DynamicPredictionRequest(user_prompt="Interprète le freinage."),
            conn,
        )
        assert predictions["context_summary"]["segment_count"] == 1
        prediction = predictions["items"][0]
        assert prediction["annotation_id"] == annotation["annotation_id"]
        assert prediction["response_json"]["label_category"] == "freinage"
        assert list_dynamic_predictions_endpoint(analysis_id, dynamic_analysis["dynamic_analysis_id"], conn)["items"][0]["prediction_id"] == prediction["prediction_id"]

        correction = create_dynamic_prediction_correction_endpoint(
            analysis_id,
            prediction["prediction_id"],
            DynamicPredictionCorrectionRequest(
                corrected_response_markdown="Correction analyste",
                corrected_response_json={"synthese": "Correction analyste"},
                corrected_confidence="haute",
                validated_for_dataset=True,
            ),
            conn,
        )
        assert correction["validated_for_dataset"] is True
