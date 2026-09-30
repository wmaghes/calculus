"""SYNTHETIC fixtures shaped like CourtListener bulk files. Every case here is
invented and marked FIXTURE; none is real law."""

import bz2
import csv
import io

import httpx

BASE = "https://bulk.fixture.example"


def pdf(lines: list[str]) -> bytes:
    """Minimal valid one-page text PDF."""
    body = "BT /F1 11 Tf 50 750 Td 14 TL " + " ".join(
        "(" + l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") '" for l in lines) + " ET"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length %d >>\nstream\n" % len(body) + body.encode("latin-1") + b"\nendstream"]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    return bytes(out)


def bz2csv(header, rows, streams: int = 1) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    data = buf.getvalue().encode()
    if streams == 1:
        return bz2.compress(data)
    cut = len(data) // 2
    return bz2.compress(data[:cut]) + bz2.compress(data[cut:])  # multi-stream file


PARA = ("The court held that the covenant not to compete was reasonable in duration and geographic scope, "
        "and that the employer had a legitimate business interest in protecting its customer relationships. ")
OPINIONS = {
    101: ["FIXTURE Freight Co. v. Example Cold Storage", "Supreme Court of Ohio (FIXTURE)"] + [PARA] * 30,
    102: ["FIXTURE Employee v. FIXTURE Employer", "Ohio Court of Appeals (FIXTURE)",
          "A carrier is liable for loss of temperature-sensitive cargo caused by refrigeration failure. " * 25],
    103: ["FIXTURE Sixth Circuit case", "negligence standard for motor carriers under the Carmack Amendment. " * 30],
    104: None,          # corrupted PDF
    105: ["short"],     # too little text
}


def files() -> dict[str, bytes]:
    f = {
        "bulk-data/courts-2026-09-30.csv.bz2": bz2csv(["id", "full_name"], [["ohio", "Supreme Court of Ohio"],
                                                                            ["ohioctapp", "Ohio Court of Appeals"],
                                                                            ["ca6", "Court of Appeals for the Sixth Circuit"],
                                                                            ["tex", "Texas Supreme Court"]]),
        "bulk-data/dockets-2026-09-30.csv.bz2": bz2csv(["id", "court_id", "docket_number"],
                                                       [[1, "ohio", "2019-001"], [2, "ohioctapp", "CA-22"], [3, "ca6", "21-3000"],
                                                        [4, "tex", "X"], [5, "ohio", "2019-002"], [6, "ohio", "2019-003"]], streams=2),
        "bulk-data/opinion-clusters-2026-09-30.csv.bz2": bz2csv(
            ["id", "case_name", "case_name_full", "date_filed", "judges", "docket_id", "precedential_status", "citation_count",
             "slug", "filepath_pdf_harvard", "blocked"],
            [[101, "FIXTURE Freight Co. v. Example Cold Storage", "", "2015-03-02", "Judge A", 1, "Published", 50, "fixture-freight", "harvard_pdf/101.pdf", "f"],
             [102, "FIXTURE Employee v. FIXTURE Employer", "", "2016-04-01", "", 2, "Published", 40, "fixture-employee", "harvard_pdf/102.pdf", "f"],
             [103, "FIXTURE Sixth Circuit case", "", "2017-05-05", "", 3, "Published", 30, "fixture-sixth", "harvard_pdf/103.pdf", "f"],
             [104, "FIXTURE Corrupt v. Pdf", "", "2014-01-01", "", 5, "Published", 20, "fixture-corrupt", "harvard_pdf/104.pdf", "f"],
             [105, "FIXTURE Short v. Text", "", "2014-01-01", "", 6, "Published", 10, "fixture-short", "harvard_pdf/105.pdf", "f"],
             [106, "FIXTURE Texas case", "", "2014-01-01", "", 4, "Published", 99, "tex", "harvard_pdf/106.pdf", "f"],
             [107, "FIXTURE No PDF", "", "2014-01-01", "", 1, "Published", 99, "nopdf", "", "f"]]),
        "bulk-data/citations-2026-09-30.csv.bz2": bz2csv(["cluster_id", "volume", "reporter", "page"],
                                                         [[101, 999, "Fixture Ohio St. 3d", 1], [101, 2015, "Ohio", 999],
                                                          [102, 998, "Fixture Ohio App. 3d", 2], [106, 1, "Tex", 1]]),
    }
    for cid, lines in OPINIONS.items():
        f[f"harvard_pdf/{cid}.pdf"] = b"%PDF-1.4 garbage" if lines is None else pdf(lines)
    return f


class Bulk:
    def __init__(self):
        self.files, self.requests, self.fail_on = files(), [], set()
        self.stall_once: dict[str, int] = {}   # path -> byte offset at which the first response dies

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        path = request.url.path.lstrip("/")
        if path == "" and "prefix" in request.url.params:
            pre = request.url.params["prefix"]
            keys = "".join(f"<Key>{k}</Key>" for k in self.files if k.startswith(pre))
            return httpx.Response(200, text=f"<ListBucketResult>{keys}</ListBucketResult>")
        if path in self.fail_on:
            raise httpx.ConnectError("simulated interruption")
        if path in self.files:
            data = self.files[path]
            rng = request.headers.get("range")
            if rng:
                start = int(rng.split("=")[1].rstrip("-"))
                return httpx.Response(206, content=data[start:])
            if path in self.stall_once:
                cut = self.stall_once.pop(path)

                def body():
                    yield data[:cut]
                    raise httpx.ReadTimeout("simulated stall")
                return httpx.Response(200, stream=_Stream(body()))
            return httpx.Response(200, content=data)
        return httpx.Response(404)


class _Stream(httpx.SyncByteStream):
    def __init__(self, gen):
        self._gen = gen

    def __iter__(self):
        yield from self._gen
