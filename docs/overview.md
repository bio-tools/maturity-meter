# Maturity meter overview

This project aims to develop a new, automated, research software maturity model for tools in GitHub or GitLab. The project evaluates whether automated maturity (e.g., documentation quality, FAIR compliance, maintenance, and reuse signals) assessment can provide a scalable and informative complement to manual maturity annotation and assign up-to-date maturity levels.

As a long-term goal, the maturity model will become part of software disambiguation that goes beyond names, descriptions and topics, allowing for more fine-grained searchability among tools with similar functionality, building on the wealth of metadata in the Research Software Ecosystem to assist researchers searching for and making informed selections of software tools.

The project combines software metadata from bio.tools and other services of the Research Software Ecosystem, including OpenEBench, repository metadata from code hosting platforms, publication metadata from Europe PMC, and static code analysis using open-source software adapting and building on an automated maturity model recently developed in the more narrowly scoped TDCC-LSH “FAIR Toolbox” project in the Netherlands.

## Research topics

- [Open science](http://edamontology.org/topic_4010)
- [Software management](http://edamontology.org/topic_4047)
- [Software engineering](http://edamontology.org/topic_3372)

## Purpose Categories

- Data analysis
- Visualization & dissemination

## Access

**Access type:** Free.

## Programming languages

- Python

## Functions and operations

- [Statistical calculation](http://edamontology.org/operation_2238), [Data analysis](http://edamontology.org/operation_2945), [Quantification](http://edamontology.org/operation_3799) - input: [Data reference](http://edamontology.org/data_2093); output: [Matrix](http://edamontology.org/data_2082); Evaluate maturity of a given repository
- [Visualisation](http://edamontology.org/operation_0337) - input: [Matrix](http://edamontology.org/data_2082); output: [Plot](http://edamontology.org/data_2884); Plot the resulting maturity

## Interfaces

- Command-line tool (Stable)
- Library (Stable)
- Web API

## Platform support

- Platform independent - Officially supported
