from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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
    LOG_LEVEL: str = "INFO"
    METRICS_ENABLED: bool = True
    METRICS_TOKEN: str = ""
    AGENT_REQUIRE_SIGNATURE: bool = False
    AGENT_SIGNATURE_MAX_SKEW: int = 300
    SCHEDULER_LOCK_ENABLED: bool = True
    SCHEDULER_LOCK_TTL_SECONDS: int = 600
    # 只读服务器发现（默认关闭；仅允许扫描白名单 CIDR，不持有凭据、不远程安装）
    DISCOVERY_ENABLED: bool = False
    DISCOVERY_ALLOWED_CIDRS: list[str] = []
    DISCOVERY_MAX_HOSTS: int = 256
    DISCOVERY_SSH_PORT: int = 22
    DISCOVERY_TIMEOUT_SECONDS: float = 0.5
    DISCOVERY_CONCURRENCY: int = 32
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "ops-monitor-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    AGENT_STATUS_REFRESH_SECONDS: int = 30
    ALERT_EVALUATE_INTERVAL_SECONDS: int = 10
    METRIC_RETENTION_DAYS: int = 7
    METRIC_AGG_RETENTION_DAYS: int = 180
    METRIC_CLEANUP_ENABLED: bool = True
    TASK_RETENTION_DAYS: int = 30
    TASK_CLEANUP_ENABLED: bool = True
    # Agent 安装包来源目录（容器内挂载；为空时自动定位仓库根）
    AGENT_BUNDLE_DIR: str = ""

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"


# 全局单例实例, 项目各处导入settings使用
settings = Settings()
