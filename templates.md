# Template design reference

## Naming

- `Template App <thing> by <method>` — e.g. `Template App Elasticsearch by HTTP`.
- `Template OS <distro> by Zabbix agent 2` — e.g. `Template OS Ubuntu by Zabbix agent 2`.
- `Template Module <concern> by <method>` — reusable single-concern module, linked into higher-level templates. E.g. `Template Module TLS certificate expiry by HTTP`.
- `Template Net <vendor> <family> by SNMP` — networking gear.

Never version-suffix a template name (`v2`, `_new`) — that's what Git is for.

## Grouping

- `Templates/Operating systems`
- `Templates/Applications`
- `Templates/Databases`
- `Templates/Server hardware`
- `Templates/Network devices`
- `Templates/Modules` — reusable modules
- `Templates/Custom/<team>` — org-specific extensions

## Module template pattern

A module template holds exactly one concern and is linked into any higher-level template that needs it:

- `Template Module ICMP ping` — every host template links this
- `Template Module TLS certificate expiry by HTTP` — every HTTPS-facing template links this
- `Template Module Zabbix agent health` — every agent-monitored template links this
- `Template Module Auditd health by Zabbix agent` — every hardened Linux template links this
- `Template Module CVE tracker by external check` — supply-chain monitoring

This keeps concerns testable in isolation and avoids duplication across 30 templates.

## YAML export/import round-trip rules

- Export with **YAML** (7.x default). Commit the exported file exactly as Zabbix emits it — do not hand-edit whitespace or key order, the importer is forgiving but diffs get noisy.
- Do commit: `zabbix_export.version`, `groups`, `templates`, `triggers` (if any orphaned), `graphs`, `value_maps`.
- Do NOT commit UUIDs edited by hand. UUIDs are stable identifiers Zabbix uses to update-in-place instead of duplicating. If you rename an item, keep the UUID.
- Round-trip test in CI: import → export → diff. If the diff is non-empty (ignoring timestamps), the template is not idempotent — fix it before merging.

## Macros on templates

Every template exposes its full config surface as macros:

```yaml
macros:
  - macro: '{$ES.URL}'
    value: 'http://localhost:9200'
    description: 'Elasticsearch REST URL'
  - macro: '{$ES.USERNAME}'
    value: 'monitoring'
    description: 'Read-only monitoring user'
  - macro: '{$ES.PASSWORD}'
    type: SECRET_TEXT           # or VAULT
    description: 'Password for {$ES.USERNAME}. Set per-host or via Vault.'
  - macro: '{$ES.HEAP.USED.MAX.WARN}'
    value: '85'
    description: 'JVM heap used % — WARN threshold'
  - macro: '{$ES.HEAP.USED.MAX.HIGH}'
    value: '95'
    description: 'JVM heap used % — HIGH threshold'
  - macro: '{$ES.CLUSTER.STATE.MATCHES}'
    value: '^(green|yellow|red)$'
    description: 'Cluster state values to accept as valid'
```

Rule of thumb: **if the user might want to override it per-host, it's a macro**.

## Tags on templates

Template-level tags flow to every problem raised by every trigger on hosts linked to the template. Use them for routing and reporting:

```yaml
tags:
  - tag: class
    value: application
  - tag: target
    value: elasticsearch
  - tag: team
    value: platform
```

Per-trigger tags add `severity`, `component`, `scope`. Per-item/prototype tags add `component` and LLD-macro-valued drill-down tags like `filesystem:{#FSNAME}`.

## Linking discipline

- A host is linked to **exactly one OS template** and 1..N application/module templates.
- Do not "nested-link" for shared config; use module templates.
- When a template is renamed, unlink+relink is destructive (loses history for the item on that host). Use API `template.update` to rename in place; the linked hosts keep item history.

## What good looks like

A "finished" template:

1. Round-trips through export/import with zero diff.
2. Has zero hardcoded numbers in trigger expressions — everything is a macro.
3. Every macro has a `description`.
4. Every trigger has a runbook URL and routing tags.
5. Every credential macro is `SECRET_TEXT` or `VAULT`.
6. Every LLD rule has user-macro-driven filters.
7. Every item type is documented in the template `description` field.
8. The template imports cleanly on an empty Zabbix instance of the target version.
