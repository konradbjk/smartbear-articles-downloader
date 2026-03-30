# SmartBear Longform Collection

This is the maintained version at `https://github.com/konradbjk/smartbear-articles-downloader`.
It is based on the original project and keeps the same spirit,
while modernizing the tooling and CLI for SmartBear Longform.

![cover](cover.png)

> "If you are not embarrassed by the first version of your product, you've launched too late."

---

Download the complete collection of SmartBear Longform articles and export them in EPUB and Markdown for easy reading.
The RSS feed includes markdown links for each article and richer metadata.

## Dependencies for MacOS

On macOS you need [brew] in order to install the external tools used by the CLI, e.g.:

```bash
brew install uv pandoc calibre
```

## Usage

Install Python dependencies with `uv`:

```bash
uv venv .venv
uv sync
```

Run the CLI:

```bash
uv run smartbear-articles fetch
uv run smartbear-articles merge
uv run smartbear-articles epub
uv run smartbear-articles pdf
uv run smartbear-articles wordcount
```

`fetch` downloads article markdown and metadata only.
`merge`, `epub`, and `pdf` are export steps you can run separately when needed.

Or run everything at once:

```bash
uv run smartbear-articles all
```

See all commands:

```bash
uv run smartbear-articles --help
```

### Metadata Exports

Each markdown file includes YAML frontmatter with `title`, `description`, `date`, `updated`, `author`, `url`, `markdown_url`, and `guid`.
The `fetch` command also writes `articles.csv` with columns:

- Article no.
- Title
- Description
- Date
- Updated
- Author
- URL
- Markdown URL
- Guid
- Filename

You can disable the CSV or choose a different path:

```bash
uv run smartbear-articles fetch --no-csv
uv run smartbear-articles fetch --csv-path data/articles.csv
```

### External Tools

Only the export commands rely on external tools:

- `pandoc` (for `merge` and `epub`)
- `calibre` (for `pdf`, which uses `ebook-convert`)

### Current Articles

Here's the current list of articles and EPUB in the project outputs after you run the CLI.

---

_If you have any ideas, suggestions, curses or feedback in order to improve the code, please don't hesitate in opening an issue or PR. They'll be very welcomed!_

[afk]: https://www.grammarly.com/blog/afk-meaning/
[smartbear longform]: https://longform.asmartbear.com/
[brew]: https://docs.brew.sh/Installation
[pandoc]: https://pandoc.org/installing.html
[calibre]: https://calibre-ebook.com/
