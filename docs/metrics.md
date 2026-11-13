# Metrics

Ingested data is grouped into metrics, and metrics into the six dimensions.
Every metric covers one concept, such as licensing, and uses every ingested
item about it.

## How a metric is built

Most metrics combine several **aspects**: distinct questions about the
concept. Licensing, for example, asks whether a licence is declared, whether
it is open source, whether it is machine-readable and whether individual files
carry one. Each aspect is answered by every source that can:

- each source's raw value is first **scaled** onto [0, 1] (see
  [Scaling](#scaling) below; yes/no answers are already 0 or 1);
- the sources answering one aspect are **reconciled** with
  `placeholder_reconcile`;
- the aspects are **combined** into the metric with `placeholder_combine`;
- the metrics are **aggregated** into the dimension with
  `placeholder_dimension_score`.

Reconciliation, combination and aggregation are placeholders (currently
means), to be replaced once they are decided; the scaling is final. A source without an answer, or an aspect no source could answer,
is left out rather than counted as a "no". Metrics with a single aspect simply
reconcile their sources. Each metric's note lists every aspect's answer and
every source's answer to it, so disagreements are visible; its suggestions are
those of the aspects scoring below 0.5.

FAIR-Checker scores (NO, WEAK, STRONG) count as 0, 0.5 and 1. FAIR-Checker
evaluates the metadata embedded in the repository's web page, so for
repositories on GitHub or GitLab it mostly describes that platform's page.

The [lineage](lineage.md) shows, generated from the code, which fields each
metric reads.

## Metrics by dimension

A metric listed under two dimensions is shared: it is computed once and
counts in both.

### FAIRness

| Metric | Aspects: sources |
|---|---|
| `licensing` | **declared**: repository licence, LICENSE/COPYING file, bio.tools and OpenEBench licences, OpenEBench source licence, RSFC/OEBFAIR licence check · **open source**: OpenEBench OSI and open-source checks, repository and bio.tools licences in a list of OSI licences · **machine-readable**: FAIR-Checker R1.1, bio.tools licence · **per file**: REUSE setup, HowFairIs per-file check |
| `citation_and_credit` | **how to cite**: CITATION file, RSFC, OpenEBench, README · **credits**: AUTHORS file, bio.tools and OpenEBench credits |
| `publications` | publications (request DOIs, bio.tools, OpenEBench) and their open-access share (Europe PMC, OpenAlex) |
| `registry_listing` | bio.tools, OpenEBench and RSEc entries, README registry badge |
| `persistent_identifier` | software DOI/SWHID in README, bio.tools ID, RSFC/OEBFAIR, FAIR-Checker F1B |
| `machine_readable_metadata` | **structured metadata**: codemeta.json, CITATION.cff, bio.tools entry, RSFC CodeMeta completeness, FAIR-Checker F2A, I1, I3, R1.2 · **community vocabularies**: EDAM topics and operations (bio.tools), Bioschemas (OpenEBench), FAIR-Checker F2B, I2, R1.3 |
| `documentation` | **user documentation**: README, docs folder, GitHub Pages, bio.tools documentation, OpenEBench documentation (including terms of use) and README checks, RSFC/OEBFAIR · **purpose**: repository, bio.tools and OpenEBench descriptions |
| `installation_instructions` | **instructions**: README, bio.tools installation docs · **dependencies**: dependency manifest, RSFC · **build**: build configuration, OpenEBench build |
| `source_availability` | **public repository**: repository visibility, OpenEBench public/online/anonymous-access checks, RSFC version control · **free download**: OpenEBench free source and source packages, bio.tools source download |
| `releases_and_versioning` | **releases**: latest release, RSFC · **version numbers**: version-like tag, RSFC |
| `binary_distribution` | release assets, bio.tools binaries, OpenEBench free binaries |
| `software_tests` | test files, RSFC |
| `source_archival` | Zenodo and Software Heritage in README, RSFC archival checks |
| `issue_tracking` | repository issue tracker, OpenEBench, bio.tools issue-tracker link |
| `project_website` | repository homepage, GitHub Pages, bio.tools homepage, OpenEBench website check |
| `contribution_and_governance` | **contribution guidelines**: CONTRIBUTING file, RSFC · **governance**: GOVERNANCE and CODE_OF_CONDUCT files · **communication channels**: RSFC, OpenEBench support e-mail, bio.tools forum/mailing-list links |
| `containerization` | container definition, conda environment, BioContainers (RSEc), RSFC |

### Compatibility

| Metric | Aspects: sources |
|---|---|
| `input_formats`, `output_formats` | share of the bio.tools formats that are specific EDAM terms |
| `package_availability` | **published package**: Bioconda and Debian Med (RSEc), OpenEBench packages, OpenSSF Scorecard · **packaging recipe**: conda recipe, Python packaging file |
| `containerization` | shared with FAIRness |
| `workflow_integration` | Galaxy (RSEc), Galaxy service link (bio.tools), Snakemake/Nextflow/CWL/WDL files |
| `dependency_management` | OpenSSF Scorecard, Dependabot/Renovate configuration (shared with Security) |

### Maintainability

| Metric | Aspects: sources |
|---|---|
| `avg_ccn` | average cyclomatic complexity per function (Lizard) |
| `duplicate_rate` | share of duplicated code (Lizard) |
| `continuous_integration` | **CI configured**: CI configuration files, RSFC repository workflows · **changes tested**: OpenSSF Scorecard CI tests |
| `linting` | **linting set up**: linter configuration files · **no linting issues**: SuperLinter (when enabled) |
| `releases_and_versioning` | shared with FAIRness |
| `requirements_specified` | dependency manifest, RSFC |

### Scientific impact

| Metric | Sources |
|---|---|
| `star_count`, `fork_count` | GitHub/GitLab |
| `citation_count` | OpenAlex, Europe PMC, bio.tools and OpenEBench citation counts, reconciled per publication and summed |
| `fwci` | OpenAlex field-weighted citation impact |

### Security

| Metric | Aspects: sources |
|---|---|
| `change_control` | **branch protection**: default branch protected · **code review**: OpenSSF Scorecard |
| `vulnerability_management` | **no critical vulnerabilities**: OpenSSF Scorecard · **security policy**: SECURITY.md |
| `security_testing` | **static analysis**, **fuzzing**: OpenSSF Scorecard |
| `repository_hygiene` | **no binary artifacts**: OpenSSF Scorecard · **ignore file**: .gitignore · **no leaked credentials**: Gitleaks (when enabled) |
| `dependency_management` | shared with Compatibility |

### Sustainability

| Metric | Aspects: sources |
|---|---|
| `development_activity` | **recent activity**: days since the last push or project activity · **active project**: OpenSSF Scorecard |
| `issue_close_time` | median close time of the GitHub/GitLab closed issues, OpenEBench resolution time |
| `resolved_issue_share` | closed issues out of all reported issues (GitHub/GitLab) |
| `inverse_simpson_index` | contributor diversity of commit shares, bots excluded |
| `contribution_and_governance` | shared with FAIRness |

## Scaling

Every numeric field is mapped onto [0, 1] before it is reconciled with other
sources. The transformations follow the literature or established thresholds;
the ingested data of about 750 bio.tools-registered tools only places the
reference points (e.g. at roughly the top 5-10%).

| Field | Transformation | Reasoning |
|---|---|---|
| Stars, forks | `log(1 + x) / log(1 + ref)`, capped at 1; ref 100 stars, 25 forks | Counts are heavily skewed (median 6 stars, maximum 884); a log scale is the standard way to compare such counts ([Thelwall 2017](https://arxiv.org/abs/1510.08877)). The references are about the top 5%. |
| Citation counts | same, ref 100 citations, per source before reconciling | Citation counts are lognormal ([Thelwall 2017](https://arxiv.org/abs/1510.08877)); 100 is about the top 10% of these tools' publications. |
| FWCI | `x / (1 + x)` | FWCI 1.0 is the world average of the field and year, so it scores 0.5; the score saturates for the lognormal tail of FWCI values. |
| Days since the last activity | 1 within 90 days, then halves every further 365 days | OpenSSF Scorecard's Maintained check looks at the last 90 days; one year without commits is the usual threshold for a dormant project ([Coelho & Valente 2017](https://arxiv.org/abs/1707.02327)). |
| Issue close time | median of the closed issues, then `1 / (1 + days / 30)` | CHAOSS recommends the [median close time](https://chaoss.community/metric-issue-resolution-duration/) over the mean; it gives no benchmark, so half the score is at one month, near the median of these tools (46 days). |
| Open issues | share of reported issues that are closed | The number of open issues grows with use, not neglect; relative to all reported issues it shows whether the backlog is handled. |
| Contributor diversity (inverse Simpson index D) | `1 - 1/D` (Gini-Simpson index) | The probability that two random commits are by different people: 0 for one developer, 0.5 for two equal ones. |
| Average cyclomatic complexity | 1 at 1, 0 at 10, linear | 10 per function is McCabe's and NIST's recommended maximum; an average at that maximum scores 0. |
| Duplicated code (%) | 1 up to 3%, 0 at 100%, linear | SonarQube's recommended quality gate ("Sonar way") allows at most [3% duplicated lines](https://docs.sonarsource.com/sonarqube-server/2025.3/quality-standards-administration/managing-quality-gates/introduction-to-quality-gates). |
| Share of EDAM leaf formats | used as is | Already a share in [0, 1]. |
| FAIR-Checker scores | NO 0, WEAK 0.5, STRONG 1 | FAIR-Checker's own three levels. |

## Ingested items that are not used

An item is left out only when the data shows it is wrong or describes
something other than the software:

| Item | Why it is left out |
|---|---|
| HowFairIs `software_has_license` | Reported "no licence" for most repositories with a LICENSE or LICENSE.md file in the root, the files it looks for. |
| OEBFAIR `listed_in_registry` | Reported "not listed" for every tool, including tools listed in bio.tools. |
| OEBFAIR `has_published_package` | Reported "no package" for every tool, including Bioconda packages. |
| RSFC and OEBFAIR `descriptive_metadata` | Gave opposite answers (always no, always yes) for the same tools. |
| OpenEBench `deprecated` | Reported as deprecated for nearly every tool. |
| OpenEBench website checks (copyright, licence, HTTPS, uptime, access time, redirects) | Describe the homepage, which for most tools is the GitHub/GitLab page. Only whether the website is up is used, in `project_website`. |
| FAIR-Checker F1A, A1.1, A1.2 | Test the URL and access protocol of the evaluated page (always the GitHub/GitLab page), not the software. |
| Lizard file and function counts, lines of code, total complexity | Measure the code base's size, which does not show how mature the software is: small, mature utilities exist. The per-function averages are used. |
| Publication reference counts | References a publication makes are not citations it receives. |
