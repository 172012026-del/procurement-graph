"""Neo4j fact mirror and retrieval; SQLite remains the source of truth."""
from __future__ import annotations

import hashlib
from .config import settings
from .database import rows


class GraphUnavailable(RuntimeError):
    pass


def session():
    from .neo4j_sync import _driver_instance
    if not settings.neo4j_uri:
        raise GraphUnavailable('Neo4j未配置')
    return _driver_instance().session(database=settings.neo4j_database)


def source_versions(dataset_id: str) -> dict[str, str]:
    versions = {row['notice_uuid']:hashlib.sha256(row['result_json'].encode()).hexdigest()
                for row in rows('SELECT notice_uuid,result_json FROM notices WHERE dataset_id=?', (dataset_id,))}
    sql_notices = {row['notice_uuid'] for row in rows('SELECT DISTINCT notice_uuid FROM projects WHERE dataset_id=?', (dataset_id,))}
    if sql_notices - versions.keys():
        raise GraphUnavailable('旧数据缺少公告快照，请重新导入后同步图数据库')
    return versions


def prune_dataset(dataset_id: str):
    active = list(source_versions(dataset_id))
    with session() as connection:
        def transaction(tx):
            tx.run('''MATCH (p:ProjectV2 {dataset:$dataset}) WHERE NOT p.notice_uuid IN $active
                OPTIONAL MATCH (p)-[:CONTAINS]->(i:ItemV2)
                OPTIONAL MATCH (b:BidV2)-[:FOR_PROJECT]->(p) DETACH DELETE i,b,p''', dataset=dataset_id,active=active).consume()
            tx.run('MATCH (m:MirrorV2 {dataset:$dataset}) WHERE NOT m.notice_uuid IN $active DELETE m', dataset=dataset_id,active=active).consume()
        connection.execute_write(transaction)


def ensure_schema():
    definitions = {
        'ProjectV2': '(n.dataset, n.notice_uuid, n.lot)', 'ItemV2': '(n.dataset, n.sql_id)',
        'BidV2': '(n.dataset, n.sql_id)', 'PurchaserV2': '(n.dataset, n.name)',
        'SupplierV2': '(n.dataset, n.name)', 'BrandV2': '(n.dataset, n.name)',
        'MirrorV2': '(n.dataset, n.notice_uuid)',
    }
    with session() as connection:
        for label, fields in definitions.items():
            connection.run(f'CREATE CONSTRAINT {label.lower()}_identity IF NOT EXISTS FOR (n:{label}) REQUIRE {fields} IS UNIQUE').consume()


def sync_notice(dataset_id: str, notice_uuid: str) -> bool:
    if not settings.neo4j_uri:
        return False
    packages = rows("SELECT * FROM projects WHERE dataset_id=? AND notice_uuid=? AND processing_status<>'fallback'", (dataset_id, notice_uuid))
    ids = {row['id'] for row in packages}
    bids = [row for row in rows('SELECT b.* FROM bids b JOIN projects p ON p.id=b.project_id WHERE p.dataset_id=? AND p.notice_uuid=?', (dataset_id, notice_uuid)) if row['project_id'] in ids]
    items = [row for row in rows('SELECT i.* FROM items i JOIN projects p ON p.id=i.project_id WHERE p.dataset_id=? AND p.notice_uuid=?', (dataset_id, notice_uuid)) if row['project_id'] in ids]
    fingerprint = source_versions(dataset_id).get(notice_uuid, '')
    def transaction(tx):
        tx.run('''MATCH (p:ProjectV2 {dataset:$dataset,notice_uuid:$notice})
            OPTIONAL MATCH (p)-[:CONTAINS]->(i:ItemV2)
            OPTIONAL MATCH (b:BidV2)-[:FOR_PROJECT]->(p)
            DETACH DELETE i,b,p''', dataset=dataset_id, notice=notice_uuid).consume()
        tx.run('''UNWIND $packages AS row
            MERGE (p:ProjectV2 {dataset:$dataset,notice_uuid:$notice,lot:row.lot_key})
            SET p += row, p.sql_id=row.id
            WITH p,row WHERE row.purchaser<>''
            MERGE (u:PurchaserV2 {dataset:$dataset,name:row.purchaser}) MERGE (u)-[:PURCHASES]->(p)''',
            packages=packages,dataset=dataset_id,notice=notice_uuid).consume()
        tx.run('''UNWIND $bids AS row MATCH (p:ProjectV2 {dataset:$dataset,sql_id:row.project_id})
            MERGE (b:BidV2 {dataset:$dataset,sql_id:row.id}) SET b += row
            MERGE (s:SupplierV2 {dataset:$dataset,name:row.bidder})
            MERGE (s)-[:SUBMITTED]->(b) MERGE (b)-[:FOR_PROJECT]->(p)''', bids=bids,dataset=dataset_id).consume()
        tx.run('''UNWIND $items AS row MATCH (p:ProjectV2 {dataset:$dataset,sql_id:row.project_id})
            MERGE (i:ItemV2 {dataset:$dataset,sql_id:row.id}) SET i += row MERGE (p)-[:CONTAINS]->(i)
            WITH i,row WHERE row.brand<>''
            MERGE (b:BrandV2 {dataset:$dataset,name:row.brand}) MERGE (i)-[:BRAND]->(b)''', items=items,dataset=dataset_id).consume()
        tx.run('''MERGE (m:MirrorV2 {dataset:$dataset,notice_uuid:$notice})
            SET m.fingerprint=$fingerprint, m.schema_version=3''', dataset=dataset_id,notice=notice_uuid,fingerprint=fingerprint).consume()
        # Nodes whose only project was replaced must not remain as phantom entities.
        for label in ['PurchaserV2', 'SupplierV2', 'BrandV2']:
            tx.run(f'MATCH (n:{label} {{dataset:$dataset}}) WHERE NOT (n)--() DELETE n', dataset=dataset_id).consume()
    with session() as connection:
        connection.execute_write(transaction)
    return True


def read_dataset(dataset_id: str, include_items: bool = False):
    expected = source_versions(dataset_id)
    try:
        with session() as connection:
            def transaction(tx):
                actual = {row['notice']:row['fingerprint'] for row in tx.run(
                    'MATCH (m:MirrorV2 {dataset:$dataset}) WHERE m.schema_version=3 RETURN m.notice_uuid AS notice,m.fingerprint AS fingerprint', dataset=dataset_id)}
                if actual != expected:
                    raise GraphUnavailable('Neo4j镜像缺失或过期，请执行同步后重试')
                packages = [dict(row['p']) for row in tx.run('MATCH (p:ProjectV2 {dataset:$dataset}) RETURN properties(p) AS p ORDER BY p.id', dataset=dataset_id)]
                bids = [dict(row['b']) for row in tx.run('MATCH (b:BidV2 {dataset:$dataset})-[:FOR_PROJECT]->(:ProjectV2) RETURN properties(b) AS b ORDER BY b.id', dataset=dataset_id)]
                items = [dict(row['i']) for row in tx.run('MATCH (:ProjectV2 {dataset:$dataset})-[:CONTAINS]->(i:ItemV2) RETURN properties(i) AS i ORDER BY i.id', dataset=dataset_id)] if include_items else []
                # Neo4j omits null properties; restore SQL-shaped records for the shared aggregation rules.
                for row in packages:
                    for key in ['awarded_amount', 'budget_amount', 'notice_awarded_amount']:
                        row.setdefault(key, None)
                for row in bids:
                    for key in ['bid_amount', 'score', 'rank']:
                        row.setdefault(key, None)
                for row in items:
                    for key in ['unit_price', 'quantity', 'total_price']:
                        row.setdefault(key, None)
                return {row['id']:row for row in packages}, bids, items
            return connection.execute_read(transaction)
    except GraphUnavailable:
        raise
    except Exception as error:
        raise GraphUnavailable('Neo4j连接或查询失败，请检查图服务与配置') from error
