import sqlalchemy as sa
from sqlalchemy.dialects import mysql as mysql_dialect
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.core.config import settings
from app.core.database import Base

EXPECTED_TABLES = {
    "sys_user",
    "sys_role",
    "sys_permission",
    "sys_user_role",
    "sys_role_permission",
    "ops_server",
    "ops_server_disk",
    "ops_server_network",
    "ops_agent_token",
    "ops_agent_heartbeat",
    "ops_server_service",
    "ops_server_container",
    "monitor_server_metric",
    "monitor_disk_metric",
    "monitor_network_metric",
    "monitor_container_metric",
    "monitor_process_snapshot",
    "alert_rule",
    "alert_event",
    "alert_event_log",
    "ops_task",
    "ops_task_target",
    "ops_task_execution",
    "ops_task_log",
    "sys_login_log",
    "sys_operation_log",
}


def test_all_tables_mapped():
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


def test_mapper_configuration():
    configure_mappers()


def test_ddl_compiles():
    dialect = mysql_dialect.dialect()
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]
        assert str(CreateTable(table).compile(dialect=dialect))


def test_columns_match_database():
    engine = sa.create_engine(settings.database_url)
    db_columns: dict[str, set[str]] = {}
    with engine.connect() as conn:
        result = conn.execute(
            sa.text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = :schema"
            ),
            {"schema": settings.DB_NAME},
        )
        for table_name, column_name in result:
            db_columns.setdefault(table_name, set()).add(column_name)

    assert EXPECTED_TABLES <= set(db_columns), f"数据库中缺少表: {EXPECTED_TABLES - set(db_columns)}"
    for table_name in EXPECTED_TABLES:
        model_cols = set(Base.metadata.tables[table_name].columns.keys())
        assert model_cols == db_columns[table_name], (
            f"{table_name} 列不一致: 模型={sorted(model_cols ^ db_columns[table_name])}"
        )
