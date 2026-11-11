"""FAIRness metrics.

One metric per merged indicator of the FAIRness sheet. Most are yes/no checks
that several sources answer (repository files and record, README, bio.tools,
OpenEBench, publications, RSEc and resqui checks); their verdicts are combined
with :func:`placeholder_reconcile` via :func:`verdict_metric`, so every source
with data contributes and the note names each one's verdict.
"""

import re
from pathlib import PurePosixPath
from typing import Any

from maturity_meter.components.utils.checks import resqui_verdict, verdict_metric
from maturity_meter.components.utils.scaling import placeholder_reconcile
from maturity_meter.models import IngestedData, MetricResult

# --- source accessors -----------------------------------------------------------


def _verdict(value: Any) -> float | None:
    """1.0 for a truthy value, 0.0 for a falsy one, None when unknown."""
    return None if value is None else float(bool(value))


def _repo(data: IngestedData) -> dict[str, Any] | None:
    """The GitHub/GitLab repository record, or None if not ingested."""
    record: dict[str, Any] | None = data.repository.get("repo")
    return record


def _files(data: IngestedData) -> list[str] | None:
    """Lower-cased repository file paths, or None without a file list."""
    files = data.repository.get("files")
    return None if files is None else [str(f).lower() for f in files]


def _has_file(data: IngestedData, matches: Any) -> float | None:
    """Whether any repository file path matches ``matches(path)``."""
    files = _files(data)
    return None if files is None else float(any(matches(f) for f in files))


def _name(path: str) -> str:
    return PurePosixPath(path).name


def _readme_has(data: IngestedData, pattern: str) -> float | None:
    """Whether the README matches ``pattern`` (case-insensitive)."""
    readme = data.repository.get("readme")
    if readme is None:
        return None
    return float(re.search(pattern, str(readme), re.IGNORECASE) is not None)


def _biotools(data: IngestedData) -> dict[str, Any] | None:
    return data.biotools


def _biotools_has(data: IngestedData, key: str) -> float | None:
    """Whether the bio.tools entry has a non-empty ``key``."""
    entry = _biotools(data)
    return None if entry is None else _verdict(entry.get(key))


def _biotools_types(data: IngestedData, key: str) -> set[str] | None:
    """All ``type`` values of a bio.tools list (e.g. documentation, links)."""
    entry = _biotools(data)
    if entry is None:
        return None
    types: set[str] = set()
    for item in entry.get(key) or []:
        kinds = item.get("type")
        types.update(kinds if isinstance(kinds, list) else [kinds])
    return {str(t) for t in types if t}


def _openebench(data: IngestedData, path: str) -> Any:
    """A value from the OpenEBench metrics by dotted path, or None."""
    value: Any = (data.openebench or {}).get("metrics")
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    # Empty objects mean OpenEBench has no data for that part.
    return None if value == {} else value


def _openebench_tool(data: IngestedData, key: str) -> float | None:
    """Whether the OpenEBench tool record has a non-empty ``key``."""
    tool = (data.openebench or {}).get("tool")
    return None if tool is None else _verdict(tool.get(key))


def _registry_lookup(data: IngestedData, source: Any) -> float | None:
    """Whether a registry source (looked up by bio.tools ID) has an entry.

    Without a bio.tools ID nothing was looked up, so the answer is unknown.
    """
    if not data.request.biotools_id:
        return None
    return float(source is not None)


# --- licensing --------------------------------------------------------------------

# Common OSI-approved licences (SPDX identifiers, without -only/-or-later).
OSI_LICENSES = {
    "0bsd", "afl-3.0", "agpl-3.0", "apache-2.0", "artistic-2.0", "bsd-2-clause",
    "bsd-3-clause", "bsl-1.0", "cddl-1.0", "cecill-2.1", "ecl-2.0", "epl-1.0",
    "epl-2.0", "eupl-1.1", "eupl-1.2", "gpl-2.0", "gpl-3.0", "isc", "lgpl-2.1",
    "lgpl-3.0", "lppl-1.3c", "mit", "mit-0", "mpl-1.1", "mpl-2.0", "ms-pl", "ms-rl",
    "ncsa", "osl-3.0", "postgresql", "unlicense", "upl-1.0", "zlib",
}  # fmt: skip


def _spdx(value: Any) -> str | None:
    """Normalized SPDX id of a licence (string or GitHub/GitLab object)."""
    if isinstance(value, dict):
        value = value.get("spdx_id") or value.get("key")
    if not value or str(value).upper() in ("NOASSERTION", "OTHER"):
        return None
    text = str(value).lower()
    for suffix in ("-only", "-or-later", "+"):
        text = text.removesuffix(suffix)
    return text


def _osi(value: Any) -> float | None:
    """Whether a licence is OSI-approved; None if unknown."""
    spdx = _spdx(value)
    return None if spdx is None else float(spdx in OSI_LICENSES)


def license_declaration(data: IngestedData) -> MetricResult:
    """Whether the software declares a licence.

    Sources: the GitHub/GitLab licence, a LICENSE/COPYING file, the bio.tools
    and OpenEBench licences, and resqui's ``software_has_license`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = _repo(data)
    return verdict_metric(
        "license_declaration",
        {
            "repository licence": None
            if repo is None
            else _verdict(repo.get("license")),
            "LICENSE file": _has_file(
                data, lambda f: _name(f).startswith(("license", "licence", "copying"))
            ),
            "bio.tools": _biotools_has(data, "license"),
            "OpenEBench": _openebench_tool(data, "license"),
            "resqui check": resqui_verdict(data, "software_has_license"),
        },
        suggestion="Add a LICENSE file with an open-source licence.",
    )


def per_file_licensing(data: IngestedData) -> MetricResult:
    """Whether individual files carry licence information (e.g. REUSE).

    Sources: a REUSE setup in the repository (``REUSE.toml``, ``.reuse/dep5``
    or a ``LICENSES/`` folder) and resqui's
    ``software_has_license_for_file_types`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "per_file_licensing",
        {
            "REUSE setup": _has_file(
                data,
                lambda f: (
                    f in ("reuse.toml", ".reuse/dep5") or f.startswith("licenses/")
                ),
            ),
            "resqui check": resqui_verdict(data, "software_has_license_for_file_types"),
        },
        suggestion="Add SPDX licence headers to the files (e.g. with REUSE).",
    )


def open_source_license(data: IngestedData) -> MetricResult:
    """Whether the licence is an OSI-approved open-source licence.

    Sources: OpenEBench's OSI check, and the GitHub/GitLab and bio.tools
    licences looked up in a list of common OSI-approved licences.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no licence is known.
    """
    repo = _repo(data) or {}
    return verdict_metric(
        "open_source_license",
        {
            "OpenEBench": _verdict(_openebench(data, "project.license.osi")),
            "repository licence": _osi(repo.get("license")),
            "bio.tools licence": _osi((_biotools(data) or {}).get("license")),
        },
        yes="OSI-approved",
        no="not OSI-approved",
        suggestion="Use an OSI-approved open-source licence.",
        missing="No licence known.",
    )


def copyright_and_attribution(data: IngestedData) -> MetricResult:
    """Whether copyright and credits (who made it) are stated.

    Sources: OpenEBench's website copyright check, credits in bio.tools and
    OpenEBench, and an AUTHORS/CONTRIBUTORS/CITATION file.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "copyright_and_attribution",
        {
            "website copyright (OpenEBench)": _verdict(
                _openebench(data, "project.website.copyright")
            ),
            "credits (bio.tools)": _biotools_has(data, "credit"),
            "credits (OpenEBench)": _openebench_tool(data, "credits"),
            "AUTHORS/CITATION file": _has_file(
                data,
                lambda f: (
                    _name(f).startswith(("authors", "contributors", "credits"))
                    or _name(f) == "citation.cff"
                ),
            ),
        },
        suggestion="State the authors, funders and copyright (e.g. an AUTHORS file).",
    )


# --- citation and publications -------------------------------------------------


def citation_information(data: IngestedData) -> MetricResult:
    """Whether users are told how to cite the software.

    Sources: a CITATION file (e.g. ``CITATION.cff``), resqui's
    ``software_has_citation`` check, OpenEBench's citation check and a
    citation section in the README.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "citation_information",
        {
            "CITATION file": _has_file(data, lambda f: _name(f).startswith("citation")),
            "resqui check": resqui_verdict(data, "software_has_citation"),
            "OpenEBench": _verdict(_openebench(data, "project.documentation.citation")),
            "README": _readme_has(data, r"\bcit(e|ing|ation)\b"),
        },
        suggestion="Add a CITATION.cff file describing how to cite the software.",
    )


def _open_access(data: IngestedData) -> dict[str, float | None]:
    """Open-access verdict per publication (DOI), reconciled across sources."""
    verdicts: dict[str, list[float | None]] = {}
    for doi, record in data.europe_pmc.items():
        if record is not None and record.get("isOpenAccess") is not None:
            verdicts.setdefault(doi.lower(), []).append(
                float(record["isOpenAccess"] == "Y")
            )
    for doi, work in data.openalex.items():
        oa = ((work or {}).get("open_access") or {}).get("is_oa")
        if oa is not None:
            verdicts.setdefault(doi.lower(), []).append(float(oa))
    return {doi: placeholder_reconcile(v) for doi, v in verdicts.items()}


def _publication_dois(data: IngestedData) -> set[str]:
    """DOIs of all known publications: request, bio.tools and OpenEBench."""
    dois = {doi.lower() for doi in data.request.dois}
    for publication in (_biotools(data) or {}).get("publication") or []:
        if publication.get("doi"):
            dois.add(str(publication["doi"]).lower())
    for publication in _openebench(data, "project.publications") or []:
        for entry in publication.get("entries") or []:
            if entry.get("doi"):
                dois.add(str(entry["doi"]).lower())
    return dois


def publications_open_access(data: IngestedData) -> MetricResult:
    """Whether publications describe the software, and are open access.

    Publications come from the request's DOIs, bio.tools and OpenEBench; the
    open-access status from Europe PMC and OpenAlex. The score reconciles
    "has publications" with the share of open-access publications.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled score.
    """
    dois = _publication_dois(data)
    if not dois and data.biotools is None and data.openebench is None:
        # Nowhere to look for publications: not assessed rather than none.
        return MetricResult(
            name="publications_open_access",
            value=None,
            note="No DOIs given and no bio.tools entry to list publications.",
            suggestions=["Add the DOIs of publications describing the software."],
        )
    if not dois:
        return MetricResult(
            name="publications_open_access",
            value=0.0,
            note="No publications found.",
            suggestions=[
                "Publish a paper about the software and list it in bio.tools."
            ],
        )
    access = _open_access(data)
    known = [v for v in access.values() if v is not None]
    share = sum(known) / len(known) if known else None
    value = placeholder_reconcile([1.0, share])
    note = f"{len(dois)} publication(s)"
    note += (
        f"; {sum(known):g} of {len(known)} with known status are open access."
        if known
        else "; open-access status unknown (add their DOIs to look it up)."
    )
    return MetricResult(
        name="publications_open_access",
        value=value,
        note=note,
        suggestions=[]
        if share in (None, 1.0)
        else ["Make the publications open access."],
    )


# --- findability and metadata -----------------------------------------------------


def registry_listing(data: IngestedData) -> MetricResult:
    """Whether the software is listed in research software registries.

    Sources: entries in bio.tools, OpenEBench and RSEc for the bio.tools ID,
    registry badges in the README, and resqui's ``listed_in_registry`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "registry_listing",
        {
            "bio.tools": _registry_lookup(data, data.biotools),
            "OpenEBench": _registry_lookup(data, data.openebench),
            "RSEc": _registry_lookup(data, data.rsec),
            "README registry badge": _readme_has(
                data, r"bio\.tools/|research-software-directory|rsd\.|biocontainers"
            ),
            "resqui check": resqui_verdict(data, "listed_in_registry"),
        },
        suggestion="Register the software in bio.tools.",
        missing="No bio.tools ID or README to check.",
    )


def persistent_identifier(data: IngestedData) -> MetricResult:
    """Whether the software has a persistent, unique identifier.

    Sources: a software DOI (Zenodo) or Software Heritage ID in the README,
    the bio.tools ID, and resqui's ``persistent_and_unique_identifier`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "persistent_identifier",
        {
            "software DOI/SWHID in README": _readme_has(
                data, r"10\.5281/zenodo\.\d+|swh:1:"
            ),
            "bio.tools ID": _registry_lookup(data, data.biotools),
            "resqui check": resqui_verdict(data, "persistent_and_unique_identifier"),
        },
        suggestion="Archive releases on Zenodo to get a DOI.",
    )


def structured_metadata(data: IngestedData) -> MetricResult:
    """Whether machine-readable descriptive metadata is available.

    Sources: ``codemeta.json`` and ``CITATION.cff`` files, the bio.tools entry,
    and resqui's ``descriptive_metadata`` and ``codemeta_completeness`` checks.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "structured_metadata",
        {
            "codemeta.json": _has_file(data, lambda f: _name(f) == "codemeta.json"),
            "CITATION.cff": _has_file(data, lambda f: _name(f) == "citation.cff"),
            "bio.tools entry": _registry_lookup(data, data.biotools),
            "resqui descriptive metadata": resqui_verdict(data, "descriptive_metadata"),
            "resqui CodeMeta completeness": resqui_verdict(
                data, "codemeta_completeness"
            ),
        },
        suggestion="Add a codemeta.json describing the software.",
    )


def semantic_annotation(data: IngestedData) -> MetricResult:
    """Whether the metadata uses community vocabularies (EDAM, Bioschemas).

    Sources: EDAM topics and operations in the bio.tools entry, and
    OpenEBench's Bioschemas check of the website.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    entry = _biotools(data)
    operations = (
        None
        if entry is None
        else float(any(f.get("operation") for f in entry.get("function") or []))
    )
    return verdict_metric(
        "semantic_annotation",
        {
            "EDAM topics (bio.tools)": _biotools_has(data, "topic"),
            "EDAM operations (bio.tools)": operations,
            "Bioschemas (OpenEBench)": _verdict(
                _openebench(data, "project.website.bioschemas")
            ),
        },
        suggestion="Annotate the bio.tools entry with EDAM topics and operations.",
        missing="No bio.tools entry or OpenEBench data.",
    )


# --- documentation ----------------------------------------------------------------


def documentation(data: IngestedData) -> MetricResult:
    """Whether documentation is available.

    Sources: a README, a ``docs/`` folder, GitHub Pages, documentation links
    in bio.tools, OpenEBench's documentation checks and resqui's
    ``software_has_documentation`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repository = data.repository
    return verdict_metric(
        "documentation",
        {
            "README": _verdict(repository.get("readme"))
            if "readme" in repository
            else None,
            "docs folder": _has_file(data, lambda f: f.startswith(("docs/", "doc/"))),
            "GitHub Pages": _verdict(repository.get("github_pages"))
            if "github_pages" in repository
            else None,
            "bio.tools documentation": _biotools_has(data, "documentation"),
            "OpenEBench": _verdict(
                _openebench(data, "project.documentation.general")
                or _openebench(data, "project.documentation.manual")
            ),
            "resqui check": resqui_verdict(data, "software_has_documentation"),
        },
        suggestion="Write a README and user documentation.",
    )


def purpose_description(data: IngestedData) -> MetricResult:
    """Whether a description of what the software is for is available.

    Sources: the GitHub/GitLab description, the bio.tools description and
    OpenEBench's description check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = _repo(data)
    return verdict_metric(
        "purpose_description",
        {
            "repository description": None
            if repo is None
            else _verdict(repo.get("description")),
            "bio.tools description": _biotools_has(data, "description"),
            "OpenEBench": _verdict(_openebench(data, "project.summary.description")),
        },
        suggestion="Describe what the software does and what it is for.",
    )


# Files that declare a project's dependencies.
_MANIFESTS = {
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "pipfile",
    "environment.yml", "environment.yaml", "package.json", "description",
    "renv.lock", "cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "build.gradle.kts", "gemfile", "cpanfile", "project.toml", "conanfile.txt",
    "vcpkg.json",
}  # fmt: skip


def installation_instructions(data: IngestedData) -> MetricResult:
    """Whether installation and dependency information is provided.

    Sources: an installation section in the README, installation docs in
    bio.tools, a dependency manifest, and resqui's ``requirements_specified``
    check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    docs = _biotools_types(data, "documentation")
    return verdict_metric(
        "installation_instructions",
        {
            "README": _readme_has(data, r"\binstall"),
            "bio.tools installation docs": None
            if docs is None
            else float("Installation instructions" in docs),
            "dependency manifest": _has_file(data, lambda f: _name(f) in _MANIFESTS),
            "resqui check": resqui_verdict(data, "requirements_specified"),
        },
        suggestion="Add installation instructions and the dependencies to the README.",
    )


# --- source code and releases ----------------------------------------------------


def version_control(data: IngestedData) -> MetricResult:
    """Whether the source is under version control in a public repository.

    Sources: the GitHub/GitLab repository itself, OpenEBench's online
    repository check and resqui's ``version_control_use`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict.
    """
    return verdict_metric(
        "version_control",
        {
            # A repository record means it is hosted on GitHub/GitLab; without
            # one (not ingested) the answer is unknown, not "no".
            "GitHub/GitLab repository": None if _repo(data) is None else 1.0,
            "OpenEBench": _verdict(
                _openebench(data, "distribution.sourcecode.repository.online")
            ),
            "resqui check": resqui_verdict(data, "version_control_use"),
        },
        suggestion="Develop the software in a public version-controlled repository.",
    )


_VERSION_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)?([-.+][\w.]+)?$", re.IGNORECASE)


def releases_and_versioning(data: IngestedData) -> MetricResult:
    """Whether there are releases with conventional version numbers.

    Sources: the latest GitHub/GitLab release and whether its tag looks like a
    version (e.g. ``v1.2.3``), and resqui's ``has_releases`` and
    ``versioning_standards_use`` checks.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repository = data.repository
    latest = repository.get("latest_release")
    known = "latest_release" in repository
    tag = str((latest or {}).get("tag_name") or "")
    return verdict_metric(
        "releases_and_versioning",
        {
            "repository releases": _verdict(latest) if known else None,
            "version-like tag": float(bool(_VERSION_TAG.match(tag))) if tag else None,
            "resqui releases check": resqui_verdict(data, "has_releases"),
            "resqui versioning check": resqui_verdict(data, "versioning_standards_use"),
        },
        suggestion="Publish releases tagged with version numbers (e.g. v1.2.3).",
    )


_BUILD_FILES = {
    "makefile", "cmakelists.txt", "configure", "configure.ac", "meson.build",
    "pyproject.toml", "setup.py", "pom.xml", "build.gradle", "build.gradle.kts",
    "cargo.toml", "go.mod", "package.json", "description", "snakefile", "justfile",
}  # fmt: skip


def automated_build(data: IngestedData) -> MetricResult:
    """Whether an automated build system is configured.

    Sources: build configuration files (Makefile, CMake, pyproject.toml, ...)
    and OpenEBench's build information.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "automated_build",
        {
            "build configuration": _has_file(data, lambda f: _name(f) in _BUILD_FILES),
            "OpenEBench": _verdict(_openebench(data, "project.build")),
        },
        suggestion="Add a build configuration (e.g. a Makefile or pyproject.toml).",
    )


def _is_test_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else ""
    return (
        any(p in ("test", "tests", "testing", "__tests__", "spec") for p in parts[:-1])
        or name.startswith("test_")
        or "_test." in name
        or ".test." in name
    )


def software_tests(data: IngestedData) -> MetricResult:
    """Whether the software comes with tests.

    Sources: test files or folders in the repository and resqui's
    ``software_has_tests`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "software_tests",
        {
            "test files": _has_file(data, _is_test_path),
            "resqui check": resqui_verdict(data, "software_has_tests"),
        },
        suggestion="Add automated tests.",
    )


def source_availability(data: IngestedData) -> MetricResult:
    """Whether the source code is publicly and freely available.

    Sources: the repository's visibility, OpenEBench's public and free source
    checks, and source-code downloads in bio.tools.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = _repo(data)
    downloads = _biotools_types(data, "download")
    return verdict_metric(
        "source_availability",
        {
            "public repository": None
            if repo is None
            else float(
                repo.get("visibility") == "public" or repo.get("private") is False
            ),
            "OpenEBench public source": _verdict(
                _openebench(data, "distribution.sourcecode.public")
            ),
            "OpenEBench free source": _verdict(
                _openebench(data, "distribution.sourcecode.free")
            ),
            "bio.tools source download": None
            if downloads is None
            else float("Source code" in downloads),
        },
        suggestion="Make the source code publicly available.",
    )


def binary_distribution(data: IngestedData) -> MetricResult:
    """Whether ready-to-use binaries or packages are distributed.

    Sources: assets of the latest GitHub/GitLab release, binary downloads in
    bio.tools, OpenEBench's binary and package checks, and Bioconda (RSEc).

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repository = data.repository
    assets = None
    if "latest_release" in repository:
        latest = repository.get("latest_release") or {}
        release_assets = latest.get("assets")
        # GitHub lists assets directly; GitLab under assets.links (its
        # assets.sources are the automatic source archives).
        if isinstance(release_assets, dict):
            release_assets = release_assets.get("links")
        assets = float(bool(release_assets))
    downloads = _biotools_types(data, "download")
    rsec_files = None if data.rsec is None else data.rsec.get("files") or []
    return verdict_metric(
        "binary_distribution",
        {
            "release assets": assets,
            "bio.tools binaries": None
            if downloads is None
            else float("Binaries" in downloads),
            "OpenEBench free binaries": _verdict(
                _openebench(data, "distribution.binaries.freeness")
            ),
            "OpenEBench packages": _verdict(_openebench(data, "distribution.packages")),
            "Bioconda (RSEc)": None
            if rsec_files is None
            else float(any(str(f).lower().startswith("bioconda_") for f in rsec_files)),
        },
        suggestion="Distribute binaries or packages (e.g. release assets, Bioconda).",
    )


def source_archival(data: IngestedData) -> MetricResult:
    """Whether the source is archived for the long term.

    Sources: Zenodo and Software Heritage references in the README, and
    resqui's ``archived_in_software_heritage`` and
    ``archived_in_scholarly_repository`` checks.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "source_archival",
        {
            "Zenodo in README": _readme_has(data, r"zenodo\.org|10\.5281/zenodo"),
            "Software Heritage in README": _readme_has(
                data, r"softwareheritage\.org|swh:1:"
            ),
            "resqui Software Heritage check": resqui_verdict(
                data, "archived_in_software_heritage"
            ),
            "resqui scholarly repository check": resqui_verdict(
                data, "archived_in_scholarly_repository"
            ),
        },
        suggestion="Archive the source code in Software Heritage and on Zenodo.",
    )


# --- quality and community ------------------------------------------------------

_LINTER_FILES = {
    ".pre-commit-config.yaml", ".flake8", "ruff.toml", ".ruff.toml", ".pylintrc",
    ".golangci.yml", ".golangci.yaml", ".lintr", ".clang-tidy", ".clang-format",
    ".rubocop.yml", ".prettierrc", "biome.json", ".markdownlint.yaml",
}  # fmt: skip


def code_quality_tooling(data: IngestedData) -> MetricResult:
    """Whether linters or static analysis are used and pass.

    Sources: linter and formatter configuration files, and resqui's
    ``has_no_linting_issues`` and ``uses_tool_for_warnings_and_mistakes``
    checks.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "code_quality_tooling",
        {
            "linter configuration": _has_file(
                data,
                lambda f: _name(f) in _LINTER_FILES or _name(f).startswith(".eslintrc"),
            ),
            "resqui linting check": resqui_verdict(data, "has_no_linting_issues"),
            "resqui static analysis check": resqui_verdict(
                data, "uses_tool_for_warnings_and_mistakes"
            ),
        },
        suggestion="Use linters or static analysis (e.g. via pre-commit).",
    )


def issue_tracking(data: IngestedData) -> MetricResult:
    """Whether users can report issues in a public tracker.

    Sources: the GitHub/GitLab issue tracker, OpenEBench's public tracker check
    and an issue-tracker link in bio.tools.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = _repo(data) or {}
    if "has_issues" in repo:
        tracker = _verdict(repo.get("has_issues"))
    else:
        # GitLab: issue statistics are only available when issues are enabled.
        tracker = None if data.repository.get("open_issues") is None else 1.0
    links = _biotools_types(data, "link")
    return verdict_metric(
        "issue_tracking",
        {
            "repository issues": tracker,
            "OpenEBench": _verdict(
                _openebench(data, "support.issue_tracking.public_tracker")
            ),
            "bio.tools link": None
            if links is None
            else float("Issue tracker" in links),
        },
        suggestion="Enable a public issue tracker.",
    )


def project_website(data: IngestedData) -> MetricResult:
    """Whether the software has its own website.

    Sources: the GitHub homepage field, GitHub Pages, a bio.tools homepage
    other than the repository, and OpenEBench's website check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = _repo(data) or {}
    repository = data.repository
    homepage = (_biotools(data) or {}).get("homepage")
    repo_url = data.request.repository.rstrip("/").lower()
    operational = _openebench(data, "project.website.operational")
    return verdict_metric(
        "project_website",
        {
            "repository homepage": _verdict(repo.get("homepage"))
            if "homepage" in repo
            else None,
            "GitHub Pages": _verdict(repository.get("github_pages"))
            if "github_pages" in repository
            else None,
            "bio.tools homepage": None
            if _biotools(data) is None
            else float(
                bool(homepage) and str(homepage).rstrip("/").lower() != repo_url
            ),
            "OpenEBench (website up)": None
            if operational is None
            else float(operational == 200),
        },
        suggestion="Provide a project website.",
    )


def contribution_and_governance(data: IngestedData) -> MetricResult:
    """Whether contribution guidelines and governance are described.

    Sources: CONTRIBUTING, GOVERNANCE and CODE_OF_CONDUCT files, and resqui's
    ``has_contribution_guidelines`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "contribution_and_governance",
        {
            "CONTRIBUTING file": _has_file(
                data, lambda f: _name(f).startswith("contributing")
            ),
            "GOVERNANCE file": _has_file(
                data, lambda f: _name(f).startswith("governance")
            ),
            "CODE_OF_CONDUCT file": _has_file(
                data,
                lambda f: _name(f).startswith(("code_of_conduct", "code-of-conduct")),
            ),
            "resqui check": resqui_verdict(data, "has_contribution_guidelines"),
        },
        suggestion="Add contribution guidelines and describe the project's governance.",
    )


def containerization(data: IngestedData) -> MetricResult:
    """Whether the software can run in a container or isolated environment.

    Sources: container definitions (Dockerfile, Containerfile, Singularity),
    conda environment files, BioContainers (RSEc), and resqui's
    ``software_is_containerized`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    rsec_files = None if data.rsec is None else data.rsec.get("files") or []
    return verdict_metric(
        "containerization",
        {
            "container definition": _has_file(
                data,
                lambda f: (
                    _name(f).startswith(("dockerfile", "containerfile", "singularity"))
                    or _name(f) == "apptainer.def"
                ),
            ),
            "conda environment": _has_file(
                data, lambda f: _name(f) in ("environment.yml", "environment.yaml")
            ),
            "BioContainers (RSEc)": None
            if rsec_files is None
            else float(
                any(str(f).lower().endswith("biocontainers.yaml") for f in rsec_files)
            ),
            "resqui check": resqui_verdict(data, "software_is_containerized"),
        },
        suggestion="Provide a Dockerfile or a conda environment file.",
    )
