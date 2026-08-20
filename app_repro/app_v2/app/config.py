from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
PROJECT_ROOT = REPO_ROOT
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv(REPO_ROOT / ".env")
load_dotenv(APP_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    db_path: Path
    acquisitions_dir: Path
    resampled_json_dir: Path
    model_artifacts_dir: Path


def get_settings() -> Settings:
    base_data_dir = Path(os.getenv("MAS_APP_V2_DATA_DIR", APP_ROOT / "data"))
    return Settings(
        db_path=Path(os.getenv("MAS_APP_V2_DB_PATH", APP_ROOT / "pipeline_v2.sqlite")),
        acquisitions_dir=Path(os.getenv("MAS_APP_V2_ACQUISITIONS_DIR", base_data_dir / "acquisitions")),
        resampled_json_dir=Path(os.getenv("MAS_APP_V2_RESAMPLED_JSON_DIR", base_data_dir / "resampled_json")),
        model_artifacts_dir=Path(os.getenv("MAS_APP_V2_MODEL_ARTIFACTS_DIR", base_data_dir / "model_artifacts")),
    )
