from __future__ import annotations

from typing import Any

from mas_essais.domain.dxd_schema import CHANNEL_SPECS, canonical_name_for, source_name_for


ANNOTATOR_DXD_CHANNELS = [
    "vehicle.vx",
    "vehicle.speed",
    "vehicle.ax",
    "vehicle.ay",
    "vehicle.yaw_rate",
    "gps.latitude",
    "gps.longitude",
    "WheelSteer_S1 (_)",
    "WheelSteer_S2 (_)",
    "WhlDirFl_D_Actl (-)",
    "WhlDirFr_D_Actl (-)",
]

ROLLOVER_DXD_CHANNELS = [
    "vehicle.vx",
    "vehicle.vy",
    "vehicle.ax",
    "vehicle.ay",
    "vehicle.roll_angle",
]

MINIMUM_DXD_CHANNELS = [
    "vehicle.vx",
    "vehicle.vy",
    "vehicle.speed",
    "vehicle.ax",
    "vehicle.ay",
    "vehicle.yaw_rate",
    "vehicle.roll_angle",
    "gps.latitude",
    "gps.longitude",
    "WheelSteer_S1 (_)",
    "WheelSteer_S2 (_)",
]

EXPLORATION_DXD_CHANNELS = [
    "vehicle.vx",
    "vehicle.vy",
    "vehicle.ax",
    "vehicle.ay",
    "WheelSteer_S1 (_)",
    "WheelSteer_S2 (_)",
]

APP_DEFAULT_DXD_CHANNELS = tuple(
    dict.fromkeys(
        [
            *(spec.canonical_name for spec in CHANNEL_SPECS),
            *ANNOTATOR_DXD_CHANNELS,
            *ROLLOVER_DXD_CHANNELS,
            *EXPLORATION_DXD_CHANNELS,
        ]
    )
)


def channel_presets() -> dict[str, dict[str, Any]]:
    return {
        "minimum": {
            "label": "Canaux minimum",
            "description": "Socle minimal pour exploration, annotation, retournement et detection d'anomalies.",
            "channels": MINIMUM_DXD_CHANNELS,
        },
        "app_default": {
            "label": "Defaut application",
            "description": "Canaux metier connus par l'application.",
            "channels": list(APP_DEFAULT_DXD_CHANNELS),
        },
        "annotator": {
            "label": "Annotateur",
            "description": "Signaux necessaires a l'annotation de segments.",
            "channels": ANNOTATOR_DXD_CHANNELS,
        },
        "rollover": {
            "label": "Retournement",
            "description": "Signaux necessaires a l'analyse retournement.",
            "channels": ROLLOVER_DXD_CHANNELS,
        },
        "exploration": {
            "label": "Exploration labels",
            "description": "Signaux utilises par l'exploration descriptive des segments.",
            "channels": EXPLORATION_DXD_CHANNELS,
        },
        "all_canonical": {
            "label": "Tous canaux canoniques",
            "description": "Tous les canaux declares dans le schema canonique.",
            "channels": [spec.canonical_name for spec in CHANNEL_SPECS],
        },
    }


def channels_for_preset(preset_name: str | None) -> list[str]:
    presets = channel_presets()
    key = str(preset_name or "app_default")
    channels = presets.get(key, presets["app_default"])["channels"]
    return list(dict.fromkeys(str(channel) for channel in channels if str(channel).strip()))


def channel_candidates(name: str) -> set[str]:
    source_name = source_name_for(name)
    canonical_name = canonical_name_for(name)
    return {name, source_name, canonical_name, canonical_name_for(source_name)}
