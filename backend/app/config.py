import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "OpenIntel-OSINT"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    # Lagringssökvägar för lokal körning
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    EVIDENCE_DIR: Path = DATA_DIR / "evidence"
    SNAPSHOTS_DIR: Path = DATA_DIR / "snapshots"
    EXPORT_DIR: Path = DATA_DIR / "exports"
    
    # Databas och externa tjänster
    DATABASE_URL: str = "sqlite:///./data/openintel.db"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "openintel_neo4j_pass"
    USE_NEO4J: bool = False
    
    # MinIO / S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "openintel_minio_admin"
    MINIO_SECRET_KEY: str = "openintel_minio_secret_key"
    MINIO_BUCKET: str = "openintel-evidence"
    USE_MINIO: bool = False
    
    # Säkerhet och ToS-efterlevnad
    JWT_SECRET: str = "openintel_super_secret_master_key_2026"
    JWT_ALGORITHM: str = "HS256"
    MAX_REQUESTS_PER_MINUTE: int = 60
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"]

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()

# Säkerställ att datakataloger finns
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
