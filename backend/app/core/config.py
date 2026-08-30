from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# 定位.env文件
_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8")

    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "ops_monitor"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 120
    CORS_ORIGINS: list[str] = ["*"]
    SEED_INIT_DATA: bool = True
    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_PASSWORD: str = "admin123456"
    OPERATION_LOG_ENABLED: bool = True

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"


# 全局单例实例, 项目各处导入settings使用
settings = Settings()
