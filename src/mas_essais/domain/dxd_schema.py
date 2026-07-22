from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


@dataclass(frozen=True)
class ChannelSpec:
    source_name: str
    canonical_name: str
    raw_unit: str
    unit: str
    scale: float = 1.0
    offset: float = 0.0
    frame: str | None = None

    def convert(self, values: Any) -> np.ndarray:
        arr = np.asarray(values, dtype=np.float64)
        return arr * self.scale + self.offset


CHANNEL_SPECS: tuple[ChannelSpec, ...] = (
    ChannelSpec("VelX (km/h)", "vehicle.vx", "km/h", "m/s", 1.0 / 3.6, frame="vehicle_body"),
    ChannelSpec("VelY (km/h)", "vehicle.vy", "km/h", "m/s", 1.0 / 3.6, frame="vehicle_body"),
    ChannelSpec("Vel (km/h)", "vehicle.speed", "km/h", "m/s", 1.0 / 3.6, frame="vehicle_body"),
    ChannelSpec("VehYaw_W_Actl (rad/s)", "vehicle.yaw_rate", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("VehPtch_W_Actl (rad/s)", "vehicle.pitch_rate", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("VehRol_W_Actl (rad/s)", "vehicle.roll_rate", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("Roll (_)", "vehicle.roll_angle", "deg", "deg", frame="vehicle_body"),
    ChannelSpec("VehLong_A_Actl (m/s^2)", "vehicle.ax", "m/s^2", "m/s^2", frame="vehicle_body"),
    ChannelSpec("VehLat_A_Actl (m/s^2)", "vehicle.ay", "m/s^2", "m/s^2", frame="vehicle_body"),
    ChannelSpec("VehVert_A_Actl (m/s^2)", "vehicle.az", "m/s^2", "m/s^2", frame="vehicle_body"),
    ChannelSpec("AccX_body (m/s_)", "imu.ax_body", "m/s^2", "m/s^2", frame="vehicle_body"),
    ChannelSpec("AccY_body (m/s_)", "imu.ay_body", "m/s^2", "m/s^2", frame="vehicle_body"),
    ChannelSpec("AccZ_body (m/s_)", "imu.az_body", "m/s^2", "m/s^2", frame="vehicle_body"),
    ChannelSpec("AngVelX_body (_/s)", "imu.wx_body", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("AngVelY_body (_/s)", "imu.wy_body", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("AngVelZ_body (_/s)", "imu.wz_body", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("Latitude (_)", "gps.latitude", "deg", "deg", frame="world"),
    ChannelSpec("Longitude (_)", "gps.longitude", "deg", "deg", frame="world"),
    ChannelSpec("Height (m)", "gps.altitude", "m", "m", frame="world"),
    ChannelSpec("Distance (m)", "gps.distance", "m", "m", frame="world"),
    ChannelSpec("Radius (m)", "gps.radius", "m", "m", frame="world"),
    ChannelSpec("Track (_)", "gps.track", "unknown", "rad", frame="world"),
    ChannelSpec("TimeOfWeek (ms)", "gps.time_of_week", "ms", "s", 0.001),
    ChannelSpec("Timestamp (-)", "gps.timestamp", "unknown", "s"),
    ChannelSpec("WhlFl_W_Meas (rad/s)", "wheel.fl.omega", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("WhlFr_W_Meas (rad/s)", "wheel.fr.omega", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("WhlRl_W_Meas (rad/s)", "wheel.rl.omega", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("WhlRr_W_Meas (rad/s)", "wheel.rr.omega", "rad/s", "rad/s", frame="vehicle_body"),
    ChannelSpec("LF_Fx_1 (N)", "wheel.fl.fx", "N", "N", frame="wheel"),
    ChannelSpec("LF_Fy_1 (N)", "wheel.fl.fy", "N", "N", frame="wheel"),
    ChannelSpec("LF_Fz_1 (N)", "wheel.fl.fz", "N", "N", frame="wheel"),
    ChannelSpec("RF_Fx_2 (N)", "wheel.fr.fx", "N", "N", frame="wheel"),
    ChannelSpec("RF_Fy_2 (N)", "wheel.fr.fy", "N", "N", frame="wheel"),
    ChannelSpec("RF_Fz_2 (N)", "wheel.fr.fz", "N", "N", frame="wheel"),
    ChannelSpec("LR_Fx_3 (N)", "wheel.rl.fx", "N", "N", frame="wheel"),
    ChannelSpec("LR_Fy_3 (N)", "wheel.rl.fy", "N", "N", frame="wheel"),
    ChannelSpec("LR_Fz_3 (N)", "wheel.rl.fz", "N", "N", frame="wheel"),
    ChannelSpec("RR_Fx_4 (N)", "wheel.rr.fx", "N", "N", frame="wheel"),
    ChannelSpec("RR_Fy_4 (N)", "wheel.rr.fy", "N", "N", frame="wheel"),
    ChannelSpec("RR_Fz_4 (N)", "wheel.rr.fz", "N", "N", frame="wheel"),
)

SPEC_BY_SOURCE = {spec.source_name: spec for spec in CHANNEL_SPECS}
SOURCE_BY_CANONICAL = {spec.canonical_name: spec.source_name for spec in CHANNEL_SPECS}
CANONICAL_DISPLAY_ORDER = tuple(dict.fromkeys(spec.canonical_name for spec in CHANNEL_SPECS))
CANONICAL_DISPLAY_RANK = {name: idx for idx, name in enumerate(CANONICAL_DISPLAY_ORDER)}


def channel_sort_key(channel_name: str) -> tuple[int, int, str]:
    if channel_name in CANONICAL_DISPLAY_RANK:
        return (0, CANONICAL_DISPLAY_RANK[channel_name], channel_name)
    if channel_name.startswith(("Resid_", "Score_")):
        return (1, 0, channel_name)
    return (2, 0, channel_name)


def to_json_list(values: Any) -> list[float | None]:
    out: list[float | None] = []
    for value in np.asarray(values, dtype=np.float64):
        out.append(float(value) if np.isfinite(value) else None)
    return out


def canonical_name_for(source_name: str) -> str:
    return SPEC_BY_SOURCE.get(source_name, ChannelSpec(source_name, source_name, "", "")).canonical_name


def source_name_for(channel_name: str) -> str:
    return SOURCE_BY_CANONICAL.get(channel_name, channel_name)


def convert_channel_values(channel_name: str, values: Any) -> np.ndarray:
    spec = SPEC_BY_SOURCE.get(channel_name)
    if spec is None:
        return np.asarray(values, dtype=np.float64)
    return spec.convert(values)


def channel_values_are_already_normalized(
    channel_name: str,
    payload: dict[str, Any],
    canonical_name: str,
    spec_source_name: str,
) -> bool:
    spec = SPEC_BY_SOURCE.get(spec_source_name)
    if spec is None:
        return False
    if channel_name != canonical_name and payload.get("canonical_name") != canonical_name:
        return False
    return payload.get("unit") == spec.unit


def channel_metadata(channel_name: str, source_name: str | None = None) -> dict[str, Any]:
    lookup_name = source_name or channel_name
    spec = SPEC_BY_SOURCE.get(lookup_name)
    if spec is None:
        return {
            "canonical_name": channel_name,
            "source_name": source_name or channel_name,
            "raw_unit": None,
            "unit": None,
            "scale_applied": 1.0,
            "offset_applied": 0.0,
            "frame": None,
        }
    return {
        "canonical_name": spec.canonical_name,
        "source_name": spec.source_name,
        "raw_unit": spec.raw_unit,
        "unit": spec.unit,
        "scale_applied": spec.scale,
        "offset_applied": spec.offset,
        "frame": spec.frame,
    }


def _map_key_dict(data: dict[str, Any], key_mapper: Callable[[str], str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        mapped = key_mapper(key)
        out[mapped] = value
    return out


def _convert_feature_value(feature_name: str, value: Any, scale: float) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [_convert_feature_value(feature_name, item, scale) for item in value]
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    if not np.isfinite(numeric):
        return None

    if feature_name in {"energy"}:
        return numeric * scale * scale
    if feature_name in {
        "mean",
        "std",
        "min",
        "max",
        "rms",
        "median",
        "q25",
        "q75",
        "iqr",
        "mean_abs",
        "range",
        "slope",
        "diff_std",
        "max_abs_diff",
    }:
        return numeric * scale
    return numeric


def _convert_feature_payload(source_name: str, payload: Any) -> Any:
    spec = SPEC_BY_SOURCE.get(source_name)
    if spec is None or spec.scale == 1.0:
        return payload
    if not isinstance(payload, dict):
        return payload
    return {
        feature_name: _convert_feature_value(feature_name, value, spec.scale)
        for feature_name, value in payload.items()
    }


def normalize_raw_json_schema(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical-channel view of a DXD export, preserving legacy metadata."""
    data = raw

    timebase = data.setdefault("timebase", {})
    if "time" not in timebase and "time" in data:
        timebase["time"] = data.get("time")

    pipeline = data.setdefault("pipeline", {})
    if "target_hz" not in pipeline and "target_hz" in data:
        pipeline["target_hz"] = data.get("target_hz")

    channels_block = data.setdefault("channels", {})
    raw_resampled = channels_block.get("resampled")
    if raw_resampled is None:
        raw_resampled = channels_block if isinstance(channels_block, dict) else {}

    canonical_resampled: dict[str, Any] = {}
    source_to_canonical: dict[str, str] = {}
    canonical_to_source: dict[str, str] = {}

    for name, payload in raw_resampled.items():
        if not isinstance(payload, dict) or "values" not in payload:
            continue
        payload_source_name = payload.get("source_name")
        source_name = payload_source_name
        if source_name == "derived":
            source_name = name
        source_name = source_name or source_name_for(name)
        spec_source_name = name if name in SPEC_BY_SOURCE else source_name
        canonical_name = canonical_name_for(name)
        if canonical_name == name:
            canonical_name = canonical_name_for(spec_source_name)

        values = payload.get("values", [])
        if channel_values_are_already_normalized(name, payload, canonical_name, spec_source_name):
            values = to_json_list(values)
        else:
            values = to_json_list(convert_channel_values(spec_source_name, values))
        mapped_payload = dict(payload)
        mapped_payload.update(channel_metadata(canonical_name, spec_source_name))
        mapped_payload["source_name"] = source_name
        mapped_payload["values"] = values
        canonical_resampled[canonical_name] = mapped_payload
        source_to_canonical[name] = canonical_name
        canonical_to_source[canonical_name] = source_name

    channels_block["resampled"] = canonical_resampled
    channels_block["source_to_canonical"] = source_to_canonical
    channels_block["canonical_to_source"] = canonical_to_source

    features = data.get("features", {})
    global_features = features.get("global", {})
    if isinstance(global_features.get("by_channel"), dict):
        global_features["by_channel"] = {
            source_to_canonical.get(key, canonical_name_for(key)): _convert_feature_payload(key, value)
            for key, value in global_features["by_channel"].items()
        }
    if isinstance(global_features.get("multivariate"), dict):
        global_features["multivariate"] = _map_key_dict(
            global_features["multivariate"],
            lambda key: " :: ".join(
                source_to_canonical.get(part, canonical_name_for(part))
                for part in key.split("__vs__")
            ) if "__vs__" in key else key,
        )

    sliding = features.get("sliding", {})
    if isinstance(sliding.get("by_channel"), dict):
        sliding["by_channel"] = {
            source_to_canonical.get(key, canonical_name_for(key)): _convert_feature_payload(key, value)
            for key, value in sliding["by_channel"].items()
        }

    return data


def normalize_feature_schema(raw: dict[str, Any]) -> dict[str, Any]:
    data = raw
    features = data.get("features", {})
    global_features = features.get("global", {})
    if isinstance(global_features.get("by_channel"), dict):
        global_features["by_channel"] = {
            canonical_name_for(key): _convert_feature_payload(key, value)
            for key, value in global_features["by_channel"].items()
        }

    sliding = features.get("sliding", {})
    if isinstance(sliding.get("by_channel"), dict):
        sliding["by_channel"] = {
            canonical_name_for(key): _convert_feature_payload(key, value)
            for key, value in sliding["by_channel"].items()
        }
    return data


def get_time_values(raw: dict[str, Any]) -> list[Any]:
    return raw.get("timebase", {}).get("time") or raw.get("time") or []


def get_resampled_channels(raw: dict[str, Any]) -> dict[str, Any]:
    channels = raw.get("channels", {})
    return channels.get("resampled", channels) if isinstance(channels, dict) else {}
