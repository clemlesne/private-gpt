# Security Policy

## Proactive detection of vulnerabilities

At each build, a vulnerability scan is performed on the system. If a vulnerability that can be upgraded is detected, the build is stopped and the image is not pushed to the registry. Vulnerability is reported in [GitHub Security](https://docs.github.com/en/code-security/code-scanning/automatically-scanning-your-code-for-vulnerabilities-and-errors/about-code-scanning). The maintainers are alterted and have access to reports.

Automation is supported by [Snyk](https://snyk.io) and [Semgrep](https://semgrep.dev). Helm chart, configuration files, and containers, are scanned for vulnerabilities and misconfigurations.

## Reporting a vulnerability

If you think you have found a vulnerability, please do not open an issue on GitHub. Instead, please send an email to [Clémence Lesné](mailto:clemence@lesne.pro).

## Chain of trust

Helm chart and containers are not signed yet with a GPG key.

## Reliability notes

Systems are built every days. Each image is accompanied by a SBOM (Software Bill of Materials) which allows to verify that the installed packages are those expected. This speed has the advantage of minimizing exposure to security flaws, which will then be corrected on the build environments in 24 hours.

Nevertheless it can happen that a package provider (e.g. Debian, Canonical, Red Hat) deploys a system update that introduces a bug. This is difficult to predict.
