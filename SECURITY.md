# Security Policy

## Supported version

Security fixes are applied to the latest version on the `main` branch.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that exposes credentials, private transcript content, personal data, or remote-code execution. Contact the repository owner privately through GitHub instead.

## Deployment guidance

- Set `PODCAST_KG_API_KEY` for every non-local deployment.
- Put TLS and stronger authentication in a trusted reverse proxy or API gateway.
- Bind the development Compose port to localhost unless remote access is intentional.
- Treat SQLite, JSONL and N-Quads exports as potentially sensitive.
- Keep the `/data` volume encrypted at rest where required.
- The built-in API key is a minimal deployment control, not multi-user authorization or tenancy.
