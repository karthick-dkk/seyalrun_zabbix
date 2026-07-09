# Zabbix API automation reference

## Endpoint & auth

- Endpoint: `POST https://zabbix.example.com/api_jsonrpc.php`
- Protocol: JSON-RPC 2.0
- Auth: **Bearer token** via `Authorization: Bearer <token>` header (preferred in 6.4+).
  - Legacy `user.login` returning a session ID still works but treats auth as an in-payload field — avoid in new code.
- API version = Zabbix version. Confirm with `apiinfo.version` (no auth required).

## Token lifecycle

1. Create a dedicated automation user (`svc-salt`, `svc-terraform`, `svc-cicd`) — Super Admin only if it needs `configuration.import` on templates; else scope down via role.
2. Generate a token via UI or `token.create` — set an expiry (max 1 year), record the token ID, store the secret in Vault.
3. CI reads the token from Vault at run time; never in a repo, never in an env file committed.
4. Rotate: `token.update` to extend, or `token.create` a new one and `token.delete` the old — with overlap so in-flight jobs don't fail.
5. Every token action is in the audit log — ship to SIEM.

## Curl skeleton (Bash)

```bash
#!/usr/bin/env bash
set -euo pipefail

: "${ZBX_URL:?ZBX_URL required}"     # https://zabbix.example.com/api_jsonrpc.php
: "${ZBX_TOKEN:?ZBX_TOKEN required}" # from Vault

zbx_call() {
  local method="$1" params="$2"
  curl -sS --fail-with-body \
    --request POST \
    --url "$ZBX_URL" \
    --header 'Content-Type: application/json-rpc' \
    --header "Authorization: Bearer $ZBX_TOKEN" \
    --data "$(jq -cn \
        --arg m "$method" --argjson p "$params" \
        '{jsonrpc:"2.0", method:$m, params:$p, id:1}')"
}

# Example: check API version (no auth needed, but consistent shape)
zbx_call apiinfo.version '{}' | jq -r .result

# Example: list disabled hosts
zbx_call host.get '{"output":["host","status"], "filter":{"status":1}}' \
  | jq -r '.result[] | .host'
```

Always use `--fail-with-body` and parse `.error` — JSON-RPC returns HTTP 200 on logical errors.

## Python skeleton (requests)

```python
import os, requests
from typing import Any

class ZabbixAPI:
    def __init__(self, url: str, token: str, timeout: int = 30):
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json-rpc',
            'Authorization': f'Bearer {token}',
        })
        self._id = 0

    def call(self, method: str, params: Any = None) -> Any:
        self._id += 1
        payload = {'jsonrpc': '2.0', 'method': method,
                   'params': params or {}, 'id': self._id}
        r = self.session.post(self.url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        body = r.json()
        if 'error' in body:
            e = body['error']
            raise RuntimeError(f"Zabbix API {method} failed: "
                               f"{e['code']} {e['message']} — {e.get('data','')}")
        return body['result']

zbx = ZabbixAPI(os.environ['ZBX_URL'], os.environ['ZBX_TOKEN'])
print(zbx.call('apiinfo.version'))
```

For more advanced use (async, bulk, connection pooling), use the **official `zabbix-utils`** Python library — it wraps this pattern and handles pagination.

## Idempotent template sync (CI)

Pipeline stages:

1. **Lint**: `yq` or a schema validator on the template YAML.
2. **Dry-run diff**: `configuration.importcompare` (available 6.4+) — returns the entities that would be created/updated/deleted. Fail the PR if any deletion is unexpected.
3. **Apply**: `configuration.import` with the exact rule set your policy allows:
   ```json
   {
     "format": "yaml",
     "rules": {
       "templates":       {"createMissing": true, "updateExisting": true},
       "items":           {"createMissing": true, "updateExisting": true, "deleteMissing": true},
       "triggers":        {"createMissing": true, "updateExisting": true, "deleteMissing": true},
       "discoveryRules":  {"createMissing": true, "updateExisting": true, "deleteMissing": true},
       "graphs":          {"createMissing": true, "updateExisting": true, "deleteMissing": true},
       "valueMaps":       {"createMissing": true, "updateExisting": true},
       "groups":          {"createMissing": true},
       "host_groups":     {"createMissing": true},
       "template_groups": {"createMissing": true}
     },
     "source": "<yaml text>"
   }
   ```
4. **Post-apply verify**: export the template again and compare to source — round-trip check.

## Host lifecycle from Salt/Ansible

The pillar/inventory is the source of truth. Reconcile on every run:

```python
def sync_host(zbx, hostname, iface_ip, template_ids, host_groups, macros, inventory):
    existing = zbx.call('host.get', {
        'filter': {'host': [hostname]},
        'selectInterfaces': ['interfaceid','ip','port','type','main','useip'],
        'selectParentTemplates': ['templateid'],
        'selectHostGroups': ['groupid'],
        'selectMacros': ['macro','value','type','description'],
    })
    payload = {
        'host': hostname,
        'interfaces': [{
            'type': 1, 'main': 1, 'useip': 1,
            'ip': iface_ip, 'dns': '', 'port': '10050',
            'details': [],
        }],
        'groups':    [{'groupid': gid} for gid in host_groups],
        'templates': [{'templateid': tid} for tid in template_ids],
        'macros':    macros,   # list of {macro,value,type,description}
        'inventory_mode': 1,   # automatic
        'inventory':  inventory,
        'tls_connect': 2, 'tls_accept': 2,  # PSK only
        'tls_psk_identity': f'psk-{hostname}',
        # PSK itself set via host.update after Vault fetch — not committed
    }
    if existing:
        payload['hostid'] = existing[0]['hostid']
        zbx.call('host.update', payload)
    else:
        zbx.call('host.create', payload)
```

Bulk-friendly variants:

- `host.massupdate` for identical changes to N hosts (add/remove template link, change proxy).
- `hostinterface.replacehostinterfaces` when the interface set changes — atomic replace, not delete+create.

## Common gotchas

- **`templates_clear` vs `templates`**: `template.update` with only `templates` *replaces* the linked template list; hosts that were previously linked to an unmentioned template get unlinked with history preserved but items disabled. Use `templates_clear` to explicitly detach.
- **Macro types on update**: sending a macro without `type` defaults to plain text. Always send `type` explicitly (0 = text, 1 = secret, 2 = vault).
- **Rate-limiting**: no built-in server-side limit, but `configuration.import` on a huge template is I/O and CPU intensive — serialize CI jobs on the same server, don't parallelize the import step.
- **API pagination**: `.get` methods return everything by default. On large fleets, page via `limit` + `offset` or add filters. `zabbix-utils` handles this.
- **Error codes**: `-32602` = invalid params (your fault), `-32500` = application error (state problem — e.g., trying to delete a host that doesn't exist). Handle both.
