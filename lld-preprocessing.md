# LLD & preprocessing reference

Source: Zabbix guidelines & LLD manual (see SKILL.md for URLs).

## LLD JSON shape (since Zabbix 4.2)

LLD accepts a plain JSON array — the old `{"data": [...]}` wrapper is no longer required. If the source returns the old shape, Zabbix auto-extracts via `$.data`. New rules must emit the array form.

```json
[
  {"{#FSNAME}": "/", "{#FSTYPE}": "ext4"},
  {"{#FSNAME}": "/var", "{#FSTYPE}": "xfs"}
]
```

Custom paths to macros are supported via `lld_macro_paths` with JSONPath — use this instead of manual JS extraction when the source already has clean field names.

## Filter pattern

Two macros per filterable field: MATCHES and NOT_MATCHES. Filter condition uses `AND`:

```
{#IFNAME} MATCHES {$NET.IF.IFNAME.MATCHES}
{#IFNAME} NOT_MATCHES {$NET.IF.IFNAME.NOT_MATCHES}
```

Defaults on the template:

```
{$NET.IF.IFNAME.MATCHES}     = ^.*$
{$NET.IF.IFNAME.NOT_MATCHES} = (^Software Loopback Interface|^NULL[0-9.]*$|^lo$|^docker[0-9]+$|^veth.*$)
```

Users override on a host/hostgroup macro without touching the template.

## Normalize before throttling

If the source doc contains fields that change every poll (bytes, timestamps), `Discard unchanged with heartbeat` on the LLD rule won't help — the LLD JSON is always "different". Add a JS step to reduce the doc to only LLD-relevant fields first:

```javascript
// LLD rule preprocessing: strip volatile fields before throttling
const filesystems = JSON.parse(value);
const result = filesystems.map(function (fs) {
  return { fsname: fs.fsname, fstype: fs.fstype };
});
return JSON.stringify(result);
```

Then add `Discard unchanged with heartbeat = 1h` as the next step. Now the LLD rule only wakes `lld_manager` when the *set* changes.

## Singleton pattern (feature exists / doesn't)

Use when a template covers hosts that may or may not have a feature (e.g., Apache event MPM, NGINX Plus, SSL enabled). One template, no unsupported items.

```javascript
// LLD rule JS preprocessing
return JSON.stringify(value === 'found' ? [{'{#SINGLETON}': ''}] : []);
```

Then in item prototype keys: `apache.mpm.event[{#SINGLETON}]`. The empty macro is required so Zabbix distinguishes the prototype from a real item; after discovery the macro expands to nothing, leaving a clean item name.

Constraint: the LLD macro must be inside square brackets in the item key. For graphs, append `{#SINGLETON}` to the graph name; item/trigger names don't need it.

## JavaScript preprocessing rules

- Pure function of `value`. No global state between invocations.
- Always `return` a string. Zabbix stringifies but be explicit.
- Wrap parses in try/catch when the source might be malformed:

  ```javascript
  var doc;
  try { doc = JSON.parse(value); }
  catch (e) { throw 'Malformed JSON from source: ' + e; }
  return doc.some.field;
  ```

- Prefer JSONPath / Prometheus pattern steps over JS when they can express the extraction — they're faster and don't need review.
- No `HttpRequest` inside preprocessing unless you truly need an external lookup — you're inside the preprocessing manager, blocking it.

## Coded string → integer

For discrete states, convert to integers + value maps so triggers can use numeric comparison and dashboards can color-code:

```javascript
// element indexes start at 1; 0 reserved for default
const idx = {
  'PROVISIONING': 1, 'AVAILABLE': 2, 'STOPPING': 3, 'STOPPED': 4,
  'STARTING': 5, 'TERMINATING': 6, 'TERMINATED': 7
};
return idx[value] || 0;
```

Attach a value map: `0 → unknown, 1 → provisioning, ...`.

## Discard unchanged with heartbeat — when to use

**Use** on: health checks, version strings, feature flags, cluster names, config values — anything that rarely changes.

**Do NOT use** when a `nodata()` trigger relies on the item receiving fresh values within the heartbeat window — Discard will suppress values and the trigger will misfire.

Rule: if the trigger references the item with `nodata(/host/key, 5m)`, heartbeat must be < 5m or Discard must be off.

## Error handlers on preprocessing

Every step needs an explicit handler for the "bad input" case:

- `Discard value` — silently drop; item stays "not supported" briefly then recovers on next value. Use for optional fields.
- `Set value to` — substitute a default (e.g., `0`, `-1`) when upstream is intermittently missing the field. Use with a value map that maps the default to "unknown".
- `Set error to` — mark item unsupported with a specific message. Use for hard invariants ("received value must be JSON"). This surfaces in the frontend and can be alerted on via internal items.

Never leave the default. It hides bugs in your extraction.

## Overrides on LLD rules

Use overrides to selectively enable/disable prototypes without duplicating the rule. Example: for filesystems where `{#FSTYPE}` is `tmpfs`, disable the "space usage" trigger prototype but keep the item.

```yaml
overrides:
  - name: 'Exclude tmpfs from space triggers'
    step: 1
    filter:
      conditions:
        - macro: '{#FSTYPE}'
          value: '^tmpfs$'
          operator: MATCHES_REGEX
    operations:
      - operationobject: TRIGGER_PROTOTYPE
        operator: LIKE
        value: 'Filesystem space'
        status:
          status: DISABLED
```

## Common LLD sources (patterns Karthi already runs)

- **Filesystems**: `vfs.fs.discovery` (agent 1) or `vfs.fs.get` (agent 2, richer). Filter `{#FSTYPE}` NOT_MATCHES `(overlay|squashfs|tmpfs|devtmpfs|autofs)`.
- **Network interfaces**: `net.if.discovery`. Filter NIC noise, add per-VRF handling if applicable.
- **Elasticsearch indices / ILM policies**: HTTP agent master item → `_cat/indices?format=json` or `_ilm/policy` → JS extracts `{#INDEX}` / `{#POLICY}` — you already run this pattern.
- **VPN tunnels (AWS)**: HTTP agent → describe-vpn-connections → JS preprocessing extracts `{#TUNNEL.ID}`, `{#TUNNEL.OUTSIDE_IP}` — Karthi's existing pattern.
- **Kafka topics / consumer groups**: HTTP agent to Kafka admin proxy → JS reshape to LLD.
- **S3 buckets**: external check `aws s3 ls` → JS → LLD. Better: agent2 with a custom plugin.

## Zabbix 7.4 preprocessing perf note

Items with **no preprocessing and no dependents** now bypass the preprocessing manager entirely — values go straight to the history cache. Design implication: an item that only needs a value type coercion (e.g., `Type: Numeric (unsigned)` on a raw integer) should have zero preprocessing steps to hit the fast path. Add preprocessing only when you're actually transforming.
