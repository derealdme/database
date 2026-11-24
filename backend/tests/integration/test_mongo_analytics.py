"""$setWindowFields, $merge and $lookup pipelines, plus the note ticker check (MongoDB)."""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.db import mongo
from app.services import news, notes


pytestmark = pytest.mark.integration

TEST_TICKER = "ZZQS"      # never a real listing; used only for news fixtures
TEST_USER_ID = 999002


def _article(when: datetime, score: float) -> dict:
    label = "positive" if score > 0.05 else "negative" if score < -0.05 else "neutral"
    return {"ticker": TEST_TICKER, "headline": f"test headline {when:%Y-%m-%d}",
            "published_at": when, "source": "test",
            "sentiment": {"score": float(score), "label": label}}


@pytest.fixture(autouse=True)
def _clean():
    mongo.ensure_collections()
    db = mongo.get_db()

    def wipe():
        db[mongo.NEWS].delete_many({"ticker": TEST_TICKER})
        db[mongo.SENTIMENT_MONTHLY].delete_many({"ticker": TEST_TICKER})
        db[mongo.NOTES].delete_many({"user_id": TEST_USER_ID})

    wipe()
    yield
    wipe()


def test_timeline_rolling_average_and_change():
    db = mongo.get_db()
    latest = news._latest_timestamp() or datetime(2024, 6, 30, 12)
    # Four articles exactly a week apart -> four consecutive weekly buckets,
    # oldest first. None is later than the existing latest article, so the
    # timeline's window anchor does not move.
    scores = [0.1, 0.2, 0.3, 0.4]
    db[mongo.NEWS].insert_many(
        [_article(latest - timedelta(days=7 * (3 - i)), s) for i, s in enumerate(scores)])

    rows = news.sentiment_timeline(TEST_TICKER, days=60, granularity="week", window=2)

    assert [r["avg_sentiment"] for r in rows] == scores
    assert rows[0]["change"] is None
    assert [r["change"] for r in rows[1:]] == [0.1, 0.1, 0.1]
    # window=2 -> mean of this bucket and the one before it
    assert rows[0]["rolling_sentiment"] == 0.1
    assert [r["rolling_sentiment"] for r in rows[1:]] == [0.15, 0.25, 0.35]


def test_monthly_view_is_materialised_and_refresh_is_idempotent():
    db = mongo.get_db()
    db[mongo.NEWS].insert_many([
        _article(datetime(2020, 1, 10), 0.2),
        _article(datetime(2020, 1, 20), 0.6),
        _article(datetime(2020, 2, 5), -0.5),
    ])

    news.refresh_sentiment_monthly()
    rows = news.monthly_sentiment(TEST_TICKER)
    assert [(r["month"], r["articles"], r["avg_sentiment"]) for r in rows] == [
        ("2020-02", 1, -0.5), ("2020-01", 2, 0.4)]
    assert rows[1]["positive"] == 2 and rows[0]["negative"] == 1

    # Re-running replaces rows in place (unique index on ticker+month),
    # so the row count does not grow.
    news.refresh_sentiment_monthly()
    assert db[mongo.SENTIMENT_MONTHLY].count_documents({"ticker": TEST_TICKER}) == 2

    # A new source article is picked up on the next refresh.
    db[mongo.NEWS].insert_one(_article(datetime(2020, 2, 25), 0.1))
    news.refresh_sentiment_monthly()
    feb = news.monthly_sentiment(TEST_TICKER)[0]
    assert (feb["month"], feb["articles"], feb["avg_sentiment"]) == ("2020-02", 2, -0.2)


def test_note_ticker_must_exist_in_mysql():
    with pytest.raises(HTTPException) as exc_info:
        notes.create_note(TEST_USER_ID, {"body": "x", "ticker": TEST_TICKER})
    assert exc_info.value.status_code == 404
    assert mongo.get_db()[mongo.NOTES].count_documents({"user_id": TEST_USER_ID}) == 0


def test_digest_joins_each_note_to_latest_headlines():
    db = mongo.get_db()
    notes.create_note(TEST_USER_ID, {"body": "watching", "ticker": "AAPL"})
    notes.create_note(TEST_USER_ID, {"body": "no ticker"})

    per_note = 3
    digest = notes.digest(TEST_USER_ID, per_note=per_note)

    # Only the note with a ticker is joined.
    assert len(digest) == 1
    entry = digest[0]
    assert entry["ticker"] == "AAPL"
    assert "body" not in entry and "user_id" not in entry

    expected = list(db[mongo.NEWS].find({"ticker": "AAPL"}, {"published_at": 1,
                                                             "sentiment.score": 1})
                    .sort("published_at", -1).limit(per_note))
    assert expected, "CI fixture should contain AAPL news"
    got = entry["latest_news"]
    assert len(got) == len(expected)
    # Compare the multiset of timestamps, which is stable even when two
    # articles share a published_at.
    assert sorted(a["published_at"] for a in got) == sorted(
        e["published_at"].isoformat() for e in expected)
    assert entry["recent_sentiment"] == round(
        sum(a["score"] for a in got) / len(got), 4)
