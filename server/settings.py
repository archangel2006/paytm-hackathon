import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "server/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "sqlite:///./saathi.db"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    UPLOAD_DIR: str = "./uploads"
    SCHEDULER_TICK_SECONDS: int = 5

    # Simulation defaults
    SIMULATION_DEFAULT_SEEDS: int = 30
    SIMULATION_DEFAULT_POPULATION: int = 300

    # Hero phone numbers
    HERO_PHONE_RAHUL: str = "+919000000001"
    HERO_PHONE_MEENA: str = "+919000000002"
    HERO_PHONE_SUNIL: str = "+919000000003"
    HERO_PHONE_FARIDA: str = "+919000000004"
    HERO_PHONE_VIKRAM: str = "+919000000005"
    HERO_PHONE_POOJA: str = "+919000000006"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = ServerSettings()

