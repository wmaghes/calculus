"""python -m cp_ingest [--sample N] | --reindex"""

import argparse

from app import config, db, embeddings

from .bulk import BulkClient
from .pipeline import Ingest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int)
    ap.add_argument("--reindex", action="store_true", help="re-chunk and re-embed stored opinions (no network)")
    a = ap.parse_args()
    s = config.load()
    conn = db.connect(s.database_url)
    db.migrate(conn)
    ing = Ingest(conn, BulkClient(s.bulk_base, audit=lambda *x, **k: db.audit(conn, *x, **k)), embeddings.from_settings(s))
    if a.reindex:
        print(ing.reindex())
    else:
        ing.run(a.sample or s.sample_size)


if __name__ == "__main__":
    main()
