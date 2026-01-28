# Contributing to RMTC

Thank you for your interest in contributing to RMTC. This document explains our contribution process and procedures:

* [How to Contribute a Bug Fix or Change](#How-to-Contribute-a-Bug-Fix-or-Change)
* [Development Workflow](#Development-Workflow)
* [Coding Style](#Coding-Style)

For a description of the roles and responsibilities of the various members of the RMTC community, see the [governance policies], and for further details, see the project's [Technical Charter]. Briefly, Contributors are anyone who submits content to the project, TSC Members review and approve such submissions, and the Technical Steering Committee provides general project oversight. 

If you just need help or have a question, refer to [SUPPORT.md](SUPPORT.md).

## Development Workflow

RMTC follows standard [git flow] policies with [semantic versioning].

Generally avoid collapsing and rebasing changelists for a neat tramline - prioritize a 'warts and all' git history to avoid future bisection issues and full visibility of provenance to be aligned with the tracing optics of RMTC.

Finally, major releases have no other meaning outside semantic versioning; for example a major 1.0.0 release is not considered a magic project threshold and may be very quickly superseded with 2.0.0.

## Coding Style

The general style could be considered 'verbose'; favoring simple long form code over [brevity].

RMTC is currently a Python 3 [PEP8] style project with strict linting requirements checked by [pylint]. Formatting is automated by [black] - don't expect any manual formatting to persist. This is upheld by the [precommit](precommit.sh) script. C++ plugins are likely to appear in due time.

Regarding design - generally classical OO with limited inheritence using functional deferral (e.g. a class to read/write is injected rather than an overridable method). Ownership clarity is important - avoid singleton like designs and be clear who owns what.

Style and design guidelines will expand in due course of the project.

## How to Contribute a Bug Fix or Change

To contribute code to the project, first read over the [governance policies] page to understand the roles involved. Contributors should be authorized via the LFX [EasyCLA] as there is a hook on PR submission to check.

Each contribution must meet the coding style and include:

* [Tests](tests) and [documentation](docs), to explain the functionality
* Any new files have [copyright and license headers]
* A [DCO] signoff
* Submitted to the project as a pull request

For further information see general ASWF [contrbuting guidelines]. 

RMTC is licensed under the [Apache-2.0](LICENSE.md) license. Contributions should abide by that standard license.

Project committers will review the contribution in a timely manner, and advise of any changes needed to merge the request.

[governance policies]: GOVERNANCE.md
[Technical Charter]: https://lfx-cdn-prod.s3.us-east-1.amazonaws.com/project-artifacts/rongotai-model-train-club-rmtc/rongotai-model-train-club-rmtc_Charter.pdf?v=1763492766002
[ICLA]: https://cla-signature-files-prod.s3.amazonaws.com/contract-group/d5634811-ff26-4c69-a2b1-301f62c6473b/template/icla-2025-11-17T15-34-37Z.pdf
[CCLA]: https://cla-signature-files-prod.s3.amazonaws.com/contract-group/d5634811-ff26-4c69-a2b1-301f62c6473b/template/icla-2025-11-17T15-34-37Z.pdf
[EasyCLA]: https://easycla.lfx.linuxfoundation.org/
[copyright and license headers]: https://github.com/AcademySoftwareFoundation/tac/blob/main/process/contributing.md#license-specification
[contrbuting guidelines]: https://github.com/AcademySoftwareFoundation/tac/blob/main/process/contributing.md
[DCO]: https://github.com/AcademySoftwareFoundation/tac/blob/main/process/contribution_guidelines.md#contribution-sign-off
[git flow]: https://nvie.com/posts/a-successful-git-branching-model/
[PEP8]: https://peps.python.org/pep-0008/
[brevity]: https://blog.codinghorror.com/in-defense-of-verbosity/
[semantic versioning]: https://semver.org/
[black]: https://github.com/psf/black
[pylint]: https://github.com/psf/black