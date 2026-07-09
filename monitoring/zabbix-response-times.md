# Monitoring SeyalRun module response times in Zabbix

Every API call is proxied through the **api-gateway**, which now records the latency of
each upstream module (identity / inventory / terminal / recording / automation /
zabbix-integration / metrics). Two ways to read it:

| Surface | Endpoint | Auth | Format |
|---|---|---|---|
| Zabbix HTTP Agent | `GET https://<edge-host>:8443/api/metrics/response-times` | PAT `Bearer sr_...` with `metrics:read` | JSON (LLD-ready) |
| Prometheus / agent2 | `GET http://api-gateway:8000/metrics` (internal) | none (internal net) | `seyalrun_upstream_latency_ms{service,stat}` |

Sample JSON:

```json
{
  "data": [
    {"{#SERVICE}": "inventory-service", "avg_ms": 41.2, "p50_ms": 38, "p95_ms": 120, "max_ms": 380, "count": 1820, "errors": 0}
  ],
  "services": { "inventory-service": { "avg_ms": 41.2, "p95_ms": 120, ... } }
}
```

## Steps (Zabbix UI — HTTP Agent, recommended)

1. **Create a PAT in SeyalRun**: Admin → Security → Personal Access Tokens → New, scope
   **`metrics:read`**. Copy the `sr_...` token once.

2. **Zabbix → Data collection → Hosts → `SeyalRun-Platform` → Items → Create item**
   - Name: `SeyalRun response-times raw`
   - Type: **HTTP agent**
   - Key: `seyalrun.response_times`
   - URL: `https://<edge-host>:8443/api/metrics/response-times`
   - Headers: `Authorization: Bearer sr_xxxxx`
   - Type of information: **Text**, Update interval `60s`
   - (self-signed cert: enable "Don't verify host/peer" or upload the CA)

3. **Create a Discovery rule (LLD)**
   - Type: **Dependent item**, Master item: `SeyalRun response-times raw`
   - Key: `seyalrun.rt.discovery`
   - Preprocessing → JSONPath: `$.data`

4. **Item prototype** (one per discovered module)
   - Name: `p95 latency [{#SERVICE}]`
   - Type: **Dependent item**, Master: `SeyalRun response-times raw`
   - Key: `seyalrun.rt.p95[{#SERVICE}]`
   - Type of information: **Numeric (float)**, Units: `ms`
   - Preprocessing → JSONPath: `$.services['{#SERVICE}'].p95_ms`
   - (repeat for `avg_ms`, `errors` if wanted)

5. **Trigger prototype**
   - Name: `High latency on {#SERVICE} (p95 > 1s)`
   - Expression: `last(/SeyalRun-Platform/seyalrun.rt.p95[{#SERVICE}]) > 1000`
   - Severity: Warning (add a second at `>3000` = High)

6. **Graph / Dashboard**: Monitoring → Latest data → filter `p95 latency` → check the
   series → *Display graph* for a per-module latency chart, or add an "Item value"/"Graph
   (classic)" widget to a Zabbix dashboard.

## Alternative — zabbix-agent2 (already running as a sidecar)

The `seyalrun-agent` container can scrape the internal Prometheus endpoint:

```
UserParameter=seyalrun.gw.metrics,curl -s http://api-gateway:8000/metrics
```

Then in Zabbix use item key `seyalrun.gw.metrics` with a Prometheus preprocessing step,
pattern `seyalrun_upstream_latency_ms{service="inventory-service",stat="p95_ms"}`.

> Values are a rolling window of the last 500 requests per module, so they reflect recent
> live latency rather than an all-time average.
