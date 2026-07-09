# DevSecOps hardening reference

## Encryption baseline

### PSK (recommended default for agents)

PSK is symmetric, cheap to rotate, no CA to run. Every agent gets a unique PSK.

**Agent config** (`/etc/zabbix/zabbix_agent2.conf`):

```
TLSConnect=psk
TLSAccept=psk
TLSPSKIdentity=psk-<hostname>
TLSPSKFile=/etc/zabbix/psk/<hostname>.psk    # mode 0400, owner zabbix
```

**Zabbix host record** (via API):

```json
{
  "tls_connect": 2,
  "tls_accept": 2,
  "tls_psk_identity": "psk-<hostname>",
  "tls_psk": "<64-hex-char PSK>"
}
```

`tls_connect`/`tls_accept` bitmask: 1=unencrypted, 2=PSK, 4=cert. Combine for migration windows only.

**Generation**:

```bash
openssl rand -hex 32 > /etc/zabbix/psk/$(hostname).psk
chmod 0400 /etc/zabbix/psk/$(hostname).psk
chown zabbix:zabbix /etc/zabbix/psk/$(hostname).psk
```

### PSK rotation flow

Automated, no downtime:

1. Salt generates a new PSK, stores in Vault under `secret/zabbix/psk/<hostname>`.
2. Salt writes both **old and new** PSK to a transitional file — Zabbix agent 2 supports PSK rotation via `TLSPSKFile2` in newer versions; if not, plan the flip.
3. CI calls `host.update` with the new `tls_psk_identity` and `tls_psk`.
4. Salt restarts the agent (fast; agent2 is a supervisor, so items miss < 5s).
5. Old PSK is expired in Vault after a grace window.

### Certificate mode

For proxy↔server and any cross-org boundary, use certificate auth:

- Private CA (step-ca, HashiCorp Vault PKI, or your existing enterprise CA).
- Server config: `TLSCAFile`, `TLSCertFile`, `TLSKeyFile`.
- Set `TLSServerCertIssuer` / `TLSServerCertSubject` on the client side to pin the expected server cert — otherwise anyone with a CA-signed cert can impersonate.
- Rotate certs before expiry via the same CI that runs template sync; **monitor the cert expiry with Zabbix itself** using the `Template Module TLS certificate expiry by HTTP` module.

## Vault-backed secret macros

Zabbix 7.x supports HashiCorp Vault and CyberArk directly. Configure in `zabbix_server.conf`:

```
VaultProvider=HashiCorp
Vault=https://vault.example.com:8200
VaultTLSCAFile=/etc/zabbix/vault-ca.pem
VaultDBPath=secret/zabbix/db      # DB creds pulled at startup
```

Macro of type `Vault secret`:

```yaml
macros:
  - macro: '{$ES.PASSWORD}'
    type: VAULT
    value: 'secret/zabbix/elasticsearch:monitoring_password'
    description: 'Vault path is <mount>/<path>:<field>'
```

At each check, the server resolves the macro against Vault. Rotate the secret in Vault; Zabbix picks it up on next resolution (there is a small cache — check current version docs for TTL).

**Do not** put a Vault-backed macro in an item key that shows up in history — the macro is redacted in the UI but the resolved value may end up in the request URL/body. Put it in the item's HTTP agent authentication fields, or in an `Authorization` header expression that Zabbix knows to redact.

## User roles & permissions matrix

Model roles by **what they do**, not by team:

| Role                  | UI access       | API access        | Host groups                 | Notes |
|-----------------------|-----------------|-------------------|-----------------------------|-------|
| `role_readonly`       | read all        | read all          | all read                    | Support engineers, SRE on-call. |
| `role_operator`       | read + ack      | ack, event.*      | all read                    | NOC / L1. |
| `role_owner_<team>`   | read+edit hosts | host.*, item.*    | team's hostgroups edit      | Product teams managing their own hosts. |
| `role_template_editor`| read all + templates | template.*, item.*, discoveryrule.*, trigger.* | template groups edit | Monitoring team; PR reviewers. |
| `role_api_svc_ci`     | none (API only) | configuration.*, host.*, hostgroup.*, template.* | as needed | CI service account. |
| `role_api_svc_salt`   | none (API only) | host.*, hostinterface.*, hostmacro.* | as needed | Salt reactor. |
| `role_superadmin`     | all             | all               | all                         | 2 humans max, break-glass only, MFA-gated. |

Enforce via UI role definitions (7.x has fine-grained API method allow/deny lists).

## Audit log shipping (you already have ELK)

Zabbix 7.x writes a structured audit log with actor, resource, action, and old/new values. Ship it:

- Zabbix internal DB table `auditlog` — query via API `auditlog.get`, or read the log file if you enable file audit.
- Better: enable file-based audit log, tail with Filebeat, parse in Logstash into `zabbix-audit-YYYY.MM.DD`.
- Dashboard queries: "who changed template X in the last 24h", "which service accounts created hosts today", "any Super Admin logins outside the break-glass user".

Correlate with the existing Wazuh/auditbeat streams so any Zabbix DB or file mutation outside the audit-log path is flagged.

## Hardening checklist (server & proxy)

- [ ] Zabbix server, proxy, frontend on separate hosts (or at least separate systemd units on hardened hosts).
- [ ] Frontend behind reverse proxy (nginx) with:
  - HSTS
  - TLS 1.2+ only, modern ciphers
  - Rate limiting on `/api_jsonrpc.php`
  - IP allowlist on `/zabbix/` if internal
- [ ] Frontend session cookie: HTTPOnly, Secure, SameSite=Lax.
- [ ] `zabbix_server.conf` — `ListenIP` bound to internal iface; no exposure of trapper port 10051 to the internet.
- [ ] DB: dedicated user for Zabbix, read-only replica user for frontend if you split.
- [ ] DB TLS enabled (`DBTLSConnect=verify_full`, CA pinned).
- [ ] Server binary and PHP frontend from the official Zabbix repo, GPG-verified, pinned major version.
- [ ] SELinux/AppArmor in enforcing mode with the shipped Zabbix policy (do not disable).
- [ ] `zabbix` user is not a login user; owns only what it needs.
- [ ] Backups: DB dump + config bundle daily; encrypted at rest; restore-tested quarterly.

## Supply-chain: custom code review checklist

Custom JS preprocessing, agent2 plugins, external checks, webhook media, and Ansible/Salt modules are code:

- [ ] Reviewed via PR by another human.
- [ ] Linted (`shellcheck`, `pylint`, `eslint` as appropriate).
- [ ] Unit-tested with sample inputs including malformed/empty.
- [ ] Runs as `zabbix` user with no `NOPASSWD` sudo unless justified.
- [ ] External command paths absolute; no PATH-lookup shell injection surface.
- [ ] Any HTTP outbound goes to allowlisted hosts (agent2 plugins can enforce this).
- [ ] Webhook JS reviewed with same rigor as server-side code — it runs on the server.

## CVE / compliance-adjacent monitoring templates to build

Modules a senior Zabbix dev is expected to own:

- **Kernel/package CVE tracker**: nightly external check runs `apt list --upgradable` / `dnf updateinfo` (or a Wazuh vulnerability API pull), extracts CVE IDs above a severity threshold, emits an LLD list. Triggers on new critical CVEs on prod hostgroups.
- **TLS cert expiry**: HTTP agent → `openssl s_client` wrapper → JS extracts NotAfter → trigger at 30/14/7 days.
- **Auditd health**: agent item on `auditctl -s` — trigger if auditd is not enabled or not delivering.
- **Listening port drift**: agent item on `ss -tlnp | ...`, LLD ports, trigger on new port that isn't in `{$ALLOWED.LISTEN.PORTS}`.
- **Package version drift**: agent item on `dpkg -l <critical-pkg>`, compare against `{$EXPECTED.VERSION}`.
- **Zabbix agent config drift**: hash of the agent config, sent via active check; trigger on unexpected change.
- **User account drift**: LLD of local users; trigger on any user outside `{$ALLOWED.USERS.MATCHES}`.

These integrate cleanly with the existing Wazuh/Filebeat/auditbeat stack — Zabbix owns the "state changed → alert human" side, ELK owns the "search and forensics" side.
