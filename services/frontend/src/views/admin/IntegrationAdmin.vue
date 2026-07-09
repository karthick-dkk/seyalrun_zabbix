<template>
  <div>
    <div class="card">
      <div class="card-header">
        Integration
        <button class="btn btn-sm" @click="load">Refresh</button>
      </div>
      <div style="padding:18px">
        <div v-if="loading" style="color:var(--text2)">Loading…</div>
        <template v-else>
          <div class="int-grid">
            <div class="int-row">
              <span class="int-k">Zabbix URL</span>
              <a v-if="info.zabbix_url" :href="info.zabbix_url" target="_blank" class="int-link">{{ info.zabbix_url }}</a>
              <span v-else style="color:var(--text2)">— not set</span>
            </div>
            <div class="int-row">
              <span class="int-k">API endpoint</span>
              <span class="ip-mono">{{ info.api_url || '—' }}</span>
            </div>
            <div class="int-row">
              <span class="int-k">Status</span>
              <span class="badge" :class="info.reachable ? 'badge-green' : (info.configured ? 'badge-red' : 'badge-gray')">
                {{ info.reachable ? 'Connected' : (info.configured ? 'Unreachable' : 'Not configured') }}
              </span>
              <span v-if="info.version" style="color:var(--text2);font-size:12px;margin-left:8px">Zabbix {{ info.version }}</span>
            </div>
          </div>

          <div style="display:flex;gap:10px;margin-top:18px">
            <a v-if="info.zabbix_url" class="btn btn-primary" :href="info.zabbix_url" target="_blank">↗ Open Zabbix</a>
            <router-link class="btn" to="/admin/zabbix-integration">Trigger Bindings →</router-link>
          </div>

          <p style="margin-top:18px;color:var(--text2);font-size:12px;line-height:1.6">
            The Zabbix URL is stored in the database (superadmin-editable below) and falls back to
            <code>.env</code> (<code>ZABBIX_CONSOLE_URL</code> / <code>ZABBIX_API_URL</code>). The API token is
            kept server-side and never shown here. (The webhook post-back still uses the service's own
            <code>.env</code> token.)
          </p>
        </template>
      </div>
    </div>

    <!-- Superadmin-only: edit the Zabbix integration settings -->
    <div v-if="auth.isSuperAdmin" class="card" style="margin-top:16px">
      <div class="card-header">Zabbix Settings <span class="badge badge-blue">superadmin</span></div>
      <div style="padding:18px">
        <div class="fp-field">
          <label class="fp-label">Zabbix Console URL <span class="hint">(the "Open Zabbix" link / header button)</span></label>
          <input v-model="form.zabbix_console_url" class="fp-input" placeholder="https://zabbix.example.com" />
        </div>
        <div class="fp-field">
          <label class="fp-label">Zabbix API URL <span class="hint">(used for reachability + host sync)</span></label>
          <input v-model="form.zabbix_api_url" class="fp-input" placeholder="https://zabbix.example.com" />
        </div>
        <div class="fp-field">
          <label class="fp-label">
            Zabbix API Token
            <span class="hint">{{ settings.zabbix_api_token_configured ? '· currently configured — leave blank to keep' : '· not set' }}</span>
          </label>
          <input v-model="form.zabbix_api_token" type="password" autocomplete="new-password" class="fp-input" placeholder="leave blank to keep existing" />
        </div>
        <div v-if="saveMsg" class="save-msg" :class="saveErr ? 'err' : 'ok'">{{ saveMsg }}</div>
        <div style="margin-top:12px">
          <button class="btn btn-primary" :disabled="saving" @click="save">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const info = ref<any>({})
const settings = ref<any>({})
const loading = ref(false)
const saving = ref(false)
const saveMsg = ref('')
const saveErr = ref(false)
const form = reactive({ zabbix_console_url: '', zabbix_api_url: '', zabbix_api_token: '' })

async function load() {
  loading.value = true
  try { info.value = (await api.get('/integration/info')).data }
  catch { info.value = {} }
  finally { loading.value = false }
  if (auth.isSuperAdmin) {
    try {
      settings.value = (await api.get('/settings/integration')).data
      form.zabbix_console_url = settings.value.zabbix_console_url || ''
      form.zabbix_api_url = settings.value.zabbix_api_url || ''
      form.zabbix_api_token = ''
    } catch { settings.value = {} }
  }
}

async function save() {
  saving.value = true; saveMsg.value = ''; saveErr.value = false
  try {
    await api.put('/settings/integration', { ...form })
    form.zabbix_api_token = ''
    saveMsg.value = 'Saved.'
    await load()
  } catch (e: any) {
    saveErr.value = true
    saveMsg.value = e?.response?.data?.detail || 'Failed to save settings'
  } finally { saving.value = false }
}

onMounted(load)
</script>

<style scoped>
.int-grid { display: flex; flex-direction: column; gap: 12px; }
.int-row { display: flex; align-items: center; gap: 12px; font-size: 14px; }
.int-k { flex: 0 0 130px; color: var(--text2); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
.int-link { color: #58a6ff; }
code { background: var(--surface2); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.fp-field { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; }
.fp-label { font-size: 12px; color: #8b949e; font-weight: 500; }
.hint { color: #6e7681; font-weight: 400; }
.fp-input { padding: 7px 10px; background: #0d1117; border: 1px solid #30363d; border-radius: 5px; color: #e6edf3; font-size: 13px; outline: none; }
.save-msg { font-size: 12px; margin-top: 10px; }
.save-msg.ok { color: #3fb950; }
.save-msg.err { color: #f85149; }
</style>
