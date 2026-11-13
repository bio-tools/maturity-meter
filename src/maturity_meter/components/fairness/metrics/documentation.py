"""FAIRness metrics on documentation and installation."""

from maturity_meter.components.utils.checks import (
    Aspect,
    aspect_metric,
    resqui_verdict,
)
from maturity_meter.components.utils.files import (
    BUILD_FILES,
    DEPENDENCY_MANIFESTS,
)
from maturity_meter.components.utils.sources import (
    biotools_has,
    biotools_types,
    file_name,
    has_file,
    openebench_metric,
    readme_matches,
    repo_record,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult

# OpenEBench documentation checks; any of them counts as documentation.
_OPENEBENCH_DOCS = (
    "project.documentation.general",
    "project.documentation.manual",
    "project.documentation.api",
    "project.documentation.training_material",
    "project.documentation.help",
    "project.documentation.faq",
    "project.documentation.terms_of_use",
)


def _openebench_docs(data: IngestedData) -> float | None:
    """1 if OpenEBench reports any documentation, None if it reports none.

    OpenEBench lists only the documentation it found, so a missing kind
    means "not found by OpenEBench" rather than a verified absence.
    """
    found = [openebench_metric(data, path) for path in _OPENEBENCH_DOCS]
    return 1.0 if any(found) else None


def documentation(data: IngestedData) -> MetricResult:
    """Whether documentation, including a description of the purpose, exists.

    Aspects and their sources:

    - user documentation: a README, a ``docs/`` folder, GitHub Pages,
      documentation links in bio.tools, OpenEBench's documentation checks
      (general, manual, API, training material, help, FAQ, terms of
      use) and README checks,
      and the RSFC and OEBFAIR ``software_has_documentation`` checks;
    - purpose: the GitHub/GitLab description, the bio.tools description and
      OpenEBench's description check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    repository = data.repository
    repo = repo_record(data)
    return aspect_metric(
        "documentation",
        {
            "user documentation": Aspect(
                {
                    "README": verdict(repository.get("readme"))
                    if "readme" in repository
                    else None,
                    "docs folder": has_file(
                        data, lambda f: f.startswith(("docs/", "doc/"))
                    ),
                    "GitHub Pages": verdict(repository.get("github_pages"))
                    if "github_pages" in repository
                    else None,
                    "bio.tools documentation": biotools_has(data, "documentation"),
                    "OpenEBench documentation": _openebench_docs(data),
                    "OpenEBench README": verdict(
                        openebench_metric(data, "project.readme")
                    ),
                    "RSFC/OEBFAIR": resqui_verdict(data, "software_has_documentation"),
                },
                "Write a README and user documentation.",
            ),
            "purpose": Aspect(
                {
                    "repository description": None
                    if repo is None
                    else verdict(repo.get("description")),
                    "bio.tools description": biotools_has(data, "description"),
                    "OpenEBench": verdict(
                        openebench_metric(data, "project.summary.description")
                    ),
                },
                "Describe what the software does and what it is for.",
            ),
        },
    )


def installation_instructions(data: IngestedData) -> MetricResult:
    """Whether users can install and build the software.

    Aspects and their sources:

    - instructions: an installation section in the README and installation
      docs in bio.tools;
    - dependencies: a dependency manifest and RSFC's ``requirements_specified``
      check;
    - build: a build configuration (Makefile, CMake, pyproject.toml, ...) and
      OpenEBench's build information.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    docs = biotools_types(data, "documentation")
    return aspect_metric(
        "installation_instructions",
        {
            "instructions": Aspect(
                {
                    "README": readme_matches(data, r"\binstall"),
                    "bio.tools installation docs": None
                    if docs is None
                    else float("Installation instructions" in docs),
                },
                "Add installation instructions to the README.",
            ),
            "dependencies": Aspect(
                {
                    "dependency manifest": has_file(
                        data, lambda f: file_name(f) in DEPENDENCY_MANIFESTS
                    ),
                    "RSFC": resqui_verdict(data, "requirements_specified"),
                },
                "Declare the dependencies (e.g. in requirements.txt).",
            ),
            "build": Aspect(
                {
                    "build configuration": has_file(
                        data, lambda f: file_name(f) in BUILD_FILES
                    ),
                    "OpenEBench": verdict(openebench_metric(data, "project.build")),
                },
                "Add a build configuration (e.g. a Makefile or pyproject.toml).",
            ),
        },
    )
