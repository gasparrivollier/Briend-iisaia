"""Tareas planificadas de cada proyecto (Gantt)."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tarea',
        sa.Column('tarea_id', sa.Integer(), primary_key=True),
        sa.Column(
            'proyecto_id',
            sa.Integer(),
            sa.ForeignKey('proyecto.proyecto_id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('tarea_nombre', sa.Text(), nullable=False),
        sa.Column('fecha_inicio', sa.Date(), nullable=False),
        sa.Column('fecha_fin', sa.Date(), nullable=False),
        sa.Column('porcentaje_avance', sa.Double(), nullable=False, server_default='0'),
        sa.Column(
            'recurso_id',
            sa.Integer(),
            sa.ForeignKey('recurso.recurso_id', ondelete='RESTRICT'),
            nullable=True,
        ),
        sa.CheckConstraint('length(trim(tarea_nombre)) > 0', name='tarea_nombre_no_vacio'),
        sa.CheckConstraint('fecha_fin >= fecha_inicio', name='tarea_fechas'),
        sa.CheckConstraint('porcentaje_avance BETWEEN 0 AND 100', name='tarea_avance'),
    )
    op.create_index('ix_tarea_proyecto_id', 'tarea', ['proyecto_id'])
    op.create_index('ix_tarea_recurso_id', 'tarea', ['recurso_id'])


def downgrade() -> None:
    op.drop_table('tarea')
