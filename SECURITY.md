# Security

Never report credentials, session tokens, NHS identifiers or real clinical records in an issue. Revoke exposed credentials and contact the maintainer privately. Raw source files and generated patient bundles must remain outside Git.

The browser capture component is intentionally not automated in the public repository yet. Authentication, rate limiting, session expiry and TPP's terms must be understood before unattended capture is added.
