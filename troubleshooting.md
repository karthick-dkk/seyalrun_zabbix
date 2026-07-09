# Troubleshooting reference

Start every triage from the server's own health. `Zabbix server health` template exposes internal items — always link it to the Zabbix server host itself.

## First-look diagnostics

Internal items to check in this order:

| Item | What it tells you |
|------|-------------------|
| `zabbix[queue,10m]` | Number of monitored items delayed > 10 min. Should be near 0. |
| `zabbix[wcache,values,pfree]` | History write cache free %. Below 25% → server can't drain to DB. |
| `zabbix[wcache,history,pfree]` | History cache free %. Below 25% → pollers stall. |
| `zabbix[wcache,trend,pfree]` | Trend cache. Sustained low = DB write bottleneck. |
| `zabbix[rcache,buffer,pfree]` | Config cache free %. Below 10% → increase `CacheSize`. |
| `zabbix[vcache,buffer,pfree]` | Value cache — trigger/preproc reads history from here. Sustained low → increase `ValueCacheSize`. |
| `zabbix[process,poller,avg,busy]` | Avg poller utilization %. Above 75% → `StartPollers` too low. |
| `zabbix[process,preprocessing manager,avg,busy]` | If saturated, JS preprocessing is expensive — profile the scripts. |
| `zabbix[process,history syncer,avg,busy]` | Above 75% → DB write path is the bottleneck. |
| `zabbix[process,alerter,avg,busy]` | If saturated during storms, alerters are the choke point — scale `StartAlerters`. |

## Common failure modes

### Queue growing, `queue,10m` climbing

- Check `[process,poller,avg,busy]` — if high, raise `StartPollers` / `StartPollersUnreachable` / `StartHTTPPollers`.
- Check for a specific host with `zabbix_get -s <host> -k agent.ping` and look at server log — if one host is timing out and pollers are blocking on it, move it to `StartPollersUnreachable`.
- If it's a proxy: check proxy `[queue]` internal item too — proxy queues drain into server queue.

### Preprocessing manager pegged at 100%

- Almost always: an expensive JS preprocessing step running at high frequency.
- Zabbix 7.4 lets items with no preprocessing and no dependents bypass the manager entirely — audit for items that don't actually need preprocessing (raw int coming from HTTP JSON via JSONPath — do you need the JS at all?).
- Split into more preprocessing workers: `StartPreprocessors`.
- Move heavy transforms to the source (proxy-side external check that emits already-shaped JSON).

### History syncer saturated

- DB write bottleneck. Look at DB:
  - Postgres: `pg_stat_activity`, check `history*` insert wait; TimescaleDB chunk size; autovacuum on history tables.
  - MySQL: partition status on history tables; `innodb_flush_log_at_trx_commit`.
- Increase `HistoryStorageDateIndex=1` if using Elasticsearch for history — offloads history writes from RDBMS.
- Consider dropping history for high-cardinality items and keeping only trends.

### Value cache slow (triggers fire late)

- `[vcache,buffer,pfree]` low → increase `ValueCacheSize`.
- `[vcache,cache,mode]` = 1 means low-memory mode kicked in — server drops old values from cache; trigger evaluation is now hitting the DB. Fix ASAP.

### Elasticsearch cluster state bloat (Karthi's known scenario)

Symptom: LS pipelines timing out publishing to ES; ES cluster state size > 50 MB; GC pressure on masters; Zabbix triggers on ES health flapping.

- Root cause historically: dynamic field mapping on log indices exploding fields. Check `_cluster/stats` → `indices.mappings.field_types.count`.
- Force strict mappings on `logstash-*` templates; `index.mapper.dynamic: false` where possible.
- Roll indices via ILM/rollover to smaller chunks.
- Zabbix side: add HTTP agent item on `_cluster/state?filter_path=metadata.templates` size — trigger before it bites.

### Logstash → Redis backlog

- Redis full → Filebeat/Beats stop shipping → Zabbix `zabbix[queue]` on server climbs because trapper items dependent on log-derived data go stale.
- Monitor `redis-cli info memory` (used_memory, maxmemory_policy) via agent2 Redis plugin.
- Redis policy: **`noeviction`** for durable pipelines (lose no logs; block producers); `allkeys-lru` only if you can tolerate loss.

### Salt-triggered agent restart storms

- Salt state that restarts `zabbix-agent2` on every minion → 300 hosts flap simultaneously → server sees 300 "unreachable" then "reachable" → alert flood.
- Use `onchanges` requisite on Salt state; only restart if the config actually changed.
- Set trigger dependency: `Zabbix agent is not available` should suppress child triggers during flap.

### Winlogbeat high-event-volume rendering errors

Not strictly Zabbix, but you'll see it as a gap in Windows log-derived metrics:

- Winlogbeat event rendering fails on very high-volume channels (Security with process auditing).
- Solution: filter at the channel level in `winlogbeat.yml`; forward raw events to Logstash and render there.
- Zabbix HTTP agent item on Winlogbeat status endpoint to catch when the beat stops shipping.

## When a template acts wrong after import

1. Confirm you imported into the **correct template group** — a template with the same name in a different group is a different object.
2. Check UUIDs — if the export shows a UUID and the import target already has one with the same UUID, it updates in place; different UUID = new object, orphaning history.
3. Round-trip: export the imported template, diff against source YAML. Zabbix will normalize whitespace and key order — use a semantic diff (`yq eval -P` on both).
4. Look at the import log (Reports → Audit log). It shows every entity created/updated with the actor and reason.

## Trigger flapping

- Check trigger expression — using `last()` on a noisy metric is the #1 cause.
- Convert to `avg(/host/key, 5m) > threshold` with a matching recovery expression.
- Add trigger dependencies so parent unreachable states suppress child triggers.
- If flapping only during business hours: check for LLD churn re-creating item every discovery.

## "Not supported" items

Right-click the item in Latest data → Info shows the exact server message. Common causes:

- Preprocessing step threw and no error handler → item marked not supported.
- HTTP agent got 401/403 → macro credential not resolving (Vault down? macro type wrong?).
- SNMP OID doesn't exist on this device → LLD filter should have caught it; fix the filter.
- `system.run` denied → check agent `AllowKey` / `DenyKey` and audit whether you actually need `system.run` at all.

## Zabbix upgrade playbook (short form)

1. Read the version-specific upgrade notes for every intermediate major version — do not skip minors that changed the DB schema.
2. Snapshot the DB.
3. Upgrade **server** first, then **proxies**, then **agents** — agents are forward-compatible with newer servers within one major version.
4. Frontend PHP requirements often bump — verify `php -v` before starting.
5. After upgrade: run through your own dashboards; check `apiinfo.version`; re-export every template and commit — some minor exports change format between versions.
