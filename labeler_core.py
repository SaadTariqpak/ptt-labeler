"""Database side of the labelling page: the two tables and the four calls the page needs.

The pool of comments and the analysis of the answers live in the private project; this app only serves comments and
stores answers. Tables match the private project's sql/schema.sql (rating_items, ratings).
"""
from __future__ import annotations

import os
import random
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
                        create_engine, event, func, select)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

LABELS = ("positive", "negative", "neutral", "sarcastic", "unsure")
BATCH_SIZE = 25  # comments per round, checks included
CHECKS_PER_BATCH = 2

BigInt = BigInteger().with_variant(Integer, "sqlite")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RatingItem(Base):
    __tablename__ = "rating_items"
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    comment_id: Mapped[int | None] = mapped_column(BigInt, unique=True)
    text: Mapped[str] = mapped_column(Text)
    tag: Mapped[str | None] = mapped_column(String)
    post_title: Mapped[str | None] = mapped_column(Text)
    board: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String, default="item")
    expected_label: Mapped[str | None] = mapped_column(String)
    stratum: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("item_id", "rater_email"),)
    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("rating_items.id", ondelete="CASCADE"), index=True)
    rater_email: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str] = mapped_column(String)
    submission_id: Mapped[str | None] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        url = os.environ["DATABASE_URL"]
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        _engine = create_engine(url, future=True, pool_pre_ping=True)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk(conn, _):
                conn.execute("PRAGMA foreign_keys=ON")
        _Session = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def init_db():
    Base.metadata.create_all(get_engine())  # creates the two tables only if they are missing


@contextmanager
def session_scope():
    get_engine()
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def categories() -> dict[str, int]:
    with session_scope() as s:
        rows = s.execute(select(RatingItem.category, func.count()).where(
            RatingItem.kind == "item", RatingItem.is_active.is_(True)).group_by(RatingItem.category)).all()
    return {c: n for c, n in rows if c}


def next_batch(email: str, category: str | None = None, n: int = BATCH_SIZE, rng: random.Random | None = None):
    """Comments this rater has not seen, the least-rated first, with a couple of known-answer checks mixed in."""
    rng = rng or random.Random()
    with session_scope() as s:
        mine = select(Rating.item_id).where(Rating.rater_email == email)
        counts = select(Rating.item_id, func.count().label("n")).group_by(Rating.item_id).subquery()
        q = (select(RatingItem, func.coalesce(counts.c.n, 0)).outerjoin(counts, counts.c.item_id == RatingItem.id)
             .where(RatingItem.is_active.is_(True), RatingItem.id.not_in(mine)))
        items = s.execute(q.where(RatingItem.kind == "item", *([RatingItem.category == category] if category else []))).all()
        checks = s.execute(q.where(RatingItem.kind == "check")).all()
        rng.shuffle(items)
        items.sort(key=lambda r: r[1])  # stable: ties stay in random order
        rng.shuffle(checks)
        picked = [r[0] for r in checks[:CHECKS_PER_BATCH]] + [r[0] for r in items[:n - min(CHECKS_PER_BATCH, len(checks))]]
        rng.shuffle(picked)
        return [{"id": i.id, "text": i.text, "tag": i.tag, "post_title": i.post_title, "kind": i.kind} for i in picked]


def save_ratings(email: str, answers: dict[int, str], submission_id: str | None = None) -> int:
    """Store one rating per (item, rater); repeats and unknown labels are ignored.

    Each call is one attempt sharing a submission_id, so a returning rater's rounds stay separate.
    """
    submission_id = submission_id or uuid.uuid4().hex
    with session_scope() as s:
        done = set(s.scalars(select(Rating.item_id).where(Rating.rater_email == email,
                                                          Rating.item_id.in_(list(answers)))))
        new = [Rating(item_id=i, rater_email=email, label=lab, submission_id=submission_id) for i, lab in answers.items()
               if lab in LABELS and i not in done]
        s.add_all(new)
        return len(new)


def rater_stats(email: str) -> dict:
    with session_scope() as s:
        rows = s.execute(select(RatingItem.kind, RatingItem.expected_label, Rating.label)
                         .join(Rating, Rating.item_id == RatingItem.id).where(Rating.rater_email == email)).all()
    checks = [(e, l) for k, e, l in rows if k == "check"]
    return {"labelled": sum(k == "item" for k, _, _ in rows), "checks": len(checks),
            "checks_right": sum(e == l for e, l in checks)}
