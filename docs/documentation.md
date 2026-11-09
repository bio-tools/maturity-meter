# Build and view the documentation

Install the documentation dependencies:

```bash
poetry install --extras "docs"
```

Preview the documentation locally:

```bash
poetry run zensical serve
```

Build the static site and treat warnings as errors:

```bash
poetry run zensical build --strict
```

The local preview is available at <http://127.0.0.1:8000/> by default. The
static site is written to `site/`.
