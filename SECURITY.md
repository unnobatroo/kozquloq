# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | yes       |

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Report privately via GitHub Security Advisories:
`https://github.com/<owner>/kozquloq/security/advisories/new`
(or contact the maintainers listed in the repository profile).

Include: affected version/commit, reproduction steps, impact assessment
(data corruption, RCE, credential exposure, etc.).

You can expect an acknowledgment within 72 hours and a coordinated
disclosure timeline agreed with you before any public fix lands.

## Scope notes

Kozquloq processes autonomous-driving sensor data and writes audit results
to DuckDB. Relevant risk areas: unsafe deserialization of dataset payloads
(pcd.bin / npz / JPEG parsing via the devkit and OpenCV), malformed fixture
JSON, and local file writes under `--viz-dir`/`--db`/`--output` paths.
All SQL uses parameter binding; there is no dynamic query surface.
