# Contributing

Thank you for improving this project.

## Workflow

| Step | Rule |
| --- | --- |
| Branching | Create a short-lived branch from the target branch. |
| Scope | Keep each branch focused on one bug, feature, or documentation change. |
| Rebase | Rebase on the target branch before opening or updating the pull request. |
| Pull request | Open a pull request for every change to the target branch. |
| Review | Wait for maintainer review and passing CI before merge. |
| Merge style | Keep history linear; do not merge the target branch into the feature branch. |

Discuss larger changes in an issue before implementation. Use the repository's
pull request template when one is available.

## Development setup

```bash
poetry install
```

Add a dependency with:

```bash
poetry add <package>
```

## Local checks

| Check | Command |
| --- | --- |
| Format | `poetry run ruff format --check .` |
| Lint | `poetry run ruff check .` |
| Type check | `poetry run mypy src` |
| Tests | `poetry run python -m pytest` |

## Continuous integration

CI runs on pushes and pull requests for the capabilities included in this
repository.

| Stage | Runs when | What it does |
| --- | --- | --- |
| Metadata | metadata is included | Validate generated metadata files. |
| Documentation | documentation is included | Build the documentation. |
| Quality | quality tools are selected | Run applicable formatting, linting, and type checks. |
| Tests | test types or frameworks are selected | Run the selected test suite. |

The branch must be up to date with the target branch and all required stages
must pass before merge.

## Commit messages

Use Conventional Commits for commits that may be merged and for squash commit
titles.

| Prefix | Use for |
| --- | --- |
| `fix:` | Bug fixes |
| `feat:` | User-facing features |
| `docs:` | Documentation-only changes |
| `test:` | Tests |
| `refactor:` | Code changes without user-facing behavior changes |
| `build:` | Build, packaging, or dependency changes |
| `ci:` | Continuous integration changes |
| `chore:` | Maintenance that does not affect users |

An optional scope may clarify the affected component. Mark breaking changes
with `!` or a `BREAKING CHANGE:` footer.

## Pull request checklist

- [ ] The branch is rebased on the target branch.
- [ ] The pull request title follows Conventional Commits.
- [ ] The change is focused and linked to an issue or decision when relevant.
- [ ] Metadata is updated when public project information changed.
- [ ] Documentation is updated when installation, usage, configuration, or behavior changed.
- [ ] Tests are added or updated for behavior changes.
- [ ] Applicable local checks pass.
- [ ] CI passes on the latest commit.
- [ ] No secrets, private data, or non-public security details are included.

## Documentation checks

```bash
poetry install --extras "docs"
poetry run zensical build --strict
```
