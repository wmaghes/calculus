from lexreview.chunking import chunk_page


def test_chunks_cover_text_and_stay_in_bounds():
    text = " ".join(f"word{i}" for i in range(2000))
    spans = chunk_page(text, size=500, overlap=100)
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    for (s1, e1), (s2, _) in zip(spans, spans[1:]):
        assert s2 < e1  # overlap, no gaps
        assert s2 == 0 or text[s2 - 1] == " "  # starts on a word boundary
    assert all(0 <= s < e <= len(text) for s, e in spans)


def test_empty_page_has_no_chunks():
    assert chunk_page("") == [] and chunk_page("   \n ") == []


def test_unbroken_text_terminates():
    spans = chunk_page("x" * 5000, size=1000, overlap=200)
    assert spans[-1][1] == 5000
