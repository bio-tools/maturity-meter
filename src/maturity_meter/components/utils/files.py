"""Repository file patterns the metrics look for (manifests, build and
linter configuration, tests, containers and packages)."""

from pathlib import PurePosixPath

# Files that declare a project's dependencies, by ecosystem.
DEPENDENCY_MANIFESTS = {
    "requirements.txt",  # Python
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "environment.yml",  # conda
    "environment.yaml",
    "package.json",  # JavaScript
    "description",  # R
    "renv.lock",
    "cargo.toml",  # Rust
    "go.mod",  # Go
    "pom.xml",  # Java
    "build.gradle",
    "build.gradle.kts",
    "gemfile",  # Ruby
    "cpanfile",  # Perl
    "project.toml",  # Julia
    "conanfile.txt",  # C/C++
    "vcpkg.json",
}


# Configuration files of dependency update tools (Dependabot, Renovate).
DEPENDENCY_UPDATE_FILES = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "renovate.json",
    "renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".github/renovate.json",
    ".github/renovate.json5",
    ".gitlab/renovate.json",
)


BUILD_FILES = {
    "makefile", "cmakelists.txt", "configure", "configure.ac", "meson.build",
    "pyproject.toml", "setup.py", "pom.xml", "build.gradle", "build.gradle.kts",
    "cargo.toml", "go.mod", "package.json", "description", "snakefile", "justfile",
}  # fmt: skip


LINTER_FILES = {
    ".pre-commit-config.yaml", ".flake8", "ruff.toml", ".ruff.toml", ".pylintrc",
    ".golangci.yml", ".golangci.yaml", ".lintr", ".clang-tidy", ".clang-format",
    ".rubocop.yml", ".prettierrc", "biome.json", ".markdownlint.yaml",
}  # fmt: skip


def is_test_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else ""
    return (
        any(p in ("test", "tests", "testing", "__tests__", "spec") for p in parts[:-1])
        or name.startswith("test_")
        or "_test." in name
        or ".test." in name
    )


def is_distribution_file(path: str) -> bool:
    """A Dockerfile/Containerfile or a conda recipe (``meta.yaml``)."""
    name = PurePosixPath(path.lower()).name
    return name.startswith(("dockerfile", "containerfile")) or name == "meta.yaml"


def is_bioconda_file(name: str) -> bool:
    return name.startswith("bioconda_") and name.endswith(".yaml")


def is_biocontainers_file(name: str) -> bool:
    return name.endswith("biocontainers.yaml")
