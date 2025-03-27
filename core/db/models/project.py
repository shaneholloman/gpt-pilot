import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Union
from unicodedata import normalize
from uuid import UUID, uuid4

from sqlalchemy import Row, delete, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from core.db.models import Base

if TYPE_CHECKING:
    from core.db.models import Branch


class Project(Base):
    __tablename__ = "projects"

    # ID and parent FKs
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Attributes
    name: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    folder_name: Mapped[str] = mapped_column(
        default=lambda context: Project.get_folder_from_project_name(context.get_current_parameters()["name"])
    )

    # Relationships
    branches: Mapped[list["Branch"]] = relationship(back_populates="project", cascade="all", lazy="raise")

    @staticmethod
    async def get_by_id(session: "AsyncSession", project_id: Union[str, UUID]) -> Optional["Project"]:
        """
        Get a project by ID.

        :param session: The SQLAlchemy session.
        :param project_id: The project ID (as str or UUID value).
        :return: The Project object if found, None otherwise.
        """
        if not isinstance(project_id, UUID):
            project_id = UUID(project_id)

        result = await session.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def get_branch(self, name: Optional[str] = None) -> Optional["Branch"]:
        """
        Get a project branch by name.

        :param session: The SQLAlchemy session.
        :param branch_name: The name of the branch (default "main").
        :return: The Branch object if found, None otherwise.
        """
        from core.db.models import Branch

        session = inspect(self).async_session
        if session is None:
            raise ValueError("Project instance not associated with a DB session.")

        if name is None:
            name = Branch.DEFAULT

        result = await session.execute(select(Branch).where(Branch.project_id == self.id, Branch.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_projects(session: "AsyncSession") -> list[Row]:
        query = select(Project.id, Project.name, Project.created_at, Project.folder_name).order_by(Project.name)

        result = await session.execute(query)
        return result.fetchall()

    @staticmethod
    def get_folder_from_project_name(name: str):
        """
        Get the folder name from the project name.

        :param name: Project name.
        :return: Folder name.
        """
        # replace unicode with accents with base characters (eg "šašavi" → "sasavi")
        name = normalize("NFKD", name).encode("ascii", "ignore").decode("utf-8")

        # replace spaces/interpunction with a single dash
        return re.sub(r"[^a-zA-Z0-9]+", "-", name).lower().strip("-")

    @staticmethod
    async def delete_by_id(session: "AsyncSession", project_id: UUID) -> int:
        """
        Delete a project by ID.

        :param session: The SQLAlchemy session.
        :param project_id: The project ID
        :return: Number of rows deleted.
        """

        result = await session.execute(delete(Project).where(Project.id == project_id))
        return result.rowcount
