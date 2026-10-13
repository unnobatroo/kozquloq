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
to DuckDB. Relevant risk areas: SQL injection through the diagnostic
agent's `run_sql` tool (currently restricted to read-only SELECT/WITH),
unsafe deserialization of point-cloud/npz payloads, and HTML/JS injection
into the generated report from dataset-controlled strings.
