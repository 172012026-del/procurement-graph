"""Synchronize a dataset and compare SQLite/Neo4j query results."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', default='official-reference')
    args = parser.parse_args()
    from app.config import settings
    from app import analytics, graph_store
    from app.database import init_db, rows
    from app.neo4j_sync import close_driver
    if not settings.neo4j_uri:
        parser.error('Configure NEO4J_URI/NEO4J_PASSWORD first; no synchronization performed')
    init_db()
    from app.seed import seed_reference
    seed_reference()
    notices = rows('SELECT notice_uuid FROM notices WHERE dataset_id=?', (args.dataset,))
    if not notices:
        parser.error('Dataset has no notices')
    graph_store.ensure_schema()
    graph_store.prune_dataset(args.dataset)
    try:
        for notice in notices:
            graph_store.sync_notice(args.dataset, notice['notice_uuid'])
        packages, bids, _ = graph_store.read_dataset(args.dataset, True)
        purchasers = sorted({row['purchaser'] for row in packages.values() if row['purchaser']})
        suppliers = sorted({row['bidder'] for row in bids if row['is_winner'] and row['eligible']})
        cases = [(analytics.purchaser_partners, (name, args.dataset)) for name in purchasers]
        cases += [(analytics.purchaser_bidders, (name, args.dataset)) for name in purchasers]
        cases += [(analytics.supplier_competitors, (name, args.dataset)) for name in suppliers]
        if len(suppliers) >= 2:
            cases += [(analytics.common_purchasers, (suppliers[:2], args.dataset)), (analytics.common_projects, (suppliers[:2], args.dataset))]
        import app.config as config
        original = config.settings
        try:
            for function, arguments in cases:
                config.settings = replace(original, relation_backend='sqlite')
                expected = function(*arguments)
                config.settings = replace(original, relation_backend='neo4j')
                actual = function(*arguments)
                if actual != expected:
                    raise RuntimeError('Graph/SQLite result mismatch: ' + function.__name__)
        finally:
            config.settings = original
        print(json.dumps({'synced_notices':len(notices),'packages':len(packages),'parity_cases':len(cases),'passed':True,'model_requests':0}))
    finally:
        close_driver()


if __name__ == '__main__':
    main()
