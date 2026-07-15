# Environment and Secret Handling

Never hard-code API keys, access tokens, cookies, authorization headers,
private endpoints, signed URLs, account credentials, or temporary object URLs.
Tracked documentation may list variable names only.

## Public variables

Official Volcengine Ark:

- `ARK_API_KEY`
- `ARK_BASE_URL` (optional; default is the official Beijing Ark API)
- `ARK_SEEDREAM_MODEL`
- `ARK_SEEDANCE_MODEL`

Official TTS:

- `MINIMAX_API_KEY`
- `MINIMAX_GROUP_ID` (optional when derivable)
- `DOUBAO_TTS_APPID`
- `DOUBAO_TTS_ACCESS_TOKEN`
- `DOUBAO_TTS_SECRET_KEY` (optional)
- `DOUBAO_TTS_CLUSTER_ID`

RunningHub examples:

- `RUNNINGHUB_API_KEY`
- workflow-specific key and app-ID variables declared in
  `lib/config/env_registry.json`

Runtime variables such as `PYTHON_BIN`, `DOTENV_PATH`, and output/resource paths
are non-secret. Planning-runtime credentials remain generic and must still be
stored only in `.env`.

## Local-only variables

Names for additional providers belong in the ignored
`local-channels/tool_capabilities.yaml`. Their values belong in `.env`. The
public `skill.md`, `index.js`, examples, capsules, tests, and registries must not
enumerate them.

Scripts must fail with missing variable names only and redact request headers,
query strings, signed URLs, and response URLs from logs.
