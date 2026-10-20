from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="heatsense-api", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    database_url: str = Field(
        default="postgresql+psycopg://heatsense:change_me@localhost:5432/heatsense",
        validation_alias="DATABASE_URL",
    )
    cors_origins: str = Field(
        default="http://localhost:5173", validation_alias="CORS_ORIGINS"
    )
    jwt_secret_key: str = Field(
        default="heatsense_dev_secret_key_change_in_production_32bytes",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    auth_rate_limit_max_attempts: int = Field(
        default=5, ge=1, le=1000, validation_alias="AUTH_RATE_LIMIT_MAX_ATTEMPTS"
    )
    auth_rate_limit_window_seconds: int = Field(
        default=60, ge=1, le=86400, validation_alias="AUTH_RATE_LIMIT_WINDOW_SECONDS"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.app_env.lower() == "production":
            # 1. Reject default or weak development JWT secret
            default_dev_secrets = {
                "heatsense_dev_secret_key_change_in_production_32bytes",
                "secret",
                "changeme",
                "change_me",
            }
            if (
                self.jwt_secret_key in default_dev_secrets
                or "dev" in self.jwt_secret_key.lower()
                or len(self.jwt_secret_key) < 32
            ):
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: In production mode (APP_ENV=production), "
                    "JWT_SECRET_KEY must be a cryptographically secure string of at least 32 characters, "
                    "and cannot use development default or placeholder values."
                )

            # 2. Reject default database placeholder or development credentials
            if "change_me" in self.database_url or "heatsense_dev" in self.database_url:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: In production mode (APP_ENV=production), "
                    "DATABASE_URL cannot contain development credentials ('change_me' or 'heatsense_dev')."
                )

            # 3. Reject wildcard CORS origins
            if "*" in self.cors_origin_list:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: In production mode (APP_ENV=production), "
                    "CORS_ORIGINS cannot contain wildcard '*' when credentials are enabled."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
