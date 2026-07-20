# Security policy

## Supported version

Security fixes are provided for the latest published release.

## Reporting a vulnerability

Do not include secrets, private project graphs, access tokens, or confidential
concept documents in a public issue. Use the repository's private GitHub
security-advisory channel. If that channel is unavailable, open a minimal issue
requesting a private contact method without disclosing the vulnerability.

## Security model

The renderer is local-first and has no required cloud backend. This reduces
data exposure; it does not make arbitrary imported files trustworthy. Review
input graphs before opening them, use current browser and Python versions, and
do not treat generated gates or evidence as a substitute for human acceptance.
