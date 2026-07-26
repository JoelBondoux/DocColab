from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import uvicorn

from agent.config import load_config
from agent.google.google_auth import GoogleAuthenticator
from agent.logging_config import configure_logging
from agent.microsoft.ms_auth import MicrosoftAuthenticator
from agent.runtime import build_runtime
from agent.sync.state_store import StateStore
from agent.sync.sync_manager import SyncManager
from agent.webhook.app import create_webhook_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="doccolab")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to config.json (default: config.json)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run sync polling and the webhook receiver")
    subparsers.add_parser("once", help="Run one synchronization pass")
    subparsers.add_parser("auth-google", help="Authorize Google Docs and Drive")
    subparsers.add_parser("auth-microsoft", help="Authorize Microsoft Graph")
    subparsers.add_parser("watch-google", help="Create or renew Google Drive webhooks")
    subparsers.add_parser("status", help="Print local synchronization state")
    return parser


def cli() -> None:
    arguments = build_parser().parse_args()
    config = load_config(arguments.config)
    configure_logging(config.agent.log_level)
    if arguments.command == "auth-google":
        GoogleAuthenticator(config.google).authorize()
        print("Google authorization stored in the OS keyring.")
        return
    if arguments.command == "auth-microsoft":
        MicrosoftAuthenticator(config.microsoft).authorize()
        print("Microsoft authorization stored in the OS keyring.")
        return
    if arguments.command == "status":
        state = StateStore(config.agent.state_database)
        try:
            output = []
            for document in config.documents:
                output.append(asdict(state.ensure_document(document.id)))
            print(json.dumps(output, indent=2))
        finally:
            state.close()
        return

    runtime = build_runtime(config)
    try:
        if arguments.command == "once":
            results = asyncio.run(runtime.manager.sync_all())
            print(json.dumps([asdict(result) for result in results], indent=2))
        elif arguments.command == "watch-google":
            print(json.dumps(runtime.manager.renew_google_watches(), indent=2))
        elif arguments.command == "run":
            asyncio.run(_run_service(runtime.manager))
    finally:
        runtime.close()


async def _run_service(manager: SyncManager) -> None:
    app = create_webhook_app(manager)
    config = uvicorn.Config(
        app,
        host=manager.config.agent.webhook_host,
        port=manager.config.agent.webhook_port,
        log_level=manager.config.agent.log_level.lower(),
    )
    server = uvicorn.Server(config)
    sync_task = asyncio.create_task(manager.run_forever(), name="doccolab-sync")
    web_task = asyncio.create_task(server.serve(), name="doccolab-webhooks")
    try:
        done, _ = await asyncio.wait(
            {sync_task, web_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
    finally:
        manager.stop()
        server.should_exit = True
        await asyncio.gather(sync_task, web_task, return_exceptions=True)


if __name__ == "__main__":
    cli()
