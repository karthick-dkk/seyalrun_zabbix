<template>
  <div>
    <div class="card">
      <div class="card-header">
        Zabbix Trigger Bindings
        <div style="display:flex;gap:8px">
          <button class="btn btn-sm" @click="openFromProblem">⚡ From Live Problem</button>
          <button class="btn btn-primary btn-sm" @click="openCreate">+ Trigger Binding</button>
        </div>
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
          <tr><th>Name</th><th>Job Template</th><th>Trigger</th><th>Host Group</th><th>Min Severity</th><th>Post Result</th><th>Enabled</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="b in bindings" :key="b.id">
            <td style="font-weight:600">{{ b.name }}</td>
            <td style="color:var(--text2)">{{ templateName(b.job_template_id) }}</td>
            <td>
              <template v-if="b.zabbix_triggerid">
                <div>{{ b.zabbix_trigger_name || b.zabbix_triggerid }}</div>
                <div style="font-family:monospace;font-size:11px;color:var(--text2)">{{ b.zabbix_triggerid }}</div>
              </template>
              <span v-else style="color:var(--text2)">— any —</span>
            </td>
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
      <div class="modal" style="width:50vw; min-width:480px; max-width:820px">
        <div class="modal-header">{{ modal.id ? 'Edit' : 'Create' }} Trigger Binding</div>
        <div class="modal-body">
          <label class="form-label">Name</label>
          <input v-model="modal.name" class="input" placeholder="Binding name" />

          <label class="form-label" style="margin-top:12px">Job Template</label>
          <select v-model="modal.job_template_id" class="input">
            <option value="">— select template —</option>
            <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>

          <label class="form-label" style="margin-top:12px">Zabbix Trigger (optional, blank = any)</label>
          <AsyncPicker v-model="triggerPick" :search-fn="searchTriggers" :multiple="false"
                       placeholder="Search triggers by name…" />

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

    <!-- ── Create from Live Problem: search, then hand off to the modal above ── -->
    <div v-if="fromProblem.open" class="modal-overlay" @click.self="fromProblem.open = false">
      <div class="modal" style="width:50vw; min-width:420px; max-width:760px">
        <div class="modal-header">Create Binding from Live Problem</div>
        <div class="modal-body" style="min-height:340px">
          <label class="form-label">Live Problem</label>
          <AsyncPicker v-model="problemPick" :search-fn="searchLiveProblems" :multiple="false"
                       placeholder="Search current firing problems…" />
        </div>
        <div class="modal-footer">
          <button class="btn" @click="fromProblem.open = false">Cancel</button>
          <button class="btn btn-primary" :disabled="!problemPick.length" @click="useSelectedProblem">Use this problem →</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/client'
import AsyncPicker, { type PickerItem } from '@/components/common/AsyncPicker.vue'

const router = useRouter()

const SEVERITY_LABELS: Record<number, string> = {
  0: 'Not classified', 1: 'Information', 2: 'Warning', 3: 'Average', 4: 'High', 5: 'Disaster',
}

const bindings = ref<any[]>([])
const templates = ref<any[]>([])
const bindingsLoading = ref(false)

const modal = reactive({
  open: false, id: '', name: '', job_template_id: '',
  zabbix_triggerid: '', zabbix_trigger_name: '', zabbix_host_group: '',
  severity_min: 0, post_result_to_zabbix: true, enabled: true,
})

// Single-select trigger picker for the modal above — kept as its own ref
// (AsyncPicker's v-model is always an array of PickerItem) and synced into
// modal.zabbix_triggerid/zabbix_trigger_name, which stay the source of
// truth saveBinding() actually posts.
const triggerPick = ref<PickerItem[]>([])
watch(triggerPick, (v) => {
  const t = v[0]
  modal.zabbix_triggerid = t?.id || ''
  modal.zabbix_trigger_name = t?.label || ''
})

async function searchTriggers(query: string): Promise<PickerItem[]> {
  return api.get('/triggers/search', { params: { q: query, limit: 20 } }).then(r => r.data)
}

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
    zabbix_triggerid: '', zabbix_trigger_name: '', zabbix_host_group: '',
    severity_min: 0, post_result_to_zabbix: true, enabled: true,
  })
  triggerPick.value = []
}
function openEdit(b: any) {
  Object.assign(modal, {
    open: true, id: b.id, name: b.name, job_template_id: b.job_template_id,
    zabbix_triggerid: b.zabbix_triggerid || '', zabbix_trigger_name: b.zabbix_trigger_name || '',
    zabbix_host_group: b.zabbix_host_group || '',
    severity_min: b.severity_min, post_result_to_zabbix: b.post_result_to_zabbix, enabled: b.enabled,
  })
  // Populated straight from the binding's own stored name — no live
  // /triggers/search call here, so opening Edit never hits Zabbix (and
  // still shows the right label even if that trigger's since been deleted).
  triggerPick.value = b.zabbix_triggerid
    ? [{ id: b.zabbix_triggerid, label: b.zabbix_trigger_name || b.zabbix_triggerid, sublabel: '' }]
    : []
}
async function saveBinding() {
  const body = {
    name: modal.name,
    job_template_id: modal.job_template_id,
    zabbix_triggerid: modal.zabbix_triggerid || null,
    zabbix_trigger_name: modal.zabbix_trigger_name || null,
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

// ── Create from Live Problem ────────────────────────────────────────────
const fromProblem = reactive({ open: false })
const problemPick = ref<PickerItem[]>([])

async function searchLiveProblems(query: string): Promise<PickerItem[]> {
  return api.get('/triggers/live-problems', { params: { q: query, limit: 20 } }).then(r => r.data)
}

function openFromProblem() {
  problemPick.value = []
  fromProblem.open = true
}

function useSelectedProblem() {
  const p: any = problemPick.value[0]
  if (!p) return
  fromProblem.open = false
  Object.assign(modal, {
    open: true, id: '', name: `Auto: ${p.label}`, job_template_id: '',
    zabbix_triggerid: p.triggerid || '', zabbix_trigger_name: p.label || '',
    zabbix_host_group: '',
    severity_min: p.severity || 0, post_result_to_zabbix: true, enabled: true,
  })
  triggerPick.value = p.triggerid
    ? [{ id: p.triggerid, label: p.label, sublabel: p.host_name || '' }]
    : []
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
