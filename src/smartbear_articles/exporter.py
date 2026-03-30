import shutil
import subprocess
from pathlib import Path

import typer


def _require_tool(name: str) -> str:
    tool_path = shutil.which(name)
    if not tool_path:
        typer.secho(
            f"Missing required tool: {name}. Install it and ensure it's on PATH.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    return tool_path


def _require_articles_dir(base: Path) -> Path:
    articles_dir = base / "articles"
    if not articles_dir.exists():
        typer.secho("Articles directory not found. Run fetch first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    return articles_dir


def merge_articles(base: Path) -> Path:
    articles_dir = _require_articles_dir(base)

    _require_tool("pandoc")
    output_path = base / "smartbear.md"
    subprocess.run(
        ["pandoc", *map(str, sorted(articles_dir.glob("*.md"))), "-o", str(output_path)],
        check=True,
    )
    return output_path


def create_epub(base: Path) -> Path:
    articles_dir = _require_articles_dir(base)

    _require_tool("pandoc")
    output_path = base / "smartbear.epub"
    metadata_path = base / "metadata.yaml"
    cover_path = base / "cover.png"
    subprocess.run(
        [
            "pandoc",
            *map(str, sorted(articles_dir.glob("*.md"))),
            "-o",
            str(output_path),
            "-t",
            "epub3",
            "-f",
            "markdown",
            "--metadata-file",
            str(metadata_path),
            "--toc",
            "--toc-depth=1",
            "--epub-cover-image",
            str(cover_path),
        ],
        check=True,
    )
    return output_path


def create_pdf(base: Path) -> Path:
    epub_path = base / "smartbear.epub"
    if not epub_path.exists():
        typer.secho("EPUB not found. Run epub first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    _require_tool("ebook-convert")
    output_path = base / "smartbear.pdf"
    subprocess.run(
        ["ebook-convert", str(epub_path), str(output_path)],
        check=True,
    )
    return output_path
