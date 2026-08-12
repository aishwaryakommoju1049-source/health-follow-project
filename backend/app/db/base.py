"""Declarative base for all ORM models.

Every model in ``app/db/models/`` inherits from ``Base``, and every model
module must be imported here so that ``Base.metadata`` is complete — the test
fixtures and Alembic's autogenerate both rely on that.

Clinical tables are **append-only**: correct by inserting a new row, never by
updating an old one. That is what makes ``audit_log`` trustworthy.
See docs/ARCHITECTURE.md §7.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base."""


# Import model modules below so they register on Base.metadata.
# Phase 1 adds: users, doctors, patients, doctor_patient_link, consent_records,
# care_plans, prescriptions, med_events, check_ins, symptom_reports,
# agent_findings, risk_scores, escalations, soap_notes, audit_log.
#
# Example, once models exist:
#     from app.db.models import users
# Add a "noqa: F401" comment to each such import — they are imported for their
# registration side effect, not to be used.

__all__ = ["Base"]
