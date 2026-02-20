import shutil
import subprocess
from pathlib import Path

import typer

from smartbear_articles.downloader import fetch_articles

app = typer.Typer(
    add_completion=False,
    help="Download and export the SmartBear Longform collection.",
)

ROOT_OPTION = typer.Option(None, "--root", help="Project root.")
CLEAN_ROOT_OPTION = typer.Option(
    None, "--root", help="Project root where outputs are stored."
)
DELAY_OPTION = typer.Option(0.05, "--delay", help="Delay between requests.")
MARKDOWN_OPTION = typer.Option(
    False, "--markdown/--no-markdown", help="Download articles as markdown files."
)
CSV_OPTION = typer.Option(False, "--csv/--no-csv", help="Write articles.csv metadata.")
CSV_PATH_OPTION = typer.Option(None, "--csv-path", help="Optional path for the CSV export.")


def _resolve_root(root: Path | None) -> Path:
    return root.resolve() if root else Path.cwd()


def _require_tool(name: str) -> str:
    tool_path = shutil.which(name)
    if not tool_path:
        typer.secho(
            f"Missing required tool: {name}. Install it and ensure it's on PATH.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    return tool_path


@app.command()
def clean(
    root: Path | None = CLEAN_ROOT_OPTION,
) -> None:
    """Remove generated files."""
    base = _resolve_root(root)
    paths = [
        base / "articles",
        base / "smartbear.epub",
        base / "smartbear.pdf",
        base / "smartbear.md",
        base / "articles.csv",
    ]
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    typer.echo("Cleaned generated files.")


@app.command()
def fetch(
    root: Path | None = ROOT_OPTION,
    delay: float = DELAY_OPTION,
    markdown: bool = MARKDOWN_OPTION,
    csv: bool = CSV_OPTION,
    csv_path: Path | None = CSV_PATH_OPTION,
) -> None:
    """Download articles and/or export metadata."""
    if not markdown and not csv:
        typer.secho(
            "Nothing to do. Use --markdown and/or --csv to fetch.",
            fg=typer.colors.RED,
        )
        typer.echo(typer.get_current_context().get_help())
        raise typer.Exit(code=1)

    base = _resolve_root(root)
    output_dir = base / "articles"
    resolved_csv = csv_path or (base / "articles.csv")
    fetch_articles(
        output_dir=output_dir,
        csv_path=resolved_csv if csv else None,
        delay_seconds=delay,
        download_markdown=markdown,
    )


@app.command()
def merge(
    root: Path | None = ROOT_OPTION,
) -> None:
    """Merge all articles into a single markdown file using pandoc."""
    base = _resolve_root(root)
    articles_dir = base / "articles"
    if not articles_dir.exists():
        typer.secho("Articles directory not found. Run fetch first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    _require_tool("pandoc")
    output_path = base / "smartbear.md"
    subprocess.run(
        ["pandoc", *map(str, sorted(articles_dir.glob("*.md"))), "-o", str(output_path)],
        check=True,
    )
    typer.echo(f"Wrote {output_path.name}.")


@app.command()
def epub(
    root: Path | None = ROOT_OPTION,
) -> None:
    """Create an EPUB using pandoc."""
    base = _resolve_root(root)
    articles_dir = base / "articles"
    if not articles_dir.exists():
        typer.secho("Articles directory not found. Run fetch first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

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
    typer.echo(f"Wrote {output_path.name}.")


@app.command()
def pdf(
    root: Path | None = ROOT_OPTION,
) -> None:
    """Create a PDF via calibre's ebook-convert."""
    base = _resolve_root(root)
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
    typer.echo(f"Wrote {output_path.name}.")


@app.command()
def wordcount(
    root: Path | None = ROOT_OPTION,
) -> None:
    """Count total words and articles."""
    base = _resolve_root(root)
    articles_dir = base / "articles"
    if not articles_dir.exists():
        typer.secho("Articles directory not found. Run fetch first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    word_total = 0
    files = sorted(articles_dir.glob("*.md"))
    for path in files:
        word_total += len(path.read_text(encoding="utf-8", errors="ignore").split())

    typer.echo(f"Total words: {word_total}")
    typer.echo(f"Total articles: {len(files)}")


@app.command()
def all(
    root: Path | None = ROOT_OPTION,
    delay: float = DELAY_OPTION,
    csv: bool = typer.Option(True, "--csv/--no-csv", help="Write articles.csv metadata."),
    csv_path: Path | None = CSV_PATH_OPTION,
) -> None:
    """Run clean, fetch, merge, epub, and wordcount."""
    base = _resolve_root(root)
    clean(base)
    fetch(base, delay=delay, csv=csv, csv_path=csv_path, markdown=True)
    merge(base)
    epub(base)
    wordcount(base)


def _main() -> None:
    app()


if __name__ == "__main__":
    _main()
