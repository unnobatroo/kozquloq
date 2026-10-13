# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | yes       |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report privately via GitHub Security Advisories:
`https://github.com/unnobatroo/kozquloq/security/advisories/new`

Include the affected version or commit, reproduction steps, and the impact
(data corruption, code execution, credential exposure). Expect an
acknowledgment within 72 hours and a coordinated disclosure timeline before
any public fix lands.

## What the attack surface actually is

Kozquloq is a local CLI that reads dataset files and writes a DuckDB file
plus images. There is no server, no network listener, and no user input
reaching a shell. The realistic risk areas:

- **Dataset deserialization** - `pcd.bin`, `npz`, and JPEG payloads are
  parsed by the nuScenes devkit and OpenCV. A hostile dataset file is the
  main exposure; bugs there live upstream in those parsers.
- **Local file writes** - `--viz-dir`, `--db`, and `--output` write where
  you point them. They are trusted paths, not sanitized inputs.
- **SQL** - every query is parameter-bound and there is no dynamic query
  surface, so injection through the CLI is not a realistic path.
