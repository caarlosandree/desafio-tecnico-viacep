from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Endereco(Base):
    __tablename__ = "enderecos"
    __table_args__ = (
        CheckConstraint("cep ~ '^[0-9]{8}$'", name="cep_formato"),
        CheckConstraint("uf ~ '^[A-Z]{2}$'", name="uf_formato"),
        Index(None, "uf", "localidade"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cep: Mapped[str] = mapped_column(CHAR(8), unique=True)
    logradouro: Mapped[str] = mapped_column(String(255), server_default="")
    complemento: Mapped[str] = mapped_column(String(255), server_default="")
    bairro: Mapped[str] = mapped_column(String(120), server_default="")
    localidade: Mapped[str] = mapped_column(String(120))
    uf: Mapped[str] = mapped_column(CHAR(2))
    ibge: Mapped[str] = mapped_column(String(7), server_default="")
    ddd: Mapped[str] = mapped_column(String(2), server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Endereco cep={self.cep} {self.localidade}/{self.uf}>"
