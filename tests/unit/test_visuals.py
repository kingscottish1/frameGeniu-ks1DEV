from app.services.visuals import is_junk_query, sanitize_query, visual_queries


def test_rejects_month_portrait():
    assert is_junk_query("January portrait")
    assert sanitize_query("January portrait", "Black Dahlia") is None


def test_keeps_topic_queries():
    qs = visual_queries("Black Dahlia", extra=["January portrait", "Elizabeth Short", "dogs"], template="true-crime")
    assert qs
    assert all("dahlia" in q.lower() or "elizabeth" in q.lower() for q in qs)
    assert not any("january" in q.lower() and "portrait" in q.lower() for q in qs)
    assert not any(q.lower() == "dogs" for q in qs)
