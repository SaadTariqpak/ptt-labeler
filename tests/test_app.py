import os
import random

import pytest
from sqlalchemy import func, select
from streamlit.testing.v1 import AppTest

import labeler_core as core

APP = os.path.join(os.path.dirname(__file__), "..", "app.py")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setattr(core, "_engine", None)
    core.init_db()
    with core.session_scope() as s:
        s.add_all([core.RatingItem(text=f"留言{i}", tag="推", post_title="t", category="tech") for i in range(40)])
        s.add_all([core.RatingItem(text=f"檢查{i}", kind="check", expected_label="positive") for i in range(3)])
    return core


def test_batch_never_repeats_and_ratings_are_saved_once(db):
    first = db.next_batch("a@x.com", rng=random.Random(1))
    assert len(first) == db.BATCH_SIZE and sum(i["kind"] == "check" for i in first) == db.CHECKS_PER_BATCH
    assert db.save_ratings("a@x.com", {i["id"]: "neutral" for i in first}) == db.BATCH_SIZE
    assert db.save_ratings("a@x.com", {first[0]["id"]: "positive"}) == 0
    assert not {i["id"] for i in db.next_batch("a@x.com")} & {i["id"] for i in first}


def test_typed_email_then_a_round_is_saved(db, monkeypatch):
    monkeypatch.setenv("LABELER_OPEN_SIGNIN", "1")
    monkeypatch.delenv("LABELER_DEV_EMAIL", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception and len(at.pills) == 0
    at.text_input[0].set_value("Friend@Example.com")
    at.button[0].click().run()
    assert len(at.pills) == db.BATCH_SIZE and at.button[0].disabled
    for p in at.pills:
        p.set_value("neutral")
    at.run()
    at.button[0].click().run()
    assert not at.exception
    with db.session_scope() as s:
        assert s.scalar(select(func.count()).select_from(db.Rating).where(db.Rating.rater_email == "friend@example.com")) == 25
