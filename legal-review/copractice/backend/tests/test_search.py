import json

import pytest
from fastapi.testclient import TestClient

from app.embeddings import DevHashEmbedder
from app.search import Filters, rrf, search, snippet

EMB = DevHashEmbedder()
DOCS = [  # SYNTHETIC FIXTURE opinions
    ("FIXTURE Noncompete v. Employer", "ohio", "2015-01-01",
     "The covenant not to compete was unreasonable because its five-year duration exceeded any legitimate business interest of the employer."),
    ("FIXTURE Carrier v. Shipper", "ca6", "2018-06-01",
     "Under the Carmack Amendment a motor carrier is liable for actual loss or injury to property it transports in interstate commerce."),
    ("FIXTURE Tenant v. Landlord", "ohioctapp", "2012-02-02",
     "The landlord breached the implied warranty of habitability by failing to repair the heating system during winter."),
    ("FIXTURE Trade Secret Co. v. Former Employee", "ohioctapp", "2019-09-09",
     "Customer lists may qualify as trade secrets when the employer takes reasonable measures to keep them confidential."),
]


@pytest.fixture(scope="module")
def seeded(conn):
    for t in ("chunks", "opinion_texts", "opinions"):
        conn.execute(f"DELETE FROM {t}")
    for cid, name in (("ohio", "Supreme Court of Ohio"), ("ohioctapp", "Ohio Court of Appeals"), ("ca6", "Sixth Circuit")):
        conn.execute("INSERT INTO courts VALUES (%s,%s,'x') ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name", (cid, name))
    for i, (name, court, date, text) in enumerate(DOCS, start=1):
        oid = conn.execute(
            "INSERT INTO opinions (source, cluster_id, case_name, citation, court_id, date_filed, source_url, text_sha256, text_chars) "
            "VALUES ('fixture', %s, %s, %s, %s, %s, %s, 'x', %s) RETURNING id",
            (9000 + i, name, f"{i} Fixture Rep. {i}", court, date, f"https://www.courtlistener.com/opinion/{9000 + i}/x/", len(text))).fetchone()[0]
        conn.execute("INSERT INTO opinion_texts VALUES (%s, %s)", (oid, text))
        conn.execute("INSERT INTO chunks (opinion_id, position, char_start, char_end, text, embedding, embed_model) VALUES (%s,0,0,%s,%s,%s,%s)",
                     (oid, len(text), text, EMB.embed_documents([text])[0], EMB.name))
    return conn


def test_one_result_per_opinion(seeded):
    # Found on the live index: one long opinion filled 6 of 10 results.
    oid = seeded.execute("SELECT id FROM opinions WHERE case_name LIKE 'FIXTURE Carrier%'").fetchone()[0]
    extra = "The carrier is liable under the Carmack Amendment for cargo loss in interstate shipment. "
    ids = []
    for pos in (1, 2, 3):
        ids.append(seeded.execute(
            "INSERT INTO chunks (opinion_id, position, char_start, char_end, text, embedding, embed_model) "
            "VALUES (%s,%s,0,%s,%s,%s,%s) RETURNING id",
            (oid, pos, len(extra), extra, EMB.embed_documents([extra])[0], EMB.name)).fetchone()[0])
    try:
        out = search(seeded, EMB, "carrier liable for cargo loss in interstate shipment", 3)
        oids = [r["opinion_id"] for r in out["results"]]
        assert len(oids) == len(set(oids)) and oids[0] == oid
        top = out["results"][0]
        assert len(top["other_matching_chunk_ids"]) == 3 and top["chunk_id"] not in top["other_matching_chunk_ids"]
    finally:
        seeded.execute("DELETE FROM chunks WHERE id = ANY(%s)", (ids,))


def test_rrf_merges_and_rewards_agreement():
    fused = dict(rrf([[1, 2, 3], [3, 1, 4]]))
    assert fused[1] > fused[3] > fused[2] and 4 in fused
    assert rrf([[5], []]) == [(5, 1 / 61)]
    assert rrf([]) == []


def test_snippet_is_plain_window():
    text = "x " * 400 + "The covenant not to compete was void. " + "y " * 400
    s, off = snippet(text, "covenant to compete")
    assert "covenant" in s and len(s) <= 400 and text[off:off + len(s)] == s


def test_issue_statement_finds_relevant_opinion(seeded):
    out = search(seeded, EMB, "employee signed a five-year non-compete; is the covenant enforceable?", 3)
    assert out["results"][0]["case_name"] == "FIXTURE Noncompete v. Employer"
    r = out["results"][0]
    for k in ("case_name", "citation", "court", "date_filed", "snippet", "source_url", "chunk_id", "opinion_id"):
        assert r[k]
    assert r["fulltext_rank"] == 1


def test_or_semantics_and_no_match(seeded):
    out = search(seeded, EMB, "carrier liability for lost cargo in interstate shipment", 5)
    assert out["results"][0]["case_name"] == "FIXTURE Carrier v. Shipper"
    none = search(seeded, EMB, "zzzz qqqq", 5)
    assert none["fulltext_candidates"] == 0      # vector list still returns nearest neighbours


def test_filters(seeded):
    out = search(seeded, EMB, "employer employee covenant trade secret", 10, Filters(courts=["ohioctapp"]))
    assert out["results"] and all(r["court_id"] == "ohioctapp" for r in out["results"])
    out = search(seeded, EMB, "employer", 10, Filters(date_from="2016-01-01"))
    assert all(r["date_filed"] >= "2016-01-01" for r in out["results"])


def test_hostile_query_strings_are_just_text(seeded):
    for q in ["'; DROP TABLE opinions; --", "covenant & | ! :*", "a" * 1999, "<script>alert(1)</script> covenant"]:
        search(seeded, EMB, q, 3)
    assert seeded.execute("SELECT count(*) FROM opinions").fetchone()[0] == 4


@pytest.fixture
def client(seeded, db_url, monkeypatch):
    import app.main as m
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("EMBED_BACKEND", "dev-hash")
    m._state.cache_clear()
    yield TestClient(m.app)
    m._state.cache_clear()


def test_search_endpoint_contract(client, seeded):
    r = client.post("/search", json={"query": "Is a five-year covenant not to compete enforceable?", "top_k": 2})
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 2 and body["disclaimer"] == "Research aid for attorneys, not legal advice."
    assert body["embedder"].startswith("dev-hash") and "citator" in body["good_law_notice"]
    top = body["results"][0]
    assert top["case_name"] == "FIXTURE Noncompete v. Employer" and top["source_url"].startswith("https://www.courtlistener.com/opinion/")
    op = client.get(f"/opinions/{top['opinion_id']}").json()
    assert op["text"][top["snippet_start"]:top["snippet_end"]] == top["snippet"]   # click-through offsets are exact


def test_validation(client):
    assert client.post("/search", json={"query": "ab"}).status_code == 422
    assert client.post("/search", json={"query": "x" * 2001}).status_code == 422
    assert client.post("/search", json={"query": "valid query", "top_k": 500}).status_code == 422
    assert client.post("/search", json={"query": "valid query", "date_from": "2020/01/01"}).status_code == 422
    assert client.get("/opinions/999999").status_code == 404


def test_search_audit_has_no_query_text(client, seeded):
    client.post("/search", json={"query": "secret client strategy phrase xylophone"})
    rows = seeded.execute("SELECT detail FROM audit_log WHERE action='search'").fetchall()
    assert rows and all("xylophone" not in json.dumps(r[0]) for r in rows)
