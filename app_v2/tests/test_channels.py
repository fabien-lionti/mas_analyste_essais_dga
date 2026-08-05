from __future__ import annotations

from pathlib import Path

from app_v2.app.api.routes.channels import (
    channel_presence_endpoint,
    channel_presets_endpoint,
    channel_status_endpoint,
    recurrent_channels_endpoint,
)
from app_v2.app.db.connection import connect, init_db
from app_v2.app.db.repositories.analyses import create_analysis
from app_v2.app.db.repositories.channels import (
    get_channel_structure,
    get_validated_channel_structure,
    list_channel_anomalies,
    list_channel_anomaly_files,
    list_channel_inventory,
    recurrent_channels_from_inventory,
)
from app_v2.app.db.repositories.files import discover_dxd_files
from app_v2.app.services.channel_structure_service import analyze_channel_structure
from app_v2.app.services.channel_validation_service import save_validated_channel_structure


class FakeChannel:
    def __init__(self, name: str, unit: str = "", array_size: int = 1):
        self.name = name
        self.unit = unit
        self.array_size = array_size

    def __str__(self) -> str:
        return f"{self.name} ({self.unit})" if self.unit else self.name


class FakeReader:
    def __init__(self, channels: list[FakeChannel], sample_rate: float = 100.0):
        self.channels = channels
        self.sample_rate = sample_rate

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def __iter__(self):
        return iter(self.channels)


def fake_reader_factory(path: Path) -> FakeReader:
    if path.name == "a.dxd":
        return FakeReader(
            [
                FakeChannel("VelX", "km/h"),
                FakeChannel("VehLat_A_Actl", "m/s^2"),
                FakeChannel("Latitude", "_"),
            ],
            sample_rate=200.0,
        )
    return FakeReader(
        [
            FakeChannel("VelX", "km/h"),
            FakeChannel("VehYaw_W_Actl", "rad/s"),
        ],
        sample_rate=100.0,
    )


def create_analysis_with_dxd_files(tmp_path: Path):
    db_path = tmp_path / "channels.sqlite"
    dxd_dir = tmp_path / "dxd"
    dxd_dir.mkdir()
    (dxd_dir / "a.dxd").write_bytes(b"a")
    (dxd_dir / "b.dxd").write_bytes(b"b")
    conn = connect(db_path)
    init_db(conn)
    analysis = create_analysis(conn, name="Canaux", source_dxd_dir=str(dxd_dir))
    discover_dxd_files(conn, analysis_id=analysis["analysis_id"], dxd_dir=dxd_dir)
    return conn, analysis


def test_analyze_channel_structure_persists_inventory_and_recurrent_channels(tmp_path: Path):
    conn, analysis = create_analysis_with_dxd_files(tmp_path)
    try:
        result = analyze_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            preset_name="minimum",
            min_frequency=0.5,
            reader_factory=fake_reader_factory,
        )
        assert result["status"] == "finished"
        assert result["total_files"] == 2
        assert result["ok_files"] == 2

        structure = get_channel_structure(conn, analysis["analysis_id"])
        assert structure is not None
        assert structure["preset_name"] == "minimum"
        assert structure["summary"]["recurrent_channel_count"] >= 1

        inventory = list_channel_inventory(conn, analysis["analysis_id"])
        assert inventory
        vx_rows = [row for row in inventory if row["canonical_name"] == "vehicle.vx"]
        assert len(vx_rows) == 2

        recurrent = recurrent_channels_from_inventory(conn, analysis["analysis_id"])
        assert recurrent[0]["channel"] == "vehicle.vx"
        assert recurrent[0]["file_count"] == 2
    finally:
        conn.close()


def test_analyze_channel_structure_handles_empty_analysis(tmp_path: Path):
    with connect(tmp_path / "empty.sqlite") as conn:
        init_db(conn)
        analysis = create_analysis(conn, name="Vide")
        result = analyze_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            preset_name="minimum",
            reader_factory=fake_reader_factory,
        )
        assert result["total_files"] == 0
        assert result["recurrent_channel_count"] == 0
        assert list_channel_inventory(conn, analysis["analysis_id"]) == []


def test_channel_read_routes(tmp_path: Path):
    conn, analysis = create_analysis_with_dxd_files(tmp_path)
    try:
        presets = channel_presets_endpoint(analysis["analysis_id"], conn)
        assert "minimum" in presets["items"]

        analyze_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            preset_name="minimum",
            min_frequency=0.5,
            reader_factory=fake_reader_factory,
        )

        status = channel_status_endpoint(analysis["analysis_id"], conn)
        assert status["status"] == "finished"

        recurrent = recurrent_channels_endpoint(analysis["analysis_id"], conn=conn)
        assert recurrent["items"][0]["channel"] == "vehicle.vx"
    finally:
        conn.close()


def test_analyze_channel_structure_reports_progress_and_accepts_custom_channels(tmp_path: Path):
    conn, analysis = create_analysis_with_dxd_files(tmp_path)
    progress = []
    try:
        result = analyze_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            preset_name="custom",
            min_frequency=0.5,
            target_channels=["vehicle.vx", "vehicle.yaw_rate"],
            progress_callback=progress.append,
            reader_factory=fake_reader_factory,
        )
        assert result["total_files"] == 2
        assert result["ok_files"] == 2
        assert result["inventory_channel_count"] == 5
        assert progress[0]["phase"] == "initializing"
        assert progress[-1]["status"] == "finished"
    finally:
        conn.close()


def test_analyze_channel_structure_can_be_cancelled(tmp_path: Path):
    conn, analysis = create_analysis_with_dxd_files(tmp_path)
    calls = {"count": 0}

    def should_cancel() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    try:
        result = analyze_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            preset_name="minimum",
            should_cancel=should_cancel,
            reader_factory=fake_reader_factory,
        )
        assert result["status"] == "cancelled"
        assert result["processed_files"] == 1
        assert list_channel_inventory(conn, analysis["analysis_id"]) == []
        assert get_channel_structure(conn, analysis["analysis_id"]) is None
    finally:
        conn.close()


def test_save_validated_structure_generates_missing_channel_anomalies(tmp_path: Path):
    conn, analysis = create_analysis_with_dxd_files(tmp_path)
    try:
        analyze_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            preset_name="inventory",
            reader_factory=fake_reader_factory,
        )
        result = save_validated_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            selected_channels=["vehicle.vx", "gps.latitude"],
        )
        assert result["anomaly_count"] == 1
        structure = get_validated_channel_structure(conn, analysis["analysis_id"])
        assert structure["selected_channels"] == ["vehicle.vx", "gps.latitude"]
        anomaly_files = list_channel_anomaly_files(conn, analysis["analysis_id"])
        assert anomaly_files[0]["source_dxd_name"] == "b.dxd"
        anomalies = list_channel_anomalies(conn, analysis["analysis_id"], file_id=anomaly_files[0]["file_id"])
        assert anomalies[0]["channel"] == "gps.latitude"
        assert anomalies[0]["details"] == "canal récurrent sélectionné absent de ce fichier"
    finally:
        conn.close()


def test_inventory_deduplicates_channels_with_same_canonical_name(tmp_path: Path):
    conn, analysis = create_analysis_with_dxd_files(tmp_path)

    def duplicate_reader_factory(path: Path) -> FakeReader:
        return FakeReader(
            [
                FakeChannel("VelX", "km/h"),
                FakeChannel("vehicle.vx"),
            ]
        )

    try:
        result = analyze_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            preset_name="inventory",
            reader_factory=duplicate_reader_factory,
        )
        assert result["status"] == "finished"
        inventory = list_channel_inventory(conn, analysis["analysis_id"])
        vx_rows = [row for row in inventory if row["canonical_name"] == "vehicle.vx"]
        assert len(vx_rows) == 2
        assert vx_rows[0]["metadata"]["source_aliases"] == ["vehicle.vx"]
    finally:
        conn.close()


def test_analyze_channel_structure_can_limit_file_count(tmp_path: Path):
    conn, analysis = create_analysis_with_dxd_files(tmp_path)
    try:
        result = analyze_channel_structure(
            conn,
            analysis_id=analysis["analysis_id"],
            preset_name="inventory",
            max_files=1,
            reader_factory=fake_reader_factory,
        )
        assert result["total_files"] == 1
        inventory = list_channel_inventory(conn, analysis["analysis_id"])
        assert {row["metadata"]["source_dxd_name"] for row in inventory} == {"a.dxd"}
    finally:
        conn.close()
