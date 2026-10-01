"""Capitaliza los estados de proyecto existentes y el CHECK que los valida."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

OLD_TO_NEW = {
    'pendiente': 'Pendiente',
    'en curso': 'En curso',
    'pausado': 'Pausado',
    'finalizado': 'Finalizado',
}


def upgrade() -> None:
    op.drop_constraint('proyecto_estado', 'proyecto', type_='check')
    for old, new in OLD_TO_NEW.items():
        op.execute(
            sa.text('UPDATE proyecto SET proyect_status = :new WHERE proyect_status = :old').bindparams(
                new=new, old=old
            )
        )
    op.create_check_constraint(
        'proyecto_estado', 'proyecto', "proyect_status IN ('Pendiente','En curso','Pausado','Finalizado')"
    )


def downgrade() -> None:
    op.drop_constraint('proyecto_estado', 'proyecto', type_='check')
    for old, new in OLD_TO_NEW.items():
        op.execute(
            sa.text('UPDATE proyecto SET proyect_status = :old WHERE proyect_status = :new').bindparams(
                new=new, old=old
            )
        )
    op.create_check_constraint(
        'proyecto_estado', 'proyecto', "proyect_status IN ('pendiente','en curso','pausado','finalizado')"
    )
