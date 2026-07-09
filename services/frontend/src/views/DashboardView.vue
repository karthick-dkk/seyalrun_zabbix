<template>
  <AppShell>
    <div class="page">
      <div class="page-header">
        <div>
          <div class="page-title">Dashboard</div>
          <div class="page-subtitle">Welcome back, {{ auth.user?.username }}</div>
        </div>
        <button class="btn btn-icon" title="Refresh" @click="load"><svg style="width:14px;height:14px;display:block" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"/></svg></button>
      </div>

      <!-- ── KPI row ──────────────────────────────────────────────────────── -->
      <div class="kpi-row">
        <div class="kpi">
          <div class="kpi-value">{{ m?.hosts?.total ?? '—' }}</div>
          <div class="kpi-label">Total Hosts</div>
          <div class="kpi-sub kpi-ok">{{ m?.hosts?.reachable ?? 0 }} reachable</div>
        </div>
        <div class="kpi">
          <div class="kpi-value" :class="{ 'kpi-accent': (m?.sessions?.active ?? 0) > 0 }">{{ m?.sessions?.active ?? '—' }}</div>
          <div class="kpi-label">Active Sessions</div>
          <div class="kpi-sub">live SSH connections</div>
        </div>
        <div class="kpi">
          <div class="kpi-value">{{ m?.jobs?.today ?? '—' }}</div>
          <div class="kpi-label">Jobs Today</div>
          <div class="kpi-sub">{{ m?.jobs?.week ?? 0 }} this week</div>
        </div>
        <div class="kpi">
          <div class="kpi-value" :class="successClass">{{ m?.jobs?.success_rate ?? '—' }}<span v-if="m?.jobs">%</span></div>
          <div class="kpi-label">Success Rate</div>
          <div class="kpi-sub">{{ m?.jobs?.ok_week ?? 0 }} ok / {{ m?.jobs?.failed_week ?? 0 }} failed</div>
        </div>
        <div class="kpi">
          <div class="kpi-value">{{ m?.jobs?.auto ?? '—' }}</div>
          <div class="kpi-label">Auto-Triggered</div>
          <div class="kpi-sub">{{ m?.jobs?.manual ?? 0 }} manual</div>
        </div>
      </div>

      <!-- ── Risk row (admin) ─────────────────────────────────────────────── -->
      <div v-if="auth.isAdmin && hasRisks" class="kpi-row">
        <div class="kpi kpi-risk" :class="{ 'kpi-risk--on': (m?.credentials?.weak ?? 0) > 0 }" style="cursor:pointer" @click="$router.push('/admin/credentials')">
          <div class="kpi-value">{{ m?.credentials?.weak ?? 0 }}</div><div class="kpi-label">Weak Credentials</div>
        </div>
        <div class="kpi kpi-risk" :class="{ 'kpi-risk--on': (m?.credentials?.rotation_due ?? 0) > 0 }" style="cursor:pointer" @click="$router.push('/admin/credentials')">
          <div class="kpi-value">{{ m?.credentials?.rotation_due ?? 0 }}</div><div class="kpi-label">Rotation Due</div>
        </div>
        <div class="kpi kpi-risk" :class="{ 'kpi-risk--on': (m?.sessions?.failed_24h ?? 0) > 0 }">
          <div class="kpi-value">{{ m?.sessions?.failed_24h ?? 0 }}</div><div class="kpi-label">Failed Sessions 24h</div>
        </div>
        <div class="kpi kpi-risk" :class="{ 'kpi-risk--on': (m?.acl_blocks?.length ?? 0) > 0 }">
          <div class="kpi-value">{{ m?.acl_blocks?.length ?? 0 }}</div><div class="kpi-label">ACL Blocks</div>
        </div>
      </div>

      <!-- ── 7-Day Activity ───────────────────────────────────────────────── -->
      <div class="card" style="margin-bottom:16px">
        <div class="card-header">7-Day Activity</div>
        <div class="chart">
          <div v-for="d in (m?.activity_7d || [])" :key="d.date" class="chart-col">
            <div class="chart-bars">
              <div class="chart-bar chart-bar--jobs" :style="{ height: barH(d.jobs) }" :title="`${d.jobs} jobs`"></div>
              <div class="chart-bar chart-bar--sessions" :style="{ height: barH(d.sessions) }" :title="`${d.sessions} sessions`"></div>
            </div>
            <div class="chart-label">{{ shortDate(d.date) }}</div>
          </div>
          <div v-if="!(m?.activity_7d || []).length" class="muted" style="padding:24px">No activity data.</div>
        </div>
        <div class="chart-legend">
          <span><i class="dot dot--jobs"></i> Jobs</span>
          <span><i class="dot dot--sessions"></i> Sessions</span>
        </div>
      </div>

      <!-- ── Recent Jobs + Top Playbooks ──────────────────────────────────── -->
      <div class="grid-2">
        <div class="card">
          <div class="card-header">Recent Jobs <router-link to="/jobs" class="hdr-link">All Jobs →</router-link></div>
          <table class="table" style="font-size:13px">
            <thead><tr><th>Status</th><th>Playbook</th><th>Triggered</th><th>When</th></tr></thead>
            <tbody>
              <tr v-for="j in (m?.recent_jobs || [])" :key="j.id" style="cursor:pointer" @click="$router.push(`/jobs/${j.id}`)">
                <td><span :class="statusBadge(j.status)">{{ j.status }}</span></td>
                <td>{{ shortName(j.playbook) }}</td>
                <td style="color:var(--text2)">{{ trigLabel(j.triggered_by) }}</td>
                <td style="color:var(--text2)">{{ ago(j.ts) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!(m?.recent_jobs || []).length" class="muted" style="padding:20px">No jobs yet.</div>
        </div>

        <div class="card">
          <div class="card-header">Top Playbooks</div>
          <table class="table" style="font-size:13px">
            <thead><tr><th>Playbook</th><th class="r">Runs</th></tr></thead>
            <tbody>
              <tr v-for="p in (m?.top_playbooks || [])" :key="p.name">
                <td>{{ shortName(p.name) }}</td><td class="r"><span class="badge badge-blue">{{ p.runs }}</span></td>
              </tr>
            </tbody>
          </table>
          <div v-if="!(m?.top_playbooks || []).length" class="muted" style="padding:20px">No runs yet.</div>
        </div>
      </div>

      <!-- ── Active Sessions + Recent Failures ────────────────────────────── -->
      <div class="grid-2" style="margin-top:16px">
        <div class="card">
          <div class="card-header">Active Sessions <router-link to="/sessions" class="hdr-link">All →</router-link></div>
          <table class="table" style="font-size:13px">
            <thead><tr><th>User</th><th>Host</th><th>Since</th></tr></thead>
            <tbody>
              <tr v-for="(sx, i) in (m?.active_sessions || [])" :key="i">
                <td>{{ sx.user }}</td><td>{{ sx.host }}</td><td style="color:var(--text2)">{{ ago(sx.since) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!(m?.active_sessions || []).length" class="muted" style="padding:20px">No active sessions.</div>
        </div>

        <div class="card">
          <div class="card-header">Recent Failures</div>
          <table class="table" style="font-size:13px">
            <thead><tr><th>Playbook</th><th>When</th></tr></thead>
            <tbody>
              <tr v-for="(fx, i) in (m?.recent_failures || [])" :key="i">
                <td style="color:#f87171">{{ shortName(fx.playbook) }}</td><td style="color:var(--text2)">{{ ago(fx.ts) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!(m?.recent_failures || []).length" class="muted" style="padding:20px">No recent failures. 🎉</div>
        </div>
      </div>

      <!-- ACL blocks (admin) -->
      <div v-if="auth.isAdmin && (m?.acl_blocks || []).length" class="card" style="margin-top:16px">
        <div class="card-header">Recent ACL Blocks</div>
        <table class="table" style="font-size:13px">
          <thead><tr><th>Command</th><th>User</th><th>Host</th><th>When</th></tr></thead>
          <tbody>
            <tr v-for="(b, i) in m.acl_blocks" :key="i">
              <td><code style="color:#f87171">{{ b.command }}</code></td>
              <td>{{ b.user || '—' }}</td><td style="color:var(--text2)">{{ b.host || '—' }}</td><td style="color:var(--text2)">{{ ago(b.ts) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '@/components/layout/AppShell.vue'
import { useAuthStore } from '@/stores/auth'
import { getToken } from '@/api/client'

const auth = useAuthStore()
const m = ref<any>(null)

async function load() {
  try {
    const r = await fetch('/api/v1/metrics/dashboard', { headers: { Authorization: `Bearer ${getToken() || ''}` } })
    if (r.ok) m.value = await r.json()
  } catch { /* metrics-service optional */ }
}

const maxActivity = computed(() => {
  const a = m.value?.activity_7d || []
  return Math.max(1, ...a.map((d: any) => Math.max(d.jobs, d.sessions)))
})
function barH(v: number) { return `${Math.round((v / maxActivity.value) * 100)}%` }

const successClass = computed(() => {
  const r = m.value?.jobs?.success_rate
  if (r == null) return ''
  return r >= 90 ? 'kpi-ok' : r >= 70 ? 'kpi-warn' : 'kpi-bad'
})
const hasRisks = computed(() => !!m.value?.credentials || !!m.value?.sessions)

function statusBadge(s: string) {
  if (s === 'success') return 'badge badge-green'
  if (s === 'failed' || s === 'error') return 'badge badge-red'
  if (s === 'running' || s === 'pending') return 'badge badge-blue'
  return 'badge badge-gray'
}
function trigLabel(t: string) {
  if (!t) return '—'
  if (t.startsWith('user:')) return 'Manual'
  if (t.startsWith('schedule:')) return 'Schedule'
  if (t.startsWith('zabbix')) return 'Zabbix'
  return t.split(':')[0]
}
function shortName(n: string) { return n && n.length > 26 ? n.slice(0, 24) + '…' : (n || '—') }
function shortDate(iso: string) {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString(undefined, { month: 'short', day: '2-digit' })
}
function ago(iso?: string | null) {
  if (!iso) return '—'
  const secs = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return `${Math.floor(secs / 86400)}d ago`
}

onMounted(load)
</script>

<style scoped>
.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-bottom: 16px; }
.kpi { background: var(--bg2); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; text-align: center; }
.kpi-value { font-size: 34px; font-weight: 700; color: var(--text); line-height: 1.1; }
.kpi-accent { color: #3fb950; }
.kpi-ok { color: #3fb950; }
.kpi-warn { color: #e3b341; }
.kpi-bad { color: #f85149; }
.kpi-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text2); margin-top: 6px; }
.kpi-sub { font-size: 11px; color: var(--text2); margin-top: 3px; }
.kpi-risk .kpi-value { color: var(--text2); font-size: 28px; }
.kpi-risk--on .kpi-value { color: #e3b341; }

.chart { display: flex; align-items: flex-end; gap: 4px; height: 150px; padding: 16px 16px 0; }
.chart-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
.chart-bars { display: flex; align-items: flex-end; gap: 3px; height: 110px; }
.chart-bar { width: 12px; border-radius: 3px 3px 0 0; min-height: 2px; transition: height 0.3s; }
.chart-bar--jobs { background: #58a6ff; }
.chart-bar--sessions { background: #3fb950; }
.chart-label { font-size: 11px; color: var(--text2); margin-top: 8px; }
.chart-legend { display: flex; gap: 18px; padding: 8px 16px 14px; font-size: 12px; color: var(--text2); }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 5px; }
.dot--jobs { background: #58a6ff; }
.dot--sessions { background: #3fb950; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 860px) { .grid-2 { grid-template-columns: 1fr; } }
.hdr-link { font-size: 12px; font-weight: 500; color: var(--accent2); text-decoration: none; }
.table .r { text-align: right; }
.muted { text-align: center; color: var(--text2); font-size: 13px; }
</style>
