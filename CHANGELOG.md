# Changelog

## [Unreleased]
### Changed
- Moved merge, EPUB, and PDF generation into a separate export module so fetching stays focused on downloading article content and metadata.
- Updated the project documentation to point to `konradbjk/smartbear-articles-downloader` and clarified that export commands are separate from fetching.

### Fixed
- Preserved longer RSS descriptions in exported metadata instead of truncating them to the first matching line.
- Stopped wrapping single-sentence descriptions across multiple YAML lines in generated markdown frontmatter.
- Namespaced article footnote labels to avoid collisions when merging all articles into one document.
