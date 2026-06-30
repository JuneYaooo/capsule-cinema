# Environment and Secret Handling

Use this when adding or changing channels, credentials, wrappers, tool recipes, capsules, or production plans.

## Core Rule

Never hard-code sensitive information in scripts, examples, plans, capsule configs, manifests, logs, or documentation.

Sensitive information includes:

- API keys, tokens, cookies, session IDs, and bearer headers.
- Secret base URLs, signed upload/download URLs, and private endpoints.
- Account IDs when they grant access or identify private infrastructure.
- Temporary credentials and pre-signed object storage links.

Docs and channel records may list env var names, never their values.

## Env Naming

Keep env vars obvious and grouped by provider:

```text
PROVIDER_API_KEY
PROVIDER_BASE_URL
PROVIDER_TIMEOUT_SECONDS
PROVIDER_WORKFLOW_ID
PROVIDER_DEFAULT_MODEL
```

For multiple channels under one provider, prefix with the stable provider name:

```text
JULING_API_KEY
JULING_BASE_URL
KRILL_GPT_IMAGE2_API_KEY
KRILL_GPT_IMAGE2_BASE_URL
ZEAKAI_GPT_IMAGE2_PRO_API_KEY
RUNNINGHUB_API_KEY
MINIMAX_API_KEY
DOUBAO_APP_ID
DOUBAO_ACCESS_TOKEN
```

Only document required/optional status and purpose:

```markdown
Env:
- `PROVIDER_API_KEY` required, API authentication
- `PROVIDER_BASE_URL` optional, custom endpoint
```

## Script Rules

Scripts must:

- Read secrets from `os.environ`, shell env, or the project's existing config loader.
- Fail fast with a concise missing-env message.
- Print only variable names, never values.
- Avoid embedding secrets in command-line args when those commands can appear in shell history or process listings.
- Redact request headers, query strings, and signed URLs from logs.

Python pattern:

```python
import os

required = ["PROVIDER_API_KEY"]
missing = [name for name in required if not os.environ.get(name)]
if missing:
    raise RuntimeError("Missing required env vars: " + ", ".join(missing))
api_key = os.environ["PROVIDER_API_KEY"]
```

Bash check pattern:

```bash
missing=()
for name in PROVIDER_API_KEY PROVIDER_BASE_URL; do
  [ -n "${!name:-}" ] || missing+=("$name")
done
if [ "${#missing[@]}" -gt 0 ]; then
  printf 'Missing required env vars: %s\n' "${missing[*]}" >&2
  exit 1
fi
```

Do not use `env`, `printenv`, `set`, or debug dumps in final logs because they can expose values.

## Plan and Capsule Rules

Production plans and capsule configs may contain:

- tool names
- provider names
- model names
- non-secret workflow IDs when public/non-sensitive
- env var names
- normal media paths

They must not contain:

- API key values
- bearer tokens
- cookies
- secret URLs
- full Authorization headers
- private upload URLs unless the user explicitly supplied them for one-time use

If a user gives a secret in chat, use it only for the current operation when necessary, do not write it to disk, and ask the user to move it into an env var for future use.

## Recipes and Examples

Tool recipes should show env var names and parameter shapes:

```bash
python "scripts/run_tool.py" \
  --tool "ProviderTool" \
  --params '{"prompt":"...","aspect_ratio":"9:16"}'
```

Do not show:

```bash
export PROVIDER_API_KEY="<secret>"
curl -H "Authorization: Bearer <secret>" ...
```

## Efficient Maintenance

When adding a new channel, update only three env-related places:

1. The channel's `Env:` list in `channel-policy.md` or the user channel registry.
2. The wrapper/config loader that reads those env vars.
3. A missing-env smoke check that reports names only.

Avoid duplicating credential instructions across many files. Link back to this reference instead.
