# Environment and Secret Handling

Never hard-code API keys, access tokens, cookies, authorization headers,
private endpoints, signed URLs, account credentials, or temporary object URLs.
Tracked documentation may list variable names only.

## Public variables

Official Volcengine Ark:

- `ARK_API_KEY`
- `ARK_BASE_URL` (optional; default is the official Beijing Ark API)
- `ARK_SEEDREAM_MODEL` (optional; defaults to `doubao-seedream-5-0-pro-260628`)
- `ARK_SEEDANCE_MODEL` (optional; defaults to `doubao-seedance-2-0-260128`)

Official TTS:

- `MINIMAX_API_KEY`
- `MINIMAX_GROUP_ID` (optional when derivable)
- `DOUBAO_TTS_API_KEY` (Doubao Speech API Key)
- `DOUBAO_TTS_RESOURCE_ID` (optional; defaults to `seed-tts-2.0`)
- `DOUBAO_TTS_MODEL` (optional; defaults to `seed-tts-2.0-standard`)
- `DOUBAO_TTS_SPEAKER` (optional default speaker ID)
- `DOUBAO_TTS_WS_URL` (optional endpoint override)

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
