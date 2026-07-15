# Local Channel Customization

The public channel allowlist is intentionally narrow. Do not add a private,
relay, experimental, or account-specific integration to a tracked public
registry.

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
