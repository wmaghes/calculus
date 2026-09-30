"""python -m cp_ingest [--sample N]"""

import argparse

from app import config, db, embeddings

from .bulk import BulkClient
from .pipeline import Ingest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int)
    a = ap.parse_args()
    s = config.load()
    conn = db.connect(s.database_url)
    db.migrate(conn)
    ing = Ingest(conn, BulkClient(s.bulk_base, audit=lambda *x, **k: db.audit(conn, *x, **k)), embeddings.from_settings(s))
    ing.run(a.sample or s.sample_size)


if __name__ == "__main__":
    main()
