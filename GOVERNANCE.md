# Project Governance - ClawCoat

**Version:** v11.0.1 · **Maintainer:** Quietfire AI

---

## Overview

TelsonBase is a self-hosted, source-available platform for managing autonomous AI agents through earned trust — agents progress from QUARANTINE to AGENT apex tier by demonstrating compliant behavior and receiving explicit human authorization at each step. This document describes how the project is governed, how decisions are made, and how contributors can participate.

---

## Maintainer

**Jeff Phillips** - Founder, Quietfire AI
- GitHub: [@QuietFireAI](https://github.com/QuietFireAI)
- Email: support@clawcoat.com
- ORCID: [0009-0000-1375-1725](https://orcid.org/0009-0000-1375-1725)

The maintainer holds final authority over the direction, architecture, and release schedule of TelsonBase. This is a single-maintainer project at present. Governance will expand as the contributor base grows.

---

## Decision Making

**Architecture and direction:** The maintainer decides. Significant decisions are documented in CHANGELOG.md and, where relevant, in the affected documentation files.

**Feature requests:** Submitted via GitHub Issues using the feature request template. The maintainer reviews and responds. Community support for a request (upvotes, use cases described in comments) is considered but does not determine outcomes.

**Bug fixes:** Any contributor may submit a pull request for a documented bug. PRs are reviewed by the maintainer. The full 720-test suite must pass before merge.

**Breaking changes:** The maintainer documents breaking changes in CHANGELOG.md under the affected version entry. No breaking changes are introduced in patch releases.

**Security issues:** Reported privately via the process in [SECURITY.md](SECURITY.md). Security fixes are prioritized above all other work.

---

## Release Process

TelsonBase uses [Semantic Versioning](https://semver.org/).

| Part | Meaning |
|---|---|
| MAJOR | Breaking changes to the API, data model, or configuration format |
| MINOR | New features, compliance modules, or capabilities - backward compatible |
| PATCH | Bug fixes, documentation corrections, dependency updates |

**Release cadence:** Releases ship when ready, not on a fixed schedule.

**Release steps:**
1. All tests pass (720 minimum, floor enforced in CI)
2. CHANGELOG.md updated with the full change list
3. `version.py` and `core/config.py` updated to the new version string
4. Git tag created matching the version
5. GitHub release published with changelog notes
6. DigitalOcean live demo updated to the new version

---

## Contributing

All contribution paths are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

The short version:
- Fork the repository
- Create a feature branch from `main`
- Write tests for any new behavior (720 is the floor, not the ceiling)
- Submit a pull request with a clear description of what changed and why
- The CI pipeline runs the full test suite on every PR

**What gets merged:** Code that strengthens earned-autonomy controls, security, compliance, or operational reliability. The platform is built on the principle that agents earn trust through behavior and human authorization — contributions that weaken controls, bypass audits, or reduce transparency will not be merged regardless of other merit.

**What does not get merged:** Changes that add cloud dependencies, telemetry, or data collection of any kind. TelsonBase's core commitment is zero data leaving the customer's network. This is architectural and non-negotiable.

---

## Roadmap

Planned development is tracked in [docs/WHATS_NEXT.md](docs/WHATS_NEXT.md). Community members may comment on roadmap items via GitHub Issues or Discussions.

---

## Code of Conduct

All contributors and community members are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md). The maintainer enforces it.

---

## Governance Evolution

This governance model reflects the current stage of the project. As TelsonBase gains contributors and organizational adoption, governance will expand to include:

- A formal Technical Steering Committee
- Defined contributor tiers (Contributor, Committer, Maintainer)
- Documented voting procedures for major decisions
- Quarterly roadmap reviews open to community input

Changes to this document follow the same PR process as code changes and are logged in CHANGELOG.md.

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
