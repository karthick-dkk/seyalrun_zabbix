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
        <strong>Manual Trigger</strong> button to also run it on-demand. Global-script wiring
        snippets (SSH link, webhook, dropdown picker) are on the
        <router-link to="/admin/integration" style="color:var(--accent2)">Integration</router-link> page.
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
      <div v-if="!bindings.length && !bindingsLoading" style="padding:24px;text-align:center;color:var(--text2)">No trigger bindings yet.</div>
      <div v-if="bindingsLoading" style="padding:24px;text-align:center;color:var(--text2)">Loading…</div>
    </div>

    <!-- ── Trigger Binding modal ─────────────────────────────────────────── -->
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
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/client'

const router = useRouter()

const SEVERITY_LABELS: Record<number, string> = {
  0: 'Not classified', 1: 'Information', 2: 'Warning', 3: 'Average', 4: 'High', 5: 'Disaster',
}

const bindings = ref<any[]>([])
const templates = ref<any[]>([])
const bindingsLoading = ref(false)

const modal = reactive({
  open: false, id: '', name: '', job_template_id: '',
  zabbix_triggerid: '', zabbix_host_group: '',
  severity_min: 0, post_result_to_zabbix: true, enabled: true,
})

async function loadBindings() {
  bindingsLoading.value = true
  try {
    const [b, t] = await Promise.all([
      api.get('/trigger-bindings').then(r => r.data),
      api.get('/job-templates').then(r => r.data),
    ])
    bindings.value = b
    templates.value = t
  } finally {
    bindingsLoading.value = false
  }
}

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
  await loadBindings()
}
async function removeBinding(b: any) {
  if (!confirm(`Delete trigger binding "${b.name}"?`)) return
  await api.delete(`/trigger-bindings/${b.id}`)
  await loadBindings()
}
async function manualTrigger(b: any) {
  const { data } = await api.post('/triggers/manual', { binding_id: b.id })
  if (data.run_id) {
    router.push(`/jobs/${data.run_id}`)
  }
}

onMounted(loadBindings)
</script>
