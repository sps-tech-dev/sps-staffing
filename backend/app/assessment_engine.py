"""Aptitude test engine core (B.7) — pure-ish select/freeze/grade functions.

The anti-cheat contract:
  - FREEZE: at issue time, questions are weighted-random selected, question order
    AND option order are shuffled, and the exact served paper — including the
    correct answer positions AFTER shuffling — is persisted into
    tests.served_questions. Grading runs against that frozen copy ONLY; editing
    or deactivating bank questions later cannot change a taken test.
  - ANSWERS NEVER LEAVE THE SERVER: public_paper() strips the correct answers;
    it is the ONLY shape the take-test surface may return.
  - GRADE: score = correct / total, no negative marking, pass at
    settings.test_pass_threshold (>= 0.70).

Randomness uses SystemRandom (CSPRNG) — paper composition is unpredictable.
"""
from __future__ import annotations

import hashlib
import random
import secrets

from .config import settings

_rng = random.SystemRandom()


def new_link_token() -> tuple[str, str]:
    """(raw_token, sha256_hash). The raw token is shown ONCE and never stored."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def select_questions(questions: list, count: int) -> list:
    """Weighted-random selection: draw as evenly as possible across the difficulty
    levels present, fill any remainder randomly. `questions` are ORM rows (or
    anything with .difficulty). Returns at most `count` items."""
    if not questions:
        return []
    count = min(count, len(questions))
    by_diff: dict[str, list] = {}
    for q in questions:
        by_diff.setdefault(q.difficulty, []).append(q)
    for pool in by_diff.values():
        _rng.shuffle(pool)
    picked: list = []
    per_level = max(1, count // len(by_diff))
    for pool in by_diff.values():
        picked.extend(pool[:per_level])
    if len(picked) > count:
        _rng.shuffle(picked)
        picked = picked[:count]
    else:
        remaining = [q for pool in by_diff.values() for q in pool if q not in picked]
        _rng.shuffle(remaining)
        picked.extend(remaining[:count - len(picked)])
    _rng.shuffle(picked)
    return picked


def freeze_paper(questions: list) -> list[dict]:
    """The frozen served set: per question, the shuffled options and the correct
    index REMAPPED to the shuffled order. This structure is the single source of
    truth for grading."""
    frozen = []
    for q in questions:
        order = list(range(len(q.options)))
        _rng.shuffle(order)
        frozen.append({
            "qid": str(q.id),
            "stem": q.stem,
            "options": [q.options[i] for i in order],
            "correct": order.index(q.correct_index),   # position of the right answer post-shuffle
            "difficulty": q.difficulty,
        })
    return frozen


def public_paper(frozen: list[dict]) -> list[dict]:
    """What the candidate sees: stems + shuffled options ONLY. Never 'correct'."""
    return [{"qid": f["qid"], "stem": f["stem"], "options": f["options"]} for f in frozen]


def grade(frozen: list[dict], answers: dict) -> tuple[float, bool, list[dict]]:
    """Grade submitted answers ({qid: chosen_index}) against the FROZEN paper.
    Missing/invalid answers are simply wrong — no negative marking."""
    per_q = []
    correct = 0
    for f in frozen:
        chosen = answers.get(f["qid"])
        is_right = isinstance(chosen, int) and chosen == f["correct"]
        correct += int(is_right)
        per_q.append({"qid": f["qid"], "correct": is_right})
    score = correct / len(frozen) if frozen else 0.0
    return score, score >= settings.test_pass_threshold, per_q
