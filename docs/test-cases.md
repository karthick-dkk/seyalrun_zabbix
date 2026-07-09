# SeyalRun v2 — Production Test Case Suite

Maintained alongside the codebase. Use for security review, smoke testing after
every deploy, regression testing after any RBAC/auth/terminal change, and as a
code-review checklist for PRs touching these areas.

**Tags**: `[security]` — a defense boundary; failure = a real vulnerability.
`[smoke]` — run after every deploy, fast, high-signal.
`[regression]` — protects a specific bug fix from recurring.

**Conventions**: `TC-<MODULE>-<NNN>`. "Authorized" means an explicit
`za_authorizations` row exists for the (user, host, credential) combination.
Test accounts should be created via an existing superadmin (`test-admin` or
equivalent), never by editing seed data directly.

---

## 1. Authentication

| ID | Precondition | Steps | Expected | Tags |
|---|---|---|---|---|
| TC-AUTH-001 | Valid account | Log in with correct username/password | `200`, JWT issued, redirected to first allowed page | `[smoke]` |
| TC-AUTH-002 | Valid account | Log in with wrong password | `401 invalid username or password` | `[smoke]` |
| TC-AUTH-003 | — | 5 failed logins within the lockout window (`login_max_failures`) | Further attempts `429` for `login_lockout_seconds`, even with the correct password | `[security]` |
| TC-AUTH-004 | Locked-out account, wait for lockout to expire | Log in with correct password after expiry | `200`, lockout counter resets | `[regression]` (lockout-reset-on-expiry fix) |
| TC-AUTH-005 | New account with `must_change_password=true` | Log in with default password | Response requires password change before any other endpoint works; gateway 403s everything except `/auth/change-password` and `/auth/nav` | `[security]` |
| TC-AUTH-006 | mid `must_change_password` flow | Submit a new password | Fresh JWT issued, `must_change_password=false`, full access restored | `[smoke]` |
| TC-AUTH-007 | Logged in | Wait past JWT expiry (`jwt_expire_minutes`), call any endpoint | `401`, client redirected to login | `[security]` |
| TC-AUTH-008 | Logged in | Click logout | Token cleared client-side, redirected to `/login`, old token unusable if it had a server-side revocation path (PATs) | `[smoke]` |
| TC-AUTH-009 | — | Forced through login by the router guard with `?redirect=/terminal?zbx_host=X&autoconnect=1` | After successful login, lands on the **exact** original target, not `/` | `[regression]` (hash-routing redirect fix) |

## 2. Kiosk mode (Zabbix → Terminal direct connect)

| ID | Precondition | Steps | Expected | Tags |
|---|---|---|---|---|
| TC-KIOSK-001 | Not logged in; Zabbix "Terminal" link for host A (real `zbx_host`) | Click link → forced to login → authenticate | JWT contains `kiosk:true`, `kiosk_host_id` = host A's SeyalRun id | `[security][smoke]` |
| TC-KIOSK-002 | Kiosk token bound to host A | `POST /ssh/sessions {host_id: A}` | `201`, session created | `[smoke]` |
| TC-KIOSK-003 | Kiosk token bound to host A; account also separately authorized for host B | `POST /ssh/sessions {host_id: B}` | `403 kiosk session is bound to a different host` — even though otherwise authorized | `[security]` |
| TC-KIOSK-004 | Kiosk session to host A already active | Same token, `POST /ssh/sessions {host_id: A}` again | `403 a kiosk session is already active for this host` | `[security]` |
| TC-KIOSK-005 | Two different accounts, both kiosk-bound to host A | Each creates a session to host A | Both succeed independently — one user's session never blocks another's | `[regression]` |
| TC-KIOSK-006 | Kiosk session to host A ends (drops) | Reconnect to host A within 2 minutes | Same session ID/record reused, not a new row | `[smoke]` |
| TC-KIOSK-007 | Kiosk session to host A ended >2 minutes ago | Reconnect to host A | New session created (still bound to host A only) | `[regression]` |
| TC-KIOSK-008 | Login with an unresolvable/bogus `kiosk_target` (bad Zabbix id) | Complete login | Login still succeeds; no `kiosk` claim minted; behaves as an ordinary session | `[security]` (fail-open must never mean fail-insecure *or* fail-closed on login itself) |
| TC-KIOSK-009 | Already logged in (normal session, no kiosk claim) | Open the same Zabbix Terminal link | No kiosk mode; full workbench with host sidebar renders, scoped to normal PAM-authorized hosts | `[smoke]` |
| TC-KIOSK-010 | Active kiosk session | In the terminal UI: host sidebar, "New Connection", "Split Horizontal/Vertical", tab-add button | All hidden; only "Close Window" ends the session | `[smoke]` |
| TC-KIOSK-011 | Kiosk token | Raw `GET /hosts` call (bypass UI) | Returns **only** the one bound host, never the full authorized list | `[security]` |
| TC-KIOSK-012 | Kiosk token, password-change forced at login | Complete forced change | New token issued by `/auth/change-password` still carries the same `kiosk`/`kiosk_host_id` claims | `[regression]` |

## 3. RBAC — role × module matrix

Run against a fresh account per role (`superadmin`/`admin`/`support`/`user`),
created by an existing superadmin. Full segment list: `hosts, host-groups,
credentials, credential-templates, zones, authorizations, projects,
job-templates, schedules, job-runs, secret-management-jobs, trigger-bindings,
triggers, ssh, recordings, metrics, audit, users, roles, log-backend, settings,
api-tokens, command-filters, command-groups, login-acls, housekeeping`.

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-RBAC-001 | `GET /auth/nav` as each role | Matches the documented nav matrix exactly (dashboard/hosts/assets/sessions/terminal/recordings/jobs/automation + all `admin.*`) | `[security][smoke]` |
| TC-RBAC-002 | `admin`/`support`: `PUT /users/{existing}` | `200` — can edit an existing user's role/password/active state | `[smoke]` |
| TC-RBAC-003 | `admin`/`support`: `POST /users` (create) | `403` — neither can create new accounts | `[security]` |
| TC-RBAC-004 | `admin`/`support`: `POST /roles` (create) | `403` — neither can create role definitions | `[security]` |
| TC-RBAC-005 | `support`: `POST /hosts`, `POST /credentials`, `POST /job-templates` | All succeed — full CRUD on assets/credentials/playbooks | `[smoke]` |
| TC-RBAC-006 | `support`: `POST /ssh/sessions` for a host with no authorization row | `403` — support does **not** bypass the authorization gate despite broad CRUD | `[security]` |
| TC-RBAC-007 | `user`: `GET /hosts`, `GET /job-templates`, `GET /job-runs`, `GET /recordings` | All `200` (read-only) | `[smoke]` |
| TC-RBAC-008 | `user`: `POST /job-templates/{id}/run` for an authorized host | `202` — can run an existing playbook | `[smoke]` |
| TC-RBAC-009 | `user`: `POST /job-templates` (create) | `403` — cannot create/edit templates, only run them | `[security]` |
| TC-RBAC-010 | `user`: `GET /credentials`, `GET /authorizations`, `GET /log-backend`, etc. | `403` — deny-by-default on everything outside the documented module list | `[security]` |
| TC-RBAC-011 | `admin`/`support`: `GET /log-backend`, `GET /settings/integration`, `GET /api-tokens`, `GET /command-filters`, `GET /command-groups`, `GET /login-acls`, `GET /housekeeping/jobs` | All `403` for both roles | `[security]` |
| TC-RBAC-012 | `superadmin`: all of the above | Every call succeeds, no exceptions | `[smoke]` |
| TC-RBAC-013 | Any role: `GET /hosts` | The `[GET /hosts]` list is PAM-filtered to authorized hosts for every role except `superadmin`/`admin`/`support` | `[security]` |
| TC-RBAC-014 | `HostsView.vue` load, as a `user`-role account authorized for hosts but not zones/credentials/authorizations | Page renders the host list even though the auxiliary calls 403 | `[regression]` (Promise.all blanking bug) |

## 4. Hosts / Assets

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-HOST-001 | Create a native host | Appears with "S" (SeyalRun) badge | `[smoke]` |
| TC-HOST-002 | Run Zabbix host sync | Zabbix hosts appear/update with "Z" badge, `zabbix_hostid` set | `[smoke]` |
| TC-HOST-003 | Edit an existing Zabbix-synced host (name/IP/zone — anything except the Zabbix link) | `zabbix_hostid` is preserved after save, badge stays "Z" | `[regression]` (wipe-on-edit bug) |
| TC-HOST-004 | Attempt to delete a Zabbix-synced host | `409`, blocked; delete button hidden/disabled in UI | `[regression][security]` |
| TC-HOST-005 | Delete a native ("S") host | Succeeds normally | `[smoke]` |
| TC-HOST-006 | Delete a host that belongs to a host-group | Succeeds (no `AssertionError` from the group-membership FK) | `[regression]` |
| TC-HOST-007 | Sort by Host / IP column, both directions | List re-orders correctly | `[smoke]` |
| TC-HOST-008 | Search by host name, IP, and host-group name (Assets page) | All three match correctly | `[smoke]` |

## 5. Credentials

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-CRED-001 | Create/edit/delete a credential as `admin`/`support` | Succeeds | `[smoke]` |
| TC-CRED-002 | `GET /credentials/{id}/reveal` as a role without the `reveal` flag | `403` even if the role has general `credentials` read | `[security]` |
| TC-CRED-003 | `GET /credentials/{id}/reveal` as `superadmin`/`admin` (both carry `reveal`) | `200`, secret returned | `[smoke]` |
| TC-CRED-004 | Link/unlink a credential to a host | Reflected immediately in that host's authorized-credential set | `[smoke]` |

## 6. Authorizations

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-AUTHZ-001 | Create an authorization scoped to a specific host + credential | Grants exactly that pair, nothing broader | `[smoke]` |
| TC-AUTHZ-002 | Create an authorization scoped to a host-group / user-group | Applies to every member correctly | `[smoke]` |
| TC-AUTHZ-003 | Authorization with `date_start` in the future | Not yet effective — `POST /ssh/sessions` still `403` until that time | `[security]` |
| TC-AUTHZ-004 | Authorization with `date_expired` in the past | No longer effective — `403` | `[security]` |
| TC-AUTHZ-005 | Attempt to remove the last superadmin-granting role/group binding | Blocked — guard against total lockout | `[security]` |
| TC-AUTHZ-006 | `POST /ssh/sessions` with an explicit `credential_id` not in the caller's authorized set for that host | `403 credential not authorized for this host`, even if that credential is valid for the host in general | `[security][regression]` |

## 7. Terminal / Sessions

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-TERM-001 | Authorized user connects via Terminal page | Session created, WS connects, shell responds | `[smoke]` |
| TC-TERM-002 | Session recorded under the **actual** authenticated caller | `SessionOut.username` matches the real logged-in identity, never a stale/shared "Admin" from browser reuse | `[regression]` |
| TC-TERM-003 | A command-filter with `default_deny` bound to the user/host | Unlisted commands are blocked mid-session | `[security]` |
| TC-TERM-004 | A command-filter allow-list | Listed commands pass, others denied | `[security]` |
| TC-TERM-005 | Session ends | Full frame recording posted to recording-service | `[smoke]` |
| TC-TERM-006 | User A tries `DELETE /ssh/sessions/{id}` for user B's session | `403` — termination is self-scoped except for admin/superadmin | `[security]` |
| TC-TERM-007 | `admin`/`superadmin` terminates another user's session | Succeeds | `[smoke]` |
| TC-TERM-008 | See Kiosk mode section (§2) for the Zabbix deep-link path | — | — |

## 8. Automation / Playbooks

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-AUTO-001 | `admin`/`support` creates a job template | Succeeds | `[smoke]` |
| TC-AUTO-002 | `user` runs an existing template against an authorized host | `202`, job executes, output visible in Job Runs | `[smoke]` |
| TC-AUTO-003 | `user` attempts to create/edit/delete a template | `403` for all three | `[security][regression]` |
| TC-AUTO-004 | Schedule a recurring job | Fires at the scheduled time, appears in Job Runs | `[smoke]` |
| TC-AUTO-005 | Zabbix trigger fires a matching binding (auto-dispatch) | Job runs automatically, result posted back to the Zabbix event if `post_result_to_zabbix` is set | `[smoke]` |
| TC-AUTO-006 | Zabbix trigger with no matching binding | No dispatch — silent no-op, not an error | `[smoke]` |
| TC-AUTO-007 | Manual "Run from Zabbix" webhook, valid HMAC signature | `202`, job dispatched | `[security][smoke]` |
| TC-AUTO-008 | Manual webhook, invalid/missing HMAC signature | `401` | `[security]` |
| TC-AUTO-009 | Manual webhook, identical signed body replayed within the replay window | Second call `401 replay detected` | `[security]` |
| TC-AUTO-010 | Manual webhook, same event/trigger/binding but a *different* body within 10s | Second call `202 in_progress` (debounce), not a duplicate dispatch | `[regression]` |
| TC-AUTO-011 | Console "Run from Zabbix" (URL path) with `zbx_event_id` | Job runs, full output posted back to the originating Zabbix Problem | `[smoke]` |
| TC-AUTO-012 | Full output exceeds Zabbix's message length limit | Correctly chunked across multiple acknowledge messages, none truncated silently mid-line | `[regression]` |

## 9. Log Backend

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-LOG-001 | Configure Elasticsearch backend, TLS verify **off** | Connection test succeeds against a self-signed ES; log lines actually ship | `[smoke]` |
| TC-LOG-002 | Configure S3 backend | Connection test succeeds (write-probe, not just `HeadBucket`); log lines ship as gzipped ndjson objects | `[smoke]` |
| TC-LOG-003 | Routing matrix: command+audit → ES, recordings → S3, app → local | Each category ships only to its configured target(s); verify by inspecting the actual ES index / S3 objects | `[smoke]` |
| TC-LOG-004 | Combine all three backends (local+S3+ES) for one category | All three receive it | `[smoke]` |
| TC-LOG-005 | ES backend briefly unreachable/misconfigured | Shipper retries, does **not** advance the file offset and silently drop lines | `[regression][security]` (silent-loss bug) |
| TC-LOG-006 | One backend target fails while another succeeds for the same tick | Per-target offsets advance independently — no duplicate re-delivery to the succeeding target | `[regression]` |

## 10. Admin modules

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-ADMIN-001 | Zabbix user/group sync | New Zabbix users provisioned with the shipped default password + forced change; existing accounts' password/role/active state untouched | `[smoke][security]` |
| TC-ADMIN-002 | Assign a role to a Zabbix-synced group | All current members immediately inherit it via effective-roles resolution | `[smoke]` |
| TC-ADMIN-003 | Edit a Zabbix-synced user-group's name/description | `zabbix_usrgrpid` preserved | `[regression]` |
| TC-ADMIN-004 | `RolesAdmin.vue` create/edit/delete controls | Visible only to `superadmin` (not `admin`, matching the backend's `roles: [GET]`-only grant for admin/support) | `[regression]` |
| TC-ADMIN-005 | Users/Groups "+ User" / "+ Group" buttons | Visible only to `superadmin` | `[regression]` |
| TC-ADMIN-006 | Security / Housekeeping / Log Backend / Integration nav items | Hidden for every role except `superadmin` | `[security]` |
| TC-ADMIN-007 | `admin.integration` nav visibility | Correctly reflects `settings` segment access, not `trigger-bindings` | `[regression]` |

## 11. Cross-cutting

| ID | Steps | Expected | Tags |
|---|---|---|---|
| TC-X-001 | Any authorized write by a non-admin role (e.g. `support` creating a host) | Succeeds even though the downstream service's own guard is hardcoded to `admin`/`superadmin` — the gateway vouches `admin` downstream for gateway-authorized writes | `[regression]` (write-vouching mechanism) |
| TC-X-002 | `ssh` segment specifically | Downstream role is **never** vouched/elevated for `ssh`, even on writes — the real role is always forwarded, preserving self-scoping (see TC-TERM-006) | `[security]` |
| TC-X-003 | Every user-facing mutation (create/edit/delete host, user, credential, authorization, session) | Produces an audit-log entry with a resolvable actor | `[security]` |
| TC-X-004 | Burst of requests from one client | Rate limiter engages (`429`) at the configured threshold | `[security]` |
| TC-X-005 | Any endpoint call with a missing/invalid `X-Service-Token` between internal services | `401`, never silently trusted | `[security]` |
