# Developer guide

## Setup and checks

```bash
poetry install --all-extras
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy src
poetry run pytest
```

See `CONTRIBUTING.md` for the contribution policy.

## Architecture

The package uses a `src` layout. Entry points call adapters, and adapters call
services; services must not import adapters.

```text
adapters/  ->  services/
```

## Documentation

```bash
poetry install --extras "docs"
poetry run zensical serve            # preview at http://127.0.0.1:8000/
poetry run zensical build --strict   # build, warnings as errors
```

The docs workflow deploys to GitHub Pages from the default branch only. Select
**GitHub Actions** as the Pages build source in the repository settings first.

## Releases

`pyproject.toml` is the source of truth for the version (SemVer). Update
`project.version`, then run the metadata, test, and docs checks.
