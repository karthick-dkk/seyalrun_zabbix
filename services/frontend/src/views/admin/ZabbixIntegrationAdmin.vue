<template>
  <div>
    <div class="card">
      <div class="card-header">
        Zabbix Trigger Bindings
        <button class="btn btn-primary btn-sm" @click="openCreate">+ Trigger Binding</button>
      </div>
      <div style="padding:10px 16px;font-size:12px;color:var(--text2);border-bottom:1px solid var(--border)">
        Each binding maps a Zabbix trigger/event to a SeyalRun job template. When Zabbix fires a
        matching event via the webhook, a job run is automatically dispatched. Use the
        <strong>Manual Trigger</strong> button to also run it on-demand.
      </div>
      <table class="table">
        <thead>
          <tr><th>Name</th><th>Job Template</th><th>Trigger ID</th><th>Host Group</th><th>Min Severity</th><th>Post Result</th><th>Enabled</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="b in bindings" :key="b.id">
            <td style="font-weight:600">{{ b.name }}</td>
            <td style="color:var(--text2)">{{ templateName(b.job_template_id) }}</td>
            <td style="font-family:monospace;font-size:12px">{{ b.zabbix_triggerid || '— any —' }}</td>
            <td style="color:var(--text2)">{{ b.zabbix_host_group || '— any —' }}</td>
            <td><span class="badge badge-blue">{{ SEVERITY_LABELS[b.severity_min] ?? b.severity_min }}</span></td>
            <td style="text-align:center">{{ b.post_result_to_zabbix ? '✓' : '—' }}</td>
            <td><span :class="b.enabled ? 'badge badge-green' : 'badge badge-gray'">{{ b.enabled ? 'Enabled' : 'Disabled' }}</span></td>
            <td>
              <div style="display:flex;gap:8px;justify-content:flex-end">
                <button class="btn-pill btn-pill-outline" @click="manualTrigger(b)">▶ Run</button>
                <button class="btn-pill btn-pill-outline" @click="openEdit(b)">✎ Edit</button>
                <button class="btn-pill btn-pill-outline" style="color:var(--danger);border-color:var(--danger)" @click="removeBinding(b)">🗑</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!bindings.length && !loading" style="padding:24px;text-align:center;color:var(--text2)">No trigger bindings yet.</div>
      <div v-if="loading" style="padding:24px;text-align:center;color:var(--text2)">Loading…</div>
    </div>

    <!-- ── Zabbix UI wiring (copy-paste global scripts) ──────────────────── -->
    <div class="card" style="margin-top:16px">
      <div class="card-header">Connect from the Zabbix UI</div>
      <div style="padding:10px 16px;font-size:12px;color:var(--text2);border-bottom:1px solid var(--border)">
        Add these as <strong>global scripts</strong> in Zabbix (Alerts → Scripts, or Administration → Scripts).
        They appear in the host / problem context menus. Set a Zabbix macro
        <code>{$SEYALRUN_HMAC}</code> = your webhook HMAC secret for the one-click option.
      </div>
      <div style="padding:16px;display:flex;flex-direction:column;gap:18px">

        <div class="zs-block">
          <div class="zs-title">1 · SSH Terminal from a host <span class="badge badge-blue">URL · Manual host action</span></div>
          <div class="zs-desc">Opens SeyalRun's terminal and auto-connects using the credential the operator is authorized for. Secured by SeyalRun login + RBAC.</div>
          <div class="zs-code"><code>{{ sshUrl }}</code><button class="btn-pill btn-pill-outline" @click="copy(sshUrl)">Copy</button></div>
        </div>

        <div class="zs-block">
          <div class="zs-title">2 · Run remediation in the console <span class="badge badge-blue">URL · Manual event action</span></div>
          <div class="zs-desc">Opens SeyalRun pre-targeted to the problem's host + bound playbook. Operator confirms and runs; output posts back to the Problem.</div>
          <div class="zs-code"><code>{{ runUrl }}</code><button class="btn-pill btn-pill-outline" @click="copy(runUrl)">Copy</button></div>
        </div>

        <div class="zs-block">
          <div class="zs-title">3 · One-click remediation <span class="badge badge-green">Webhook · Manual event action</span></div>
          <div class="zs-desc">Runs the pre-bound playbook server-side (HMAC-signed) without leaving Zabbix; the complete output is written onto the Problem. Requires Zabbix 6.4+ (<code>hmac()</code>).</div>
          <div style="font-size:12px;color:var(--text2);margin:4px 0">Parameters:</div>
          <div class="zs-code"><code>{{ webhookParams }}</code><button class="btn-pill btn-pill-outline" @click="copy(webhookParams)">Copy</button></div>
          <div style="font-size:12px;color:var(--text2);margin:8px 0 4px">Script:</div>
          <div class="zs-code"><pre style="margin:0">{{ webhookScript }}</pre><button class="btn-pill btn-pill-outline" @click="copy(webhookScript)">Copy</button></div>
        </div>

        <div class="zs-block" style="border-color:#1f6feb55">
          <div class="zs-title">Let the operator PICK the playbook</div>
          <div class="zs-desc">
            Add one more webhook parameter <code>binding</code>. The chosen playbook name is shown on the Problem
            (<code>playbook: …</code>), so you always see what ran. Two ways:
          </div>
          <div style="font-size:12px;color:var(--text);margin:4px 0"><strong>A · One script per playbook</strong> — set <code>binding</code> to a fixed name below. Name each Zabbix script after the playbook; the operator picks from the menu.</div>
          <div style="font-size:12px;color:var(--text);margin:8px 0 4px"><strong>B · One script, dropdown</strong> — set parameter <code>binding</code> = <code>&#123;MANUALINPUT&#125;</code>, then in the script's <em>Advanced configuration</em> enable <em>User input → Dropdown</em> and paste these options:</div>
          <div class="zs-code"><code>{{ bindingNames || '(create a binding first)' }}</code><button class="btn-pill btn-pill-outline" @click="copy(bindingNames)">Copy</button></div>
          <div class="zs-desc" style="margin-top:8px">Only enabled bindings are runnable — an unknown name is rejected (<code>no_binding</code>).</div>
        </div>

      </div>
    </div>

    <!-- ── Modal ─────────────────────────────────────────────────────────── -->
    <div v-if="modal.open" class="modal-overlay" @click.self="modal.open = false">
      <div class="modal" style="max-width:540px">
        <div class="modal-header">{{ modal.id ? 'Edit' : 'Create' }} Trigger Binding</div>
        <div class="modal-body">
          <label class="form-label">Name</label>
          <input v-model="modal.name" class="input" placeholder="Binding name" />

          <label class="form-label" style="margin-top:12px">Job Template</label>
          <select v-model="modal.job_template_id" class="input">
            <option value="">— select template —</option>
            <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>

          <label class="form-label" style="margin-top:12px">Zabbix Trigger ID (optional, blank = any)</label>
          <input v-model="modal.zabbix_triggerid" class="input" placeholder="e.g. 12345" style="font-family:monospace" />

          <label class="form-label" style="margin-top:12px">Zabbix Host Group filter (optional, blank = any)</label>
          <input v-model="modal.zabbix_host_group" class="input" placeholder="e.g. Linux servers" />

          <label class="form-label" style="margin-top:12px">Minimum Severity</label>
          <select v-model="modal.severity_min" class="input">
            <option :value="0">Not classified (0)</option>
            <option :value="1">Information (1)</option>
            <option :value="2">Warning (2)</option>
            <option :value="3">Average (3)</option>
            <option :value="4">High (4)</option>
            <option :value="5">Disaster (5)</option>
          </select>

          <div style="display:flex;gap:16px;margin-top:16px">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
              <input type="checkbox" v-model="modal.post_result_to_zabbix" />
              <span class="form-label" style="margin:0">Post result back to Zabbix</span>
            </label>
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
              <input type="checkbox" v-model="modal.enabled" />
              <span class="form-label" style="margin:0">Enabled</span>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="modal.open = false">Cancel</button>
          <button class="btn btn-primary" @click="saveBinding" :disabled="!modal.name || !modal.job_template_id">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/client'

const router = useRouter()

const SEVERITY_LABELS: Record<number, string> = {
  0: 'Not classified', 1: 'Information', 2: 'Warning', 3: 'Average', 4: 'High', 5: 'Disaster',
}

const bindings = ref<any[]>([])
const templates = ref<any[]>([])
const loading = ref(false)

// ── Zabbix-side setup snippets (computed from this deployment's origin) ──────
const origin = window.location.origin
const sshUrl = `${origin}/#/terminal?zbx_host={HOST.ID}&autoconnect=1`
const runUrl = `${origin}/#/zbx/run?zbx_host={HOST.ID}&event={EVENT.ID}&trigger={TRIGGER.ID}&severity={EVENT.NSEVERITY}`
const webhookParams = [
  `url         ${origin}/webhook/zabbix/execute`,
  `eventid     {EVENT.ID}`,
  `triggerid   {TRIGGER.ID}`,
  `hostname    {HOST.HOST}`,
  `severity    {EVENT.NSEVERITY}`,
  `hmac_secret {$SEYALRUN_HMAC}`,
].join('\n')
const webhookScript = `var p = JSON.parse(value);
var body = JSON.stringify({
  eventid: p.eventid, triggerid: p.triggerid,
  hostname: p.hostname, severity: parseInt(p.severity || '0'),
  host_groups: [], binding: p.binding || ''
});
var sig = hmac('sha256', p.hmac_secret, body);
var req = new HttpRequest();
req.addHeader('Content-Type: application/json');
req.addHeader('X-SeyalRun-Signature: ' + sig);
var resp = req.post(p.url, body);
if (req.getStatus() >= 400) throw 'SeyalRun ' + req.getStatus() + ': ' + resp;
return resp;`

// Comma-separated binding names for a Zabbix manual-input Dropdown.
const bindingNames = computed(() => bindings.value.map((b: any) => b.name).join(','))

async function copy(text: string) {
  try { await navigator.clipboard.writeText(text) } catch { /* clipboard blocked */ }
}

const modal = reactive({
  open: false, id: '', name: '', job_template_id: '',
  zabbix_triggerid: '', zabbix_host_group: '',
  severity_min: 0, post_result_to_zabbix: true, enabled: true,
})

async function load() {
  loading.value = true
  try {
    const [b, t] = await Promise.all([
      api.get('/trigger-bindings').then(r => r.data),
      api.get('/job-templates').then(r => r.data),
    ])
    bindings.value = b
    templates.value = t
  } finally {
    loading.value = false
  }
}
onMounted(load)

const templateName = (id: string) => templates.value.find(t => t.id === id)?.name || id

function openCreate() {
  Object.assign(modal, {
    open: true, id: '', name: '', job_template_id: '',
    zabbix_triggerid: '', zabbix_host_group: '',
    severity_min: 0, post_result_to_zabbix: true, enabled: true,
  })
}
function openEdit(b: any) {
  Object.assign(modal, {
    open: true, id: b.id, name: b.name, job_template_id: b.job_template_id,
    zabbix_triggerid: b.zabbix_triggerid || '', zabbix_host_group: b.zabbix_host_group || '',
    severity_min: b.severity_min, post_result_to_zabbix: b.post_result_to_zabbix, enabled: b.enabled,
  })
}
async function saveBinding() {
  const body = {
    name: modal.name,
    job_template_id: modal.job_template_id,
    zabbix_triggerid: modal.zabbix_triggerid || null,
    zabbix_host_group: modal.zabbix_host_group || null,
    severity_min: modal.severity_min,
    post_result_to_zabbix: modal.post_result_to_zabbix,
    enabled: modal.enabled,
  }
  if (modal.id) {
    await api.put(`/trigger-bindings/${modal.id}`, body)
  } else {
    await api.post('/trigger-bindings', body)
  }
  modal.open = false
  await load()
}
async function removeBinding(b: any) {
  if (!confirm(`Delete trigger binding "${b.name}"?`)) return
  await api.delete(`/trigger-bindings/${b.id}`)
  await load()
}
async function manualTrigger(b: any) {
  const { data } = await api.post('/triggers/manual', { binding_id: b.id })
  if (data.run_id) {
    router.push(`/jobs/${data.run_id}`)
  }
}
</script>

<style scoped>
.zs-block { border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; }
.zs-title { font-size: 13px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 8px; }
.zs-desc { font-size: 12px; color: var(--text2); margin: 6px 0 10px; }
.zs-code { display: flex; align-items: flex-start; gap: 8px; background: #0d1117; border-radius: 6px; padding: 10px 12px; }
.zs-code code, .zs-code pre { flex: 1; color: #c9d1d9; font-family: monospace; font-size: 12px; white-space: pre-wrap; word-break: break-all; }
.zs-code .btn-pill { flex-shrink: 0; }
</style>
