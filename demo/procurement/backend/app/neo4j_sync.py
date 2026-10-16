from __future__ import annotations

from threading import Lock
from .config import settings
from .database import one

_driver = None
_lock = Lock()


def _driver_instance():
    global _driver
    with _lock:
        if _driver is None:
            from neo4j import GraphDatabase
            _driver = GraphDatabase.driver(settings.neo4j_uri,auth=(settings.neo4j_user,settings.neo4j_password),
                connection_timeout=10,max_connection_pool_size=2,connection_acquisition_timeout=15)
        return _driver


def close_driver():
    global _driver
    with _lock:
        if _driver is not None:
            _driver.close()
            _driver = None


def sync_notice(dataset_id: str, notice_uuid: str) -> bool:
    from .graph_store import ensure_schema, sync_notice as synchronize
    if settings.neo4j_uri:
        ensure_schema()
    return synchronize(dataset_id, notice_uuid)


def sync_project(project_id: int) -> bool:
    project = one('SELECT dataset_id,notice_uuid FROM projects WHERE id=?',(project_id,))
    return sync_notice(project['dataset_id'],project['notice_uuid']) if project else False
