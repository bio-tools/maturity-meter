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


def is_bioconda_file(name: str) -> bool:
    return name.startswith("bioconda_") and name.endswith(".yaml")


# Continuous integration configuration (paths relative to the repository root).
CI_CONFIG_FILES = {
    ".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml", "jenkinsfile",
    "bitbucket-pipelines.yml", "appveyor.yml", ".appveyor.yml",
}  # fmt: skip
CI_CONFIG_DIRS = (".github/workflows/", ".circleci/", ".woodpecker/")

# Python packaging files (a package can be built from the repository).
PYTHON_PACKAGING_FILES = {"pyproject.toml", "setup.py", "setup.cfg"}


def is_ci_config(path: str) -> bool:
    """A continuous integration configuration file."""
    return path in CI_CONFIG_FILES or path.startswith(CI_CONFIG_DIRS)


def is_workflow_file(path: str) -> bool:
    """A workflow-manager file: Snakemake, Nextflow, CWL or WDL."""
    name = PurePosixPath(path).name
    return name in ("snakefile", "nextflow.config") or name.endswith(
        (".smk", ".nf", ".cwl", ".wdl")
    )
