from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from core.db.models import Base

if TYPE_CHECKING:
    from core.db.models import ChatMessage, ProjectState


class ChatConvo(Base):
    __tablename__ = "chat_convos"

    id: Mapped[int] = mapped_column(primary_key=True)
    convo_id: Mapped[UUID] = mapped_column(default=uuid4, unique=True)
    project_state_id: Mapped[UUID] = mapped_column(ForeignKey("project_states.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    project_state: Mapped["ProjectState"] = relationship(back_populates="chat_convos", lazy="selectin")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="convo", cascade="all,delete-orphan", lazy="selectin"
    )

    @staticmethod
    async def get_chat_history(session: AsyncSession, convo_id) -> list["ChatMessage"]:
        from core.db.models import ChatMessage

        result = await session.execute(select(ChatMessage).where(ChatMessage.convo_id == convo_id))
        return result.scalars().all()
