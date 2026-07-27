from __future__ import annotations

import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path

from agent.config import ConversionConfig
from agent.conversion.docx_to_md import docx_to_markdown as fallback_docx_to_markdown
from agent.conversion.md_to_docx import markdown_to_docx as fallback_markdown_to_docx

# Pandoc is invoked with a fixed argv shape, shell=False, and a bounded timeout.


class DocumentConverter:
    def __init__(self, config: ConversionConfig) -> None:
        self.config = config

    @property
    def pandoc_available(self) -> bool:
        return shutil.which(self.config.pandoc_binary) is not None

    def docx_to_markdown(self, content: bytes) -> str:
        if self.config.prefer_pandoc and self.pandoc_available:
            return self._pandoc_docx_to_markdown(content)
        return fallback_docx_to_markdown(content)

    def markdown_to_docx(self, markdown: str) -> bytes:
        if self.config.prefer_pandoc and self.pandoc_available:
            return self._pandoc_markdown_to_docx(markdown)
        return fallback_markdown_to_docx(markdown)

    def _pandoc_docx_to_markdown(self, content: bytes) -> str:
        with tempfile.TemporaryDirectory(prefix="doccolab-") as temp:
            source = Path(temp) / "source.docx"
            target = Path(temp) / "document.md"
            source.write_bytes(content)
            self._run(
                [
                    self.config.pandoc_binary,
                    str(source),
                    "--from=docx",
                    "--to=gfm",
                    "--wrap=none",
                    "--output",
                    str(target),
                ]
            )
            return target.read_text(encoding="utf-8").strip() + "\n"

    def _pandoc_markdown_to_docx(self, markdown: str) -> bytes:
        with tempfile.TemporaryDirectory(prefix="doccolab-") as temp:
            source = Path(temp) / "document.md"
            target = Path(temp) / "document.docx"
            source.write_text(markdown, encoding="utf-8")
            command = [
                self.config.pandoc_binary,
                str(source),
                "--from=gfm",
                "--to=docx",
                "--output",
                str(target),
            ]
            if self.config.reference_docx:
                command.extend(["--reference-doc", str(self.config.reference_docx)])
            self._run(command)
            return target.read_bytes()

    @staticmethod
    def _run(command: list[str]) -> None:
        # No shell is involved; the configured executable and temporary paths are argv entries.
        result = subprocess.run(  # nosec B603
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode:
            raise ConversionError(
                f"Pandoc failed with exit code {result.returncode}: {result.stderr.strip()}"
            )


class ConversionError(RuntimeError):
    pass
