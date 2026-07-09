<template>
  <div>
    <!-- ── Projects ─────────────────────────────────────────────────────── -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header">
        Projects
        <button class="btn btn-primary btn-sm" @click="openCreateProject">+ Project</button>
      </div>
      <table class="table">
        <thead>
          <tr><th>Name</th><th>Description</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="p in projects" :key="p.id">
            <td style="font-weight:600">{{ p.name }}</td>
            <td style="color:var(--text2)">{{ p.description || '—' }}</td>
            <td>
              <div style="display:flex;gap:8px;justify-content:flex-end">
                <button class="btn-pill btn-pill-outline" @click="openEditProject(p)">✎ Edit</button>
                <button class="btn-pill btn-pill-outline" style="color:var(--danger);border-color:var(--danger)" @click="removeProject(p)">🗑</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!projects.length && !loadingProjects" style="padding:24px;text-align:center;color:var(--text2)">No projects yet.</div>
      <div v-if="loadingProjects" style="padding:24px;text-align:center;color:var(--text2)">Loading…</div>
    </div>

    <!-- ── Job Templates ─────────────────────────────────────────────────── -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header">
        Job Templates
        <button class="btn btn-primary btn-sm" @click="openCreateTemplate">+ Job Template</button>
      </div>
      <table class="table">
        <thead>
          <tr><th>Name</th><th>Action Type</th><th>Project</th><th>Quick Action</th><th>Enabled</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="t in templates" :key="t.id">
            <td style="font-weight:600">{{ t.name }}</td>
            <td><span class="badge badge-blue">{{ t.action_type }}</span></td>
            <td style="color:var(--text2)">{{ projectName(t.project_id) }}</td>
            <td style="text-align:center">{{ t.quick_action ? '✓' : '—' }}</td>
            <td><span :class="t.enabled ? 'badge badge-green' : 'badge badge-gray'">{{ t.enabled ? 'Enabled' : 'Disabled' }}</span></td>
            <td>
              <div style="display:flex;gap:8px;justify-content:flex-end">
                <button class="btn-pill btn-pill-outline" @click="runTemplate(t)">▶ Run</button>
                <button class="btn-pill btn-pill-outline" @click="openEditTemplate(t)">✎ Edit</button>
                <button class="btn-pill btn-pill-outline" style="color:var(--danger);border-color:var(--danger)" @click="removeTemplate(t)">🗑</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!templates.length && !loadingTemplates" style="padding:24px;text-align:center;color:var(--text2)">No job templates yet.</div>
      <div v-if="loadingTemplates" style="padding:24px;text-align:center;color:var(--text2)">Loading…</div>
    </div>

    <!-- ── Schedules ─────────────────────────────────────────────────────── -->
    <div class="card" style="margin-bottom:20px">
      <div class="card-header">
        Schedules
        <button class="btn btn-primary btn-sm" @click="openCreateSchedule">+ Schedule</button>
      </div>
      <table class="table">
        <thead>
          <tr><th>Name</th><th>Job Template</th><th>Cron</th><th>Next Run</th><th>Enabled</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="s in schedules" :key="s.id">
            <td style="font-weight:600">{{ s.name }}</td>
            <td style="color:var(--text2)">{{ templateName(s.job_template_id) }}</td>
            <td><code>{{ s.cron_expression }}</code></td>
            <td style="color:var(--text2)">{{ s.next_run_at ? new Date(s.next_run_at).toLocaleString() : '—' }}</td>
            <td><span :class="s.enabled ? 'badge badge-green' : 'badge badge-gray'">{{ s.enabled ? 'Enabled' : 'Disabled' }}</span></td>
            <td>
              <div style="display:flex;gap:8px;justify-content:flex-end">
                <button class="btn-pill btn-pill-outline" @click="openEditSchedule(s)">✎ Edit</button>
                <button class="btn-pill btn-pill-outline" style="color:var(--danger);border-color:var(--danger)" @click="removeSchedule(s)">🗑</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!schedules.length && !loadingSchedules" style="padding:24px;text-align:center;color:var(--text2)">No schedules yet.</div>
      <div v-if="loadingSchedules" style="padding:24px;text-align:center;color:var(--text2)">Loading…</div>
    </div>

    <!-- ── Project modal ────────────────────────────────────────────────── -->
    <div v-if="projectModal.open" class="modal-overlay" @click.self="projectModal.open = false">
      <div class="modal">
        <div class="modal-header">{{ projectModal.id ? 'Edit' : 'Create' }} Project</div>
        <div class="modal-body">
          <label class="form-label">Name</label>
          <input v-model="projectModal.name" class="input" placeholder="Project name" />
          <label class="form-label" style="margin-top:12px">Description</label>
          <input v-model="projectModal.description" class="input" placeholder="Optional description" />
        </div>
        <div class="modal-footer">
          <button class="btn" @click="projectModal.open = false">Cancel</button>
          <button class="btn btn-primary" @click="saveProject" :disabled="!projectModal.name">Save</button>
        </div>
      </div>
    </div>

    <!-- ── Template modal ───────────────────────────────────────────────── -->
    <div v-if="templateModal.open" class="modal-overlay" @click.self="templateModal.open = false">
      <div class="modal" style="max-width:580px">
        <div class="modal-header">{{ templateModal.id ? 'Edit' : 'Create' }} Job Template</div>
        <div class="modal-body">
          <label class="form-label">Name</label>
          <input v-model="templateModal.name" class="input" placeholder="Template name" />

          <label class="form-label" style="margin-top:12px">Project</label>
          <select v-model="templateModal.project_id" class="input">
            <option value="">— select project —</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>

          <label class="form-label" style="margin-top:12px">Action Type</label>
          <select v-model="templateModal.action_type" class="input">
            <option value="bash_script">Bash Script</option>
            <option value="ansible_playbook">Ansible Playbook</option>
            <option value="account_push">Account Push</option>
            <option value="rotate_secret">Rotate Secret</option>
          </select>

          <template v-if="templateModal.action_type === 'bash_script'">
            <label class="form-label" style="margin-top:12px">Script Content</label>
            <textarea v-model="templateModal.script_content" class="input" rows="6" placeholder="#!/bin/bash&#10;echo hello" style="font-family:monospace;font-size:12px" />
          </template>
          <template v-else-if="templateModal.action_type === 'ansible_playbook'">
            <label class="form-label" style="margin-top:12px">Playbook Path (within project)</label>
            <input v-model="templateModal.playbook_path" class="input" placeholder="site.yml" />
          </template>

          <label class="form-label" style="margin-top:12px">Execution Credential</label>
          <AsyncPicker v-model="templateModal.credential_id" endpoint="/api/v1/credentials" label-key="name" placeholder="Select credential (SSH login)" />

          <template v-if="['account_push','rotate_secret'].includes(templateModal.action_type)">
            <label class="form-label" style="margin-top:12px">Subject Credential (to push/rotate)</label>
            <AsyncPicker v-model="templateModal.subject_credential_id" endpoint="/api/v1/credentials" label-key="name" placeholder="Select credential to manage" />
          </template>

          <div style="display:flex;gap:16px;margin-top:16px">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
              <input type="checkbox" v-model="templateModal.quick_action" />
              <span class="form-label" style="margin:0">Quick Action (shown on host row)</span>
            </label>
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
              <input type="checkbox" v-model="templateModal.enabled" />
              <span class="form-label" style="margin:0">Enabled</span>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="templateModal.open = false">Cancel</button>
          <button class="btn btn-primary" @click="saveTemplate" :disabled="!templateModal.name || !templateModal.project_id">Save</button>
        </div>
      </div>
    </div>

    <!-- ── Schedule modal ───────────────────────────────────────────────── -->
    <div v-if="scheduleModal.open" class="modal-overlay" @click.self="scheduleModal.open = false">
      <div class="modal">
        <div class="modal-header">{{ scheduleModal.id ? 'Edit' : 'Create' }} Schedule</div>
        <div class="modal-body">
          <label class="form-label">Name</label>
          <input v-model="scheduleModal.name" class="input" placeholder="Schedule name" />
          <label class="form-label" style="margin-top:12px">Job Template</label>
          <select v-model="scheduleModal.job_template_id" class="input">
            <option value="">— select template —</option>
            <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
          <label class="form-label" style="margin-top:12px">Cron Expression</label>
          <input v-model="scheduleModal.cron_expression" class="input" placeholder="0 * * * *" style="font-family:monospace" />
          <p v-if="scheduleModal.cron_expression" style="font-size:12px;color:var(--text2);margin-top:4px">{{ cronHint(scheduleModal.cron_expression) }}</p>
          <div style="margin-top:12px">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
              <input type="checkbox" v-model="scheduleModal.enabled" />
              <span class="form-label" style="margin:0">Enabled</span>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="scheduleModal.open = false">Cancel</button>
          <button class="btn btn-primary" @click="saveSchedule" :disabled="!scheduleModal.name || !scheduleModal.job_template_id">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api/client'
import AsyncPicker from '@/components/common/AsyncPicker.vue'

const router = useRouter()

const projects = ref<any[]>([])
const templates = ref<any[]>([])
const schedules = ref<any[]>([])
const loadingProjects = ref(false)
const loadingTemplates = ref(false)
const loadingSchedules = ref(false)

const projectModal = reactive({ open: false, id: '', name: '', description: '' })
const templateModal = reactive({
  open: false, id: '', name: '', project_id: '', action_type: 'bash_script',
  script_content: '', playbook_path: '', credential_id: '', subject_credential_id: '',
  quick_action: false, enabled: true,
})
const scheduleModal = reactive({
  open: false, id: '', name: '', job_template_id: '', cron_expression: '0 * * * *', enabled: true,
})

async function loadAll() {
  loadingProjects.value = true
  loadingTemplates.value = true
  loadingSchedules.value = true
  try {
    const [p, t, s] = await Promise.all([
      api.get('/projects').then(r => r.data),
      api.get('/job-templates').then(r => r.data),
      api.get('/schedules').then(r => r.data),
    ])
    projects.value = p
    templates.value = t
    schedules.value = s
  } finally {
    loadingProjects.value = false
    loadingTemplates.value = false
    loadingSchedules.value = false
  }
}
onMounted(loadAll)

const projectName = (id: string) => projects.value.find(p => p.id === id)?.name || id
const templateName = (id: string) => templates.value.find(t => t.id === id)?.name || id

function openCreateProject() {
  Object.assign(projectModal, { open: true, id: '', name: '', description: '' })
}
function openEditProject(p: any) {
  Object.assign(projectModal, { open: true, id: p.id, name: p.name, description: p.description || '' })
}
async function saveProject() {
  const body = { name: projectModal.name, description: projectModal.description, source_type: 'local' }
  if (projectModal.id) {
    await api.put(`/projects/${projectModal.id}`, body)
  } else {
    await api.post('/projects', body)
  }
  projectModal.open = false
  await loadAll()
}
async function removeProject(p: any) {
  if (!confirm(`Delete project "${p.name}"?`)) return
  await api.delete(`/projects/${p.id}`)
  await loadAll()
}

function openCreateTemplate() {
  Object.assign(templateModal, {
    open: true, id: '', name: '', project_id: projects.value[0]?.id || '',
    action_type: 'bash_script', script_content: '', playbook_path: '',
    credential_id: '', subject_credential_id: '', quick_action: false, enabled: true,
  })
}
function openEditTemplate(t: any) {
  Object.assign(templateModal, {
    open: true, id: t.id, name: t.name, project_id: t.project_id,
    action_type: t.action_type, script_content: t.script_content || '',
    playbook_path: t.playbook_path || '', credential_id: t.credential_id || '',
    subject_credential_id: t.subject_credential_id || '',
    quick_action: t.quick_action, enabled: t.enabled,
  })
}
async function saveTemplate() {
  const body = {
    project_id: templateModal.project_id,
    name: templateModal.name,
    action_type: templateModal.action_type,
    script_content: templateModal.script_content,
    playbook_path: templateModal.playbook_path,
    credential_id: templateModal.credential_id || null,
    subject_credential_id: templateModal.subject_credential_id || null,
    target_scope: 'hosts',
    target_host_ids: [],
    quick_action: templateModal.quick_action,
    enabled: templateModal.enabled,
  }
  if (templateModal.id) {
    await api.put(`/job-templates/${templateModal.id}`, body)
  } else {
    await api.post('/job-templates', body)
  }
  templateModal.open = false
  await loadAll()
}
async function removeTemplate(t: any) {
  if (!confirm(`Delete template "${t.name}"?`)) return
  await api.delete(`/job-templates/${t.id}`)
  await loadAll()
}
async function runTemplate(t: any) {
  const { data } = await api.post(`/job-templates/${t.id}/run`, {})
  if (data.run_id) {
    router.push(`/jobs/${data.run_id}`)
  }
}

function openCreateSchedule() {
  Object.assign(scheduleModal, {
    open: true, id: '', name: '', job_template_id: '', cron_expression: '0 * * * *', enabled: true,
  })
}
function openEditSchedule(s: any) {
  Object.assign(scheduleModal, {
    open: true, id: s.id, name: s.name, job_template_id: s.job_template_id,
    cron_expression: s.cron_expression, enabled: s.enabled,
  })
}
async function saveSchedule() {
  const body = {
    name: scheduleModal.name,
    job_template_id: scheduleModal.job_template_id,
    cron_expression: scheduleModal.cron_expression,
    enabled: scheduleModal.enabled,
  }
  if (scheduleModal.id) {
    await api.put(`/schedules/${scheduleModal.id}`, body)
  } else {
    await api.post('/schedules', body)
  }
  scheduleModal.open = false
  await loadAll()
}
async function removeSchedule(s: any) {
  if (!confirm(`Delete schedule "${s.name}"?`)) return
  await api.delete(`/schedules/${s.id}`)
  await loadAll()
}

function cronHint(expr: string): string {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return 'Invalid cron expression (need 5 fields)'
  const [min, hour, dom, mon, dow] = parts
  if (min === '*' && hour === '*') return 'Every minute'
  if (dom === '*' && mon === '*' && dow === '*') return `At ${hour}:${min.padStart(2,'0')} every day`
  return 'Custom schedule'
}
</script>
