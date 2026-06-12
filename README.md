# tendrilio-contract

The versioned contract between the open-source [Tendrilio hub] and Tendrilio
Cloud: the command envelope JSON Schema, the canonical MQTT topic grammar,
the event vocabulary, and the prose specification (`SPEC.md`).

**This repository is published automatically.** Its contents are synced from
the private Tendrilio Cloud repository's CI on tagged contract releases
(`contract-v{major}.{minor}.{patch}`). Hand edits here will be overwritten —
open issues instead.

## Pinning a version

The hub repository pins a release tag and runs its contract tests against
that pinned bundle:

```
git -C tendrilio-contract checkout contract-v1.0.0
```

The cloud supports contract versions N and N-1, so a Connector built against
the previous major keeps working while you upgrade.

Start with [`SPEC.md`](./SPEC.md).
