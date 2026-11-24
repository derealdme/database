"""Research notes -- full CRUD against MongoDB.

Deliberately schema-light: a note may carry a price target, arbitrary
tags, or nothing beyond a body. Adding a field to one note costs nothing
and migrates nothing, which is the argument for the document model.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.db import mongo, mysql

EDITABLE = {"title", "body", "ticker", "tags", "rating", "price_target",
            "conviction", "horizon", "attachments"}


def _oid(note_id: str) -> ObjectId:
    try:
        return ObjectId(note_id)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed note id")


def _checked_ticker(ticker: Any) -> str:
    """Normalise a note's ticker and confirm it exists in MySQL.

    MongoDB cannot hold a foreign key into MySQL, so this is the
    application-level stand-in for one: a note may only reference a
    stock the relational store knows about.
    """
    symbol = str(ticker).strip().upper()
    if mysql.query_one("SELECT 1 AS ok FROM stocks WHERE ticker = :t", {"t": symbol}) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown ticker {symbol}")
    return symbol


def _clean(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    for key in ("created_at", "updated_at"):
        if isinstance(doc.get(key), datetime):
            doc[key] = doc[key].isoformat()
    return doc


def list_notes(user_id: int, ticker: str | None = None,
               tag: str | None = None, search: str | None = None,
               limit: int = 50) -> list[dict]:
    query: dict[str, Any] = {"user_id": user_id}
    if ticker:
        query["ticker"] = ticker.strip().upper()
    if tag:
        query["tags"] = tag
    if search:
        query["$text"] = {"$search": search}

    cursor = mongo.get_db()[mongo.NOTES].find(query) \
        .sort([("updated_at", -1)]).limit(limit)
    return [_clean(d) for d in cursor]


def get_note(user_id: int, note_id: str) -> dict:
    doc = mongo.get_db()[mongo.NOTES].find_one(
        {"_id": _oid(note_id), "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return _clean(doc)


def create_note(user_id: int, payload: dict) -> dict:
    body = {k: v for k, v in payload.items() if k in EDITABLE and v is not None}
    if not body.get("body"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A note needs a body")

    now = datetime.utcnow()
    body.update({"user_id": user_id, "created_at": now, "updated_at": now})
    if body.get("ticker"):
        body["ticker"] = _checked_ticker(body["ticker"])

    result = mongo.get_db()[mongo.NOTES].insert_one(body)
    mongo.log_activity(user_id, "note.create",
                       {"note_id": str(result.inserted_id),
                        "ticker": body.get("ticker")})
    return get_note(user_id, str(result.inserted_id))


def update_note(user_id: int, note_id: str, payload: dict) -> dict:
    changes = {k: v for k, v in payload.items() if k in EDITABLE}
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")
    if changes.get("ticker"):
        changes["ticker"] = _checked_ticker(changes["ticker"])
    changes["updated_at"] = datetime.utcnow()

    result = mongo.get_db()[mongo.NOTES].update_one(
        {"_id": _oid(note_id), "user_id": user_id}, {"$set": changes})
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    mongo.log_activity(user_id, "note.update", {"note_id": note_id})
    return get_note(user_id, note_id)


def delete_note(user_id: int, note_id: str) -> None:
    result = mongo.get_db()[mongo.NOTES].delete_one(
        {"_id": _oid(note_id), "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    mongo.log_activity(user_id, "note.delete", {"note_id": note_id})


def digest(user_id: int, per_note: int = 3, limit: int = 20) -> list[dict]:
    """Each of the user's ticker notes joined to that ticker's latest headlines.

    One aggregation does the join: $lookup (MongoDB 5+ form, localField/
    foreignField plus a sub-pipeline) pulls the newest `per_note` articles
    for the note's ticker, using the {ticker, published_at} index on
    news_articles, and $addFields averages their sentiment.
    """
    pipeline = [
        {"$match": {"user_id": user_id, "ticker": {"$type": "string", "$ne": ""}}},
        {"$sort": {"updated_at": -1}},
        {"$limit": limit},
        {"$lookup": {
            "from": mongo.NEWS,
            "localField": "ticker",
            "foreignField": "ticker",
            "pipeline": [
                {"$sort": {"published_at": -1}},
                {"$limit": per_note},
                {"$project": {"_id": 0, "headline": 1, "published_at": 1,
                              "score": "$sentiment.score", "label": "$sentiment.label"}},
            ],
            "as": "latest_news",
        }},
        {"$addFields": {"recent_sentiment": {"$round": [{"$avg": "$latest_news.score"}, 4]}}},
        {"$project": {"user_id": 0, "body": 0, "attachments": 0}},
    ]
    out = []
    for doc in mongo.get_db()[mongo.NOTES].aggregate(pipeline):
        doc = _clean(doc)
        for article in doc["latest_news"]:
            if isinstance(article.get("published_at"), datetime):
                article["published_at"] = article["published_at"].isoformat()
        out.append(doc)
    return out


def tag_cloud(user_id: int) -> list[dict]:
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 40},
        {"$project": {"_id": 0, "tag": "$_id", "count": 1}},
    ]
    return list(mongo.get_db()[mongo.NOTES].aggregate(pipeline))


def recent_activity(user_id: int, limit: int = 40) -> list[dict]:
    """The TTL-expiring activity log."""
    cursor = mongo.get_db()[mongo.ACTIVITY].find({"user_id": user_id}) \
        .sort([("created_at", -1)]).limit(limit)
    out = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        out.append(doc)
    return out
