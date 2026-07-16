# Channel Customization

The public channel allowlist is intentionally narrow. Do not add a private,
relay, experimental, or account-specific integration to a tracked public
registry.

## Publish an approved official example

An official channel may be committed as a public example when the user
explicitly approves publication and all of the following are true:

- the implementation uses the provider's official API and public
  documentation rather than a private relay or reverse-engineered protocol;
- tracked files contain reusable Model IDs or documented defaults only, never
  account-specific credentials, cookies, Endpoint IDs, signed URLs, or result
  URLs;
- the adapter downloads generated results to local artifacts and redacts
  remote URLs and authorization data from errors and manifests;
- registry, capability, environment-variable, recipe, pitfall, cost, and QA
  documentation are updated together;
- request construction passes non-billed/mock checks, followed by one
  user-approved lowest-cost real smoke test;
- an unproven route remains `suspended`; it becomes `approved` only after the
  real smoke test succeeds.

Public examples belong in `lib/custom_tools/`,
`lib/config/tool_registry.yaml`, `lib/config/tool_capabilities.yaml`, and
`lib/config/env_registry.json`. Add a runnable example to
`references/tool-recipes.md` and provider-specific failure/QA notes to
`references/assembly-qc-pitfalls.md`. A clean clone must be able to import the
adapter without any ignored local file.

Users may provide the official API documentation directly to an AI agent. The
agent should extract authentication shape, endpoints, models, inputs, async
states, limits, result fields, and pricing notes; implement the same public
surfaces; verify missing details against official documentation; and never
copy a credential from the conversation into tracked files.

## Add a local-only adapter

1. Keep the adapter implementation in a Git-ignored path or one of the ignored
   local adapter files already present in this checkout.
2. Add a record to `local-channels/tool_registry.yaml` with `module`,
   `category`, `provider`, `status: local_only`, and `runtime_engine` when the
   general image/video pipeline should select it.
3. Add its capability record to
   `local-channels/tool_capabilities.yaml`, including `modality`, `provides`,
   `tags`, and env variable names.
4. Store credentials in `.env`, never in either registry.
5. Test it through `scripts/run_tool.py` before allowing a capsule to reference
   it.

Local records override public records with the same tool name. This supports
private compatibility aliases without publishing provider information.

## Runtime substitution

Public capsules should declare role capabilities in `contracts/runtime.yaml`.
`validated_with` is the clean-clone baseline, not a permanent channel lock.
At runtime, Preflight merges the public capability registry with the local
overlay, filters candidates by available env variables, required flags/enums/
limits, preferences, and status, then writes:

- `preflight_report.json` for review;
- `execution_plan.json` for execution;
- `resolved_tools` in local-script params and the final manifest.

If the selected tool differs from `validated_with`, generation stops with
`needs_confirmation` unless the caller explicitly passes
`--accept_preflight_changes`. Storyboard/dry-run previews may inspect the route
without calling the provider. Disabled and suspended tools are not selected
automatically.

Both `preset` and `local_script` capsules must consume the selected tools.
Local scripts read `params.resolved_tools.<role>` and may use the default tool
only when that role was not declared. They must not silently replace the
Preflight selection with a hard-coded provider.

## Remove or suspend a local adapter

- Remove the local registry entries, or set `status: suspended` while keeping
  it out of local automatic selection.
- Update local capsules that reference the adapter.
- Do not change the public allowlist unless the channel is explicitly approved
  for publication.

## Capsule compatibility

A public capsule must resolve against public tools in a clean clone. The same
capability contract may resolve to a local-only adapter in a developer checkout
after Preflight and explicit confirmation; provider names, endpoints, and
credentials remain in the ignored overlay. A capsule whose required capability
exists only in a private adapter must itself remain local-only under the ignored
`capsules/*.capsule/` boundary.
