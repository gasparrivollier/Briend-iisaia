"""ORM models. Table and column names keep the original Spanish schema (incl. `proyect_status`)."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STATUSES = ('Pendiente', 'En curso', 'Pausado', 'Finalizado')


class Base(DeclarativeBase):
    pass


class Recurso(Base):
    __tablename__ = 'recurso'
    __table_args__ = (CheckConstraint('length(trim(recurso_nombre)) > 0', name='recurso_nombre_no_vacio'),)

    recurso_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recurso_nombre: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    password: Mapped[str] = mapped_column(Text)
    es_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')


class Rol(Base):
    __tablename__ = 'rol'
    __table_args__ = (CheckConstraint('length(trim(rol_descripcion)) > 0', name='rol_descripcion_no_vacia'),)

    rol_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rol_descripcion: Mapped[str] = mapped_column(Text)


# Case-insensitive uniqueness (replaces SQLite's COLLATE NOCASE).
Index('recurso_nombre_unico', func.lower(Recurso.recurso_nombre), unique=True)
Index('rol_descripcion_unica', func.lower(Rol.rol_descripcion), unique=True)


class Proyecto(Base):
    __tablename__ = 'proyecto'
    __table_args__ = (
        CheckConstraint('length(trim(proyecto_nombre)) > 0', name='proyecto_nombre_no_vacio'),
        CheckConstraint('fecha_fin >= fecha_inicio', name='proyecto_fechas'),
        CheckConstraint('horas_requeridas > 0', name='proyecto_horas_positivas'),
        CheckConstraint(
            "proyect_status IN ('Pendiente','En curso','Pausado','Finalizado')", name='proyecto_estado'
        ),
        CheckConstraint('porcentaje_avance BETWEEN 0 AND 100', name='proyecto_avance'),
    )

    proyecto_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proyecto_nombre: Mapped[str] = mapped_column(Text)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    horas_requeridas: Mapped[float] = mapped_column(Double)
    owner_id: Mapped[int] = mapped_column(ForeignKey('recurso.recurso_id', ondelete='RESTRICT'), index=True)
    proyect_status: Mapped[str] = mapped_column(Text)
    porcentaje_avance: Mapped[float] = mapped_column(Double, default=0, server_default='0')


class Consumo(Base):
    __tablename__ = 'consumo'
    __table_args__ = (
        CheckConstraint('fecha_fin >= fecha_inicio', name='consumo_fechas'),
        CheckConstraint('horas_consumidas > 0', name='consumo_horas_positivas'),
        CheckConstraint('length(trim(tarea)) > 0', name='consumo_tarea_no_vacia'),
    )

    consumo_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(
        ForeignKey('proyecto.proyecto_id', ondelete='RESTRICT'), index=True
    )
    recurso_id: Mapped[int] = mapped_column(ForeignKey('recurso.recurso_id', ondelete='RESTRICT'), index=True)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    horas_consumidas: Mapped[float] = mapped_column(Double)
    tarea: Mapped[str] = mapped_column(Text)
    rol_id: Mapped[int] = mapped_column(ForeignKey('rol.rol_id', ondelete='RESTRICT'), index=True)


class Tarea(Base):
    """Planned task of a project (Gantt). Its dates must fall inside the project's (checked by the API)."""

    __tablename__ = 'tarea'
    __table_args__ = (
        CheckConstraint('length(trim(tarea_nombre)) > 0', name='tarea_nombre_no_vacio'),
        CheckConstraint('fecha_fin >= fecha_inicio', name='tarea_fechas'),
        CheckConstraint('porcentaje_avance BETWEEN 0 AND 100', name='tarea_avance'),
    )

    tarea_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proyecto_id: Mapped[int] = mapped_column(
        ForeignKey('proyecto.proyecto_id', ondelete='RESTRICT'), index=True
    )
    tarea_nombre: Mapped[str] = mapped_column(Text)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    porcentaje_avance: Mapped[float] = mapped_column(Double, default=0, server_default='0')
    recurso_id: Mapped[int | None] = mapped_column(
        ForeignKey('recurso.recurso_id', ondelete='RESTRICT'), index=True, nullable=True
    )


class Sesion(Base):
    """Server-side browser session. Anonymous sessions (recurso_id NULL) carry the CSRF token before login."""

    __tablename__ = 'sesion'

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    recurso_id: Mapped[int | None] = mapped_column(
        ForeignKey('recurso.recurso_id', ondelete='CASCADE'), index=True
    )
    csrf: Mapped[str] = mapped_column(Text)
    creada: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
