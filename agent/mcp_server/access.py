from __future__ import annotations

from agent.mcp_server.models import ROLE_LEVEL, ProjectDefinition, Role, UserRecord
from agent.mcp_server.registry import ProjectRegistry


class AccessController:
    def __init__(self, projects: ProjectRegistry) -> None:
        self.projects = projects

    def role_for(self, user: UserRecord, project: ProjectDefinition) -> Role | None:
        if user.role == Role.OWNER:
            return Role.OWNER
        return project.members.get(user.user_id)

    def authorize(
        self,
        user: UserRecord,
        project_id: str,
        tool_name: str,
        minimum_role: Role,
    ) -> ProjectDefinition:
        project = self.projects.get(project_id)
        if not project.enabled:
            raise AccessDenied("Project is disabled")
        role = self.role_for(user, project)
        if role is None or ROLE_LEVEL[role] < ROLE_LEVEL[minimum_role]:
            raise AccessDenied(
                f"{user.user_id} requires {minimum_role.value} access to {project_id}"
            )
        if "*" not in project.allowed_tools and tool_name not in project.allowed_tools:
            raise AccessDenied(f"Tool {tool_name} is disabled for project {project_id}")
        return project

    @staticmethod
    def require_global_owner(user: UserRecord) -> None:
        if user.role != Role.OWNER:
            raise AccessDenied("This operation requires a global owner")


class AccessDenied(PermissionError):
    pass
