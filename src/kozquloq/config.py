from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KOZQULOQ_")

    dataroot: Path = Path("data/nuscenes")
    version: str = "v1.0-mini"
    db_path: Path = Path("data/kozquloq.duckdb")
    viz_dir: Path = Path("viz_out")

    lidar_horizon_m: float = 80.0  # depth normalization for overlays
