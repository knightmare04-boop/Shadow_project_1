"""gl_invariants_triggers

Three database-level invariants that must hold no matter what application
code does (a bug, a bypassed service layer, a future direct SQL script):

1. Double-entry balance: sum(debit) == sum(credit) per journal_entry.
   A DEFERRABLE INITIALLY DEFERRED constraint trigger — checked once at
   COMMIT, after every line of a multi-line entry has been inserted, not
   after each individual row (which would reject every entry with more than
   one line, since debit and credit lines are inserted separately).
2. Period close: a journal_entry cannot be inserted or updated to reference
   a fiscal_period whose status is not 'open'. This is the actual
   enforcement; the FastAPI-level check (Module 4) exists only to return a
   friendly 409 before this trigger would raise a raw database error.
3. Audit-log immutability: UPDATE and DELETE are rejected outright on
   audit_log. Only INSERT is ever valid — this is what "immutable" means in
   a SOX-trail table, not just an application-level convention.

Revision ID: 6192dae4f4a4
Revises: 5444d20effda
Create Date: 2026-09-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "6192dae4f4a4"
down_revision: Union[str, None] = "5444d20effda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1. Double-entry balance (deferred constraint trigger) ------------
    op.execute("""
        CREATE OR REPLACE FUNCTION check_journal_entry_balance()
        RETURNS TRIGGER AS $$
        DECLARE
            entry_id UUID;
            total_debit NUMERIC(18,2);
            total_credit NUMERIC(18,2);
        BEGIN
            IF TG_OP = 'DELETE' THEN
                entry_id := OLD.journal_entry_id;
            ELSE
                entry_id := NEW.journal_entry_id;
            END IF;

            SELECT COALESCE(SUM(debit_amount), 0), COALESCE(SUM(credit_amount), 0)
              INTO total_debit, total_credit
              FROM journal_lines
             WHERE journal_entry_id = entry_id;

            IF total_debit <> total_credit THEN
                RAISE EXCEPTION
                    'journal entry % is not balanced: debit=% credit=%',
                    entry_id, total_debit, total_credit
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_journal_lines_balance
        AFTER INSERT OR UPDATE OR DELETE ON journal_lines
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION check_journal_entry_balance();
    """)

    # ---- 2. Period close ----------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION check_fiscal_period_open()
        RETURNS TRIGGER AS $$
        DECLARE
            period_status VARCHAR;
        BEGIN
            SELECT status INTO period_status
              FROM fiscal_periods
             WHERE id = NEW.fiscal_period_id;

            IF period_status IS NULL THEN
                RAISE EXCEPTION 'fiscal_period % does not exist', NEW.fiscal_period_id
                    USING ERRCODE = 'foreign_key_violation';
            ELSIF period_status <> 'open' THEN
                RAISE EXCEPTION
                    'cannot post journal entry: fiscal period % is %',
                    NEW.fiscal_period_id, period_status
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_journal_entries_period_open
        BEFORE INSERT OR UPDATE ON journal_entries
        FOR EACH ROW
        EXECUTE FUNCTION check_fiscal_period_open();
    """)

    # ---- 3. Audit-log immutability ------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_audit_log_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only: % is not permitted', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION reject_audit_log_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation();")

    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_period_open ON journal_entries;")
    op.execute("DROP FUNCTION IF EXISTS check_fiscal_period_open();")

    op.execute("DROP TRIGGER IF EXISTS trg_journal_lines_balance ON journal_lines;")
    op.execute("DROP FUNCTION IF EXISTS check_journal_entry_balance();")
