from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import TypeVar

from pydantic import ValidationError

T = TypeVar("T")


def run_cli(action: Callable[[], T]) -> int:
    """Run a CLI action with concise, stable operator-facing failures."""
    try:
        action()
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except (FileNotFoundError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Configuration error: {_summary(exc)}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"Access denied: {_summary(exc)}", file=sys.stderr)
        return 3
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"Operation failed: {_summary(exc)}", file=sys.stderr)
        return 1
    return 0


def _summary(exc: BaseException) -> str:
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return message[:500]
