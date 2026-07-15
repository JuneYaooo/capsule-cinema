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

## Remove or suspend a local adapter

- Remove the local registry entries, or set `status: suspended` while keeping
  it out of local automatic selection.
- Update local capsules that reference the adapter.
- Do not change the public allowlist unless the channel is explicitly approved
  for publication.

## Capsule compatibility

A public capsule must resolve entirely against public tools, local processing,
user-supplied media, or packaged public assets. A capsule bound to a local-only
tool must itself remain local-only under the ignored `capsules/*.capsule/`
boundary.
