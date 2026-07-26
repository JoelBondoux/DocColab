from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agent.config import load_config
from agent.logging_config import configure_logging
from agent.mcp_server.auth_middleware import BearerAuthMiddleware
from agent.mcp_server.models import MCPServerConfig, Role
from agent.mcp_server.registry import (
    ProjectRegistry,
    UserRegistry,
    load_server_config,
)
from agent.mcp_server.runtime_cache import ProjectRuntimeCache, SyncSupervisor
from agent.mcp_server.service import MCPService
from agent.mcp_server.tools import register_tools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="doccolab-mcp")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("mcp-config.json"),
        help="Path to mcp-config.json",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("serve", help="Run the authenticated Streamable HTTP MCP server")
    owner = subparsers.add_parser("init-owner", help="Create the first global owner")
    owner.add_argument("--user-id", required=True)
    owner.add_argument("--display-name")
    rotate = subparsers.add_parser("rotate-token", help="Rotate one user's bearer token")
    rotate.add_argument("--user-id", required=True)
    subparsers.add_parser("validate", help="Validate server, user, project, and sync configs")
    return parser


def cli() -> None:
    arguments = build_parser().parse_args()
    config = load_server_config(arguments.config)
    configure_logging(config.log_level)
    users = UserRegistry(config.users_file)
    projects = ProjectRegistry(config)
    if arguments.command == "init-owner":
        record, token = users.add(
            arguments.user_id,
            Role.OWNER,
            display_name=arguments.display_name,
        )
        print(
            json.dumps(
                {
                    "user_id": record.user_id,
                    "role": record.role.value,
                    "bearer_token": token,
                    "warning": "Store this token now; DocColab stores only its SHA-256 hash.",
                },
                indent=2,
            )
        )
        return
    if arguments.command == "rotate-token":
        token = users.rotate_token(arguments.user_id)
        print(
            json.dumps(
                {
                    "user_id": arguments.user_id,
                    "bearer_token": token,
                    "warning": "The previous token is invalid. Store this token now.",
                },
                indent=2,
            )
        )
        return
    if arguments.command == "validate":
        validated = []
        for project in projects.list():
            sync_config = load_config(project.root_path / project.sync_config)
            validated.append(
                {
                    "project_id": project.id,
                    "documents": len(sync_config.documents),
                    "exposed_folders": project.exposed_folders,
                }
            )
        owners = [user for user in users.list() if user.enabled and user.role == Role.OWNER]
        if not owners:
            raise RuntimeError("No enabled global owner exists; run init-owner")
        print(json.dumps({"users": len(users.list()), "projects": validated}, indent=2))
        return
    if arguments.command == "serve":
        if not any(user.enabled and user.role == Role.OWNER for user in users.list()):
            raise RuntimeError("No enabled global owner exists; run init-owner first")
        asyncio.run(_serve(config, users, projects))


async def _serve(
    config: MCPServerConfig,
    users: UserRegistry,
    projects: ProjectRegistry,
) -> None:
    runtimes = ProjectRuntimeCache()
    application = create_application(config, users, projects, runtimes)
    supervisor = application.supervisor
    uvicorn_server = uvicorn.Server(
        uvicorn.Config(
            application.app,
            host=config.host,
            port=config.port,
            log_level=config.log_level.lower(),
        )
    )
    supervisor_task = asyncio.create_task(supervisor.run(), name="doccolab-supervisor")
    server_task = asyncio.create_task(uvicorn_server.serve(), name="doccolab-mcp-http")
    try:
        done, _ = await asyncio.wait(
            {supervisor_task, server_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
    finally:
        supervisor.stop()
        uvicorn_server.should_exit = True
        await asyncio.gather(supervisor_task, server_task, return_exceptions=True)
        runtimes.close()


@dataclass(frozen=True, slots=True)
class MCPApplication:
    app: Any
    mcp: FastMCP
    supervisor: SyncSupervisor


def create_application(
    config: MCPServerConfig,
    users: UserRegistry,
    projects: ProjectRegistry,
    runtimes: ProjectRuntimeCache,
) -> MCPApplication:
    service = MCPService(
        config=config,
        users=users,
        projects=projects,
        runtimes=runtimes,
    )
    mcp = FastMCP(
        name="DocColab",
        instructions=(
            "Document collaboration tools are scoped by project, user role, configured "
            "tool allowlists, and explicitly exposed folders. Always supply project_id "
            "for project-scoped tools."
        ),
        host=config.host,
        port=config.port,
        streamable_http_path=config.mcp_path,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=config.allowed_hosts,
            allowed_origins=config.allowed_origins,
        ),
    )
    register_tools(mcp, service)
    app = mcp.streamable_http_app()

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "doccolab-mcp"})

    app.routes.append(Route("/healthz", endpoint=health, methods=["GET"]))
    authenticated_app = BearerAuthMiddleware(app, users)
    supervisor = SyncSupervisor(
        server_config=config,
        projects=projects,
        runtimes=runtimes,
    )
    return MCPApplication(app=authenticated_app, mcp=mcp, supervisor=supervisor)


if __name__ == "__main__":
    cli()
