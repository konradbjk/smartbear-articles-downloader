import csv
import html
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import html2text
import regex as re
import requests
from dateparser import parse as parse_date
from htmldate import find_date


@dataclass(frozen=True)
class ArticleSource:
    feed_url: str = "https://longform.asmartbear.com/index.xml"


def _parse_rss(source: ArticleSource) -> list[dict[str, str]]:
    response = requests.get(source.feed_url, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.text)

    items: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        items.append(
            {
                "title": _find_child_text(item, ["title"]),
                "link": _find_child_text(item, ["link"]),
                "description": _find_child_text(item, ["description"]),
                "pub_date": _find_child_text(item, ["pubDate"]),
                "updated": _find_child_text(item, ["updated", "date"]),
                "author": _find_child_text(item, ["creator", "author"]),
                "markdown_url": _find_child_text(item, ["markdown"]),
                "guid": _find_child_text(item, ["guid"]),
            }
        )
    return items


def _find_child_text(item: ET.Element, names: list[str]) -> str:
    for child in item:
        local = child.tag.split("}")[-1]
        if local in names and child.text:
            return child.text.strip()
    return ""


def _convert_to_pandoc_footnotes(text: bytes | str) -> bytes:
    if isinstance(text, bytes):
        text = text.decode("utf-8")

    notes_section_pattern = r"\*\*Notes?\*\*.*?(?=\n\s*\*\*|\Z)"
    notes_match = re.search(notes_section_pattern, text, re.DOTALL | re.IGNORECASE)

    if not notes_match:
        return text.encode("utf-8")

    notes_content = notes_match.group(0)
    footnote_pattern = r"\[(\d+)\]\s*(.*?)(?=\s*\[\d+\]|\s*$)"
    footnotes = re.findall(footnote_pattern, notes_content, re.DOTALL)

    if not footnotes:
        return text.encode("utf-8")

    footnote_definitions: dict[str, str] = {}
    for note_num, note_content in footnotes:
        note_content = re.sub(r"\s+", " ", note_content.strip()).strip()
        if note_content:
            footnote_definitions[note_num] = note_content

    text = re.sub(notes_section_pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
    for note_num in footnote_definitions.keys():
        text = re.sub(rf"\[{note_num}\]", f"[^{note_num}]", text)

    if footnote_definitions:
        footnote_defs = []
        for note_num in sorted(footnote_definitions.keys(), key=int):
            footnote_defs.append(f"[^{note_num}]: {footnote_definitions[note_num]}")
        text += "\n\n" + "\n\n".join(footnote_defs)

    return text.encode("utf-8")


def _namespace_footnotes(text: str, prefix: str) -> str:
    def replace(match: re.Match) -> str:
        label = match.group("label")
        suffix = ":" if match.group("definition") else ""
        return f"[^{prefix}-{label}]{suffix}"

    return re.sub(
        r"\[\^(?P<label>[^\]\s]+)\](?P<definition>:)?",
        replace,
        text,
    )


def _yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _extract_description(parsed_text: str) -> str:
    lines = []
    for line in (line.strip() for line in parsed_text.splitlines()):
        if not line:
            continue
        if len(line) < 20:
            continue
        lines.append(line)
    return "\n".join(lines)


def _yaml_field(name: str, value: str) -> str:
    if "\n" not in value:
        return f'{name}: "{_yaml_escape(value)}"'

    lines = "\n".join(f"  {line}" for line in value.splitlines())
    return f"{name}: |-\n{lines}"


def _normalize_date(value: str) -> str:
    if not value:
        return ""
    parsed_date = parse_date(value)
    if not parsed_date:
        return ""
    return parsed_date.strftime("%Y-%m-%d")


def _normalize_url(value: str, base_url: str) -> str:
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return urljoin(base_url, value)


def fetch_articles(
    output_dir: Path,
    csv_path: Path | None,
    delay_seconds: float = 0.05,
    source: ArticleSource | None = None,
    download_markdown: bool = True,
    log: Callable[[str], None] | None = None,
) -> int:
    """Fetch articles into output_dir. Returns number of articles downloaded."""
    logger = log or (lambda message: print(message))
    source = source or ArticleSource()

    toc = list(reversed(_parse_rss(source)))
    logger(f"Found {len(toc)} articles.")

    if download_markdown:
        output_dir.mkdir(parents=True, exist_ok=True)

    if csv_path is not None and csv_path.exists():
        csv_path.unlink()

    if csv_path is not None:
        with csv_path.open("a+", newline="\n") as csv_file:
            fieldnames = [
                "Article no.",
                "Title",
                "Description",
                "Date",
                "Updated",
                "Author",
                "URL",
                "Markdown URL",
                "Guid",
                "Filename",
            ]
            csvwriter = csv.DictWriter(csv_file, fieldnames=fieldnames)
            csvwriter.writeheader()

    html_parser = html2text.HTML2Text()
    html_parser.ignore_images = True
    html_parser.ignore_tables = True
    html_parser.escape_all = True
    html_parser.reference_links = True
    html_parser.mark_code = True

    existing_keys = (
        _collect_existing_keys(output_dir) if download_markdown and output_dir.exists() else set()
    )
    new_entries: list[dict[str, str]] = []
    for entry in toc:
        key = _entry_key(entry, source)
        if not key:
            continue
        if key not in existing_keys:
            new_entries.append(entry)
    if download_markdown and not new_entries:
        logger("No new articles found. Skipping markdown download.")
        if csv_path is None:
            return 0

    success_count = 0
    for index, entry in enumerate(toc, start=1):
        entry_key = _entry_key(entry, source)
        if download_markdown and entry_key in existing_keys:
            if csv_path is not None:
                _write_csv_row(
                    csv_path,
                    index,
                    entry,
                    html_parser,
                    source,
                    output_filename="",
                )
            continue

        title = entry["title"]

        if not download_markdown:
            if csv_path is not None:
                _write_csv_row(
                    csv_path,
                    index,
                    entry,
                    html_parser,
                    source,
                    output_filename="",
                )
            continue

        try:
            output_path = _write_markdown_file(
                entry,
                index,
                output_dir,
                html_parser,
                source,
            )

            if csv_path is not None:
                _write_csv_row(
                    csv_path,
                    index,
                    entry,
                    html_parser,
                    source,
                    output_filename=output_path.name,
                )

            logger(f"✅ {str(index).zfill(3)} {title}")
            success_count += 1
        except Exception as exc:
            logger(f"❌ {str(index).zfill(3)} {title}, ({exc})")
        time.sleep(delay_seconds)

    return success_count


def _entry_key(entry: dict[str, str], source: ArticleSource) -> str:
    guid = entry.get("guid") or ""
    if guid:
        return guid
    markdown_url = _normalize_url(entry.get("markdown_url") or "", source.feed_url)
    if markdown_url:
        return markdown_url
    link = _normalize_url(entry.get("link") or "", source.feed_url)
    return link


def _collect_existing_keys(output_dir: Path) -> set[str]:
    keys: set[str] = set()
    for path in output_dir.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        frontmatter = _extract_frontmatter(text)
        for key in ("guid", "markdown_url", "url"):
            value = frontmatter.get(key)
            if value:
                keys.add(value)
    return keys


def _extract_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    frontmatter_text = parts[1]
    data: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        data[key.strip()] = value
    return data


def _write_markdown_file(
    entry: dict[str, str],
    index: int,
    output_dir: Path,
    html_parser: html2text.HTML2Text,
    source: ArticleSource,
) -> Path:
    url = _normalize_url(entry["link"], source.feed_url)
    title = entry["title"]
    markdown_url = _normalize_url(entry["markdown_url"], source.feed_url)
    description_raw = html.unescape(entry["description"])
    description = (
        _extract_description(html_parser.handle(description_raw)) if description_raw else ""
    )
    date_value = _normalize_date(entry["pub_date"])
    updated_value = _normalize_date(entry["updated"])
    author = entry["author"] or "Jason Cohen"
    guid = entry["guid"]

    if markdown_url:
        with urllib.request.urlopen(markdown_url, timeout=30) as website:
            content = website.read().decode("utf-8")
        parsed = content
    else:
        with urllib.request.urlopen(url, timeout=30) as website:
            content = website.read().decode("utf-8")
        parsed = html_parser.handle(content)
        if not description:
            description = _extract_description(parsed)
        if not date_value:
            date_value = _normalize_date(find_date(content))

    normalized_title = re.sub(r"[\W\s]+", "", "_".join(title.split(" ")).lower())
    footnote_prefix = str(index).zfill(3)

    output_path = output_dir / f"{str(index).zfill(3)}_{normalized_title}.md"
    with output_path.open("wb+") as file:
        frontmatter = "\n".join(
            [
                "---",
                f'title: "{_yaml_escape(title)}"',
                _yaml_field("description", description),
                f'date: "{date_value}"',
                f'updated: "{updated_value}"',
                f'author: "{_yaml_escape(author)}"',
                f'url: "{_yaml_escape(url)}"',
                f'markdown_url: "{_yaml_escape(markdown_url)}"',
                f'guid: "{_yaml_escape(guid)}"',
                "---",
                "",
            ]
        )
        file.write(frontmatter.encode())
        file.write(f"# {str(index).zfill(3)} {title}\n\n".encode())
        if markdown_url:
            file.write(_namespace_footnotes(parsed, footnote_prefix).encode())
        else:
            parsed = parsed.replace("[](index.html)  \n  \n", "")

            parsed_lines = [
                (
                    paragraph.replace("\n", " ")
                    if re.match(
                        r"^[\p{Z}\s]*(?:[^\p{Z}\s][\p{Z}\s]*){5,100}$",
                        paragraph,
                    )
                    else "\n" + paragraph + "\n"
                )
                for paragraph in parsed.split("\n")
            ]

            encoded = " ".join(parsed_lines).encode()
            processed_content = _convert_to_pandoc_footnotes(encoded)
            file.write(
                _namespace_footnotes(processed_content.decode("utf-8"), footnote_prefix).encode()
            )

    return output_path


def _write_csv_row(
    csv_path: Path,
    index: int,
    entry: dict[str, str],
    html_parser: html2text.HTML2Text,
    source: ArticleSource,
    output_filename: str,
) -> None:
    url = _normalize_url(entry["link"], source.feed_url)
    markdown_url = _normalize_url(entry["markdown_url"], source.feed_url)
    description_raw = html.unescape(entry["description"])
    description = (
        _extract_description(html_parser.handle(description_raw)) if description_raw else ""
    )
    date_value = _normalize_date(entry["pub_date"])
    updated_value = _normalize_date(entry["updated"])
    author = entry["author"] or "Jason Cohen"
    guid = entry["guid"]

    with csv_path.open("a+", newline="\n") as csv_file:
        csvwriter = csv.writer(csv_file, quoting=csv.QUOTE_MINIMAL, delimiter=",", quotechar='"')
        csvwriter.writerow(
            [
                str(index).zfill(3),
                entry["title"],
                description,
                date_value,
                updated_value,
                author,
                url,
                markdown_url,
                guid,
                output_filename,
            ]
        )
