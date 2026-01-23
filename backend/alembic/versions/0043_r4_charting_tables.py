"""add r4 charting tables

Revision ID: 0043_r4_charting_tables
Revises: 0042_r4_appointment_patient_links
Create Date: 2026-01-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0043_r4_charting_tables"
down_revision = "0042_r4_appointment_patient_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "r4_tooth_systems",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_tooth_system_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.SmallInteger(), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_tooth_system_id",
            name="uq_r4_tooth_systems_legacy_key",
        ),
    )
    op.create_table(
        "r4_tooth_surfaces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_tooth_id", sa.Integer(), nullable=False),
        sa.Column("legacy_surface_no", sa.SmallInteger(), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=True),
        sa.Column("short_label", sa.String(length=20), nullable=True),
        sa.Column("sort_order", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_tooth_id",
            "legacy_surface_no",
            name="uq_r4_tooth_surfaces_legacy_key",
        ),
    )
    op.create_table(
        "r4_chart_healing_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_action_id", sa.Integer(), nullable=False),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("appointment_need_id", sa.Integer(), nullable=True),
        sa.Column("tp_number", sa.Integer(), nullable=True),
        sa.Column("tp_item", sa.Integer(), nullable=True),
        sa.Column("code_id", sa.Integer(), nullable=True),
        sa.Column("action_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_type", sa.String(length=120), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("surface", sa.SmallInteger(), nullable=True),
        sa.Column("status", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_action_id",
            name="uq_r4_chart_healing_actions_legacy_key",
        ),
    )
    op.create_table(
        "r4_bpe_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_bpe_key", sa.String(length=160), nullable=False),
        sa.Column("legacy_bpe_id", sa.Integer(), nullable=True),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sextant_1", sa.SmallInteger(), nullable=True),
        sa.Column("sextant_2", sa.SmallInteger(), nullable=True),
        sa.Column("sextant_3", sa.SmallInteger(), nullable=True),
        sa.Column("sextant_4", sa.SmallInteger(), nullable=True),
        sa.Column("sextant_5", sa.SmallInteger(), nullable=True),
        sa.Column("sextant_6", sa.SmallInteger(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_bpe_key",
            name="uq_r4_bpe_entries_legacy_key",
        ),
    )
    op.create_table(
        "r4_bpe_furcations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_bpe_furcation_key", sa.String(length=160), nullable=False),
        sa.Column("legacy_bpe_id", sa.Integer(), nullable=True),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("furcation", sa.SmallInteger(), nullable=True),
        sa.Column("sextant", sa.SmallInteger(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_bpe_furcation_key",
            name="uq_r4_bpe_furcations_legacy_key",
        ),
    )
    op.create_table(
        "r4_perio_probes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_probe_key", sa.String(length=160), nullable=False),
        sa.Column("legacy_trans_id", sa.Integer(), nullable=True),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("probing_point", sa.SmallInteger(), nullable=True),
        sa.Column("depth", sa.SmallInteger(), nullable=True),
        sa.Column("bleeding", sa.SmallInteger(), nullable=True),
        sa.Column("plaque", sa.SmallInteger(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_probe_key",
            name="uq_r4_perio_probes_legacy_key",
        ),
    )
    op.create_table(
        "r4_perio_plaque",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_plaque_key", sa.String(length=160), nullable=False),
        sa.Column("legacy_trans_id", sa.Integer(), nullable=True),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("plaque", sa.SmallInteger(), nullable=True),
        sa.Column("bleeding", sa.SmallInteger(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_plaque_key",
            name="uq_r4_perio_plaque_legacy_key",
        ),
    )
    op.create_table(
        "r4_patient_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_note_key", sa.String(length=200), nullable=False),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("legacy_note_number", sa.Integer(), nullable=True),
        sa.Column("note_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("surface", sa.SmallInteger(), nullable=True),
        sa.Column("category_number", sa.Integer(), nullable=True),
        sa.Column("fixed_note_code", sa.Integer(), nullable=True),
        sa.Column("user_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_note_key",
            name="uq_r4_patient_notes_legacy_key",
        ),
    )
    op.create_table(
        "r4_fixed_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_fixed_note_code", sa.Integer(), nullable=False),
        sa.Column("category_number", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("surface", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_fixed_note_code",
            name="uq_r4_fixed_notes_legacy_key",
        ),
    )
    op.create_table(
        "r4_note_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_category_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_category_number",
            name="uq_r4_note_categories_legacy_key",
        ),
    )
    op.create_table(
        "r4_treatment_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_treatment_note_id", sa.Integer(), nullable=False),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("tp_number", sa.Integer(), nullable=True),
        sa.Column("tp_item", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("note_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_treatment_note_id",
            name="uq_r4_treatment_notes_legacy_key",
        ),
    )
    op.create_table(
        "r4_temporary_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_patient_code",
            name="uq_r4_temporary_notes_legacy_key",
        ),
    )
    op.create_table(
        "r4_old_patient_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "legacy_source",
            sa.String(length=120),
            server_default=sa.text("'r4'"),
            nullable=False,
        ),
        sa.Column("legacy_note_key", sa.String(length=200), nullable=False),
        sa.Column("legacy_patient_code", sa.Integer(), nullable=True),
        sa.Column("legacy_note_number", sa.Integer(), nullable=True),
        sa.Column("note_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("tooth", sa.SmallInteger(), nullable=True),
        sa.Column("surface", sa.SmallInteger(), nullable=True),
        sa.Column("category_number", sa.Integer(), nullable=True),
        sa.Column("fixed_note_code", sa.Integer(), nullable=True),
        sa.Column("user_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "legacy_source",
            "legacy_note_key",
            name="uq_r4_old_patient_notes_legacy_key",
        ),
    )

    op.create_index(
        "ix_r4_tooth_surfaces_tooth",
        "r4_tooth_surfaces",
        ["legacy_source", "legacy_tooth_id"],
    )
    op.create_index(
        "ix_r4_chart_healing_actions_patient_date",
        "r4_chart_healing_actions",
        ["legacy_source", "legacy_patient_code", "action_date"],
    )
    op.create_index(
        "ix_r4_bpe_entries_patient_date",
        "r4_bpe_entries",
        ["legacy_source", "legacy_patient_code", "recorded_at"],
    )
    op.create_index(
        "ix_r4_bpe_furcations_patient",
        "r4_bpe_furcations",
        ["legacy_source", "legacy_patient_code"],
    )
    op.create_index(
        "ix_r4_perio_probes_patient",
        "r4_perio_probes",
        ["legacy_source", "legacy_patient_code"],
    )
    op.create_index(
        "ix_r4_perio_plaque_patient",
        "r4_perio_plaque",
        ["legacy_source", "legacy_patient_code"],
    )
    op.create_index(
        "ix_r4_patient_notes_patient_date",
        "r4_patient_notes",
        ["legacy_source", "legacy_patient_code", "note_date"],
    )
    op.create_index(
        "ix_r4_treatment_notes_patient_date",
        "r4_treatment_notes",
        ["legacy_source", "legacy_patient_code", "note_date"],
    )
    op.create_index(
        "ix_r4_temporary_notes_patient",
        "r4_temporary_notes",
        ["legacy_source", "legacy_patient_code"],
    )
    op.create_index(
        "ix_r4_old_patient_notes_patient_date",
        "r4_old_patient_notes",
        ["legacy_source", "legacy_patient_code", "note_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_r4_old_patient_notes_patient_date", table_name="r4_old_patient_notes")
    op.drop_index("ix_r4_temporary_notes_patient", table_name="r4_temporary_notes")
    op.drop_index("ix_r4_treatment_notes_patient_date", table_name="r4_treatment_notes")
    op.drop_index("ix_r4_patient_notes_patient_date", table_name="r4_patient_notes")
    op.drop_index("ix_r4_perio_plaque_patient", table_name="r4_perio_plaque")
    op.drop_index("ix_r4_perio_probes_patient", table_name="r4_perio_probes")
    op.drop_index("ix_r4_bpe_furcations_patient", table_name="r4_bpe_furcations")
    op.drop_index("ix_r4_bpe_entries_patient_date", table_name="r4_bpe_entries")
    op.drop_index(
        "ix_r4_chart_healing_actions_patient_date",
        table_name="r4_chart_healing_actions",
    )
    op.drop_index("ix_r4_tooth_surfaces_tooth", table_name="r4_tooth_surfaces")

    op.drop_table("r4_old_patient_notes")
    op.drop_table("r4_temporary_notes")
    op.drop_table("r4_treatment_notes")
    op.drop_table("r4_note_categories")
    op.drop_table("r4_fixed_notes")
    op.drop_table("r4_patient_notes")
    op.drop_table("r4_perio_plaque")
    op.drop_table("r4_perio_probes")
    op.drop_table("r4_bpe_furcations")
    op.drop_table("r4_bpe_entries")
    op.drop_table("r4_chart_healing_actions")
    op.drop_table("r4_tooth_surfaces")
    op.drop_table("r4_tooth_systems")
