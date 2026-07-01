# Infisical

This repo is linked to the Infisical `Casdoor` project.

Credential paths:

- `prod:/casdoor/sae` - current SAE `casdoor` application environment.
- `prod:/casdoor/local` - local Casdoor RDS/bootstrap deployment credentials.
- `prod:/omni-db/sae` - current SAE `omni-db` application environment.
- `prod:/omni-db/local` - local OmniDB SAE deployment credentials.

Examples:

```bash
infisical export --env=prod --path=/casdoor/sae --format=dotenv
infisical export --env=prod --path=/omni-db/sae --format=dotenv
```
