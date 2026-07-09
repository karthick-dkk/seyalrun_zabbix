<template>
  <div class="app-shell">
    <!-- Sidebar — hidden when embedded inside Zabbix (its native menu provides navigation) -->
    <nav v-if="!isEmbedded" class="sidebar" :class="{ collapsed }">
      <div class="sidebar-logo">
        <span class="logo-icon" v-html="ICONS.logo" />
        <span class="logo-text">SeyalRun</span>
        <button class="sidebar-collapse-btn" @click="collapsed = !collapsed" :title="collapsed ? 'Expand' : 'Collapse'">
          <span v-html="collapsed ? ICONS.chevronRight : ICONS.chevronLeft" />
        </button>
      </div>
      <div class="sidebar-nav">
        <router-link v-if="auth.can('dashboard')" to="/"         class="nav-item" active-class="active"><span class="nav-icon" v-html="ICONS.dashboard" /><span class="nav-label">Dashboard</span></router-link>
        <router-link v-if="auth.can('hosts')"     to="/hosts"    class="nav-item" active-class="active"><span class="nav-icon" v-html="ICONS.hosts" /><span class="nav-label">Hosts</span></router-link>
        <router-link v-if="auth.can('assets')"    to="/assets"   class="nav-item" active-class="active"><span class="nav-icon" v-html="ICONS.assets" /><span class="nav-label">Assets</span></router-link>
        <router-link v-if="auth.can('sessions')"  to="/sessions" class="nav-item" active-class="active"><span class="nav-icon" v-html="ICONS.sessions" /><span class="nav-label">Sessions</span></router-link>
        <router-link v-if="auth.can('jobs')" to="/jobs"       class="nav-item" active-class="active"><span class="nav-icon" v-html="ICONS.jobRuns" /><span class="nav-label">Job Runs</span></router-link>
        <router-link v-if="auth.can('automation')" to="/automation" class="nav-item" active-class="active"><span class="nav-icon" v-html="ICONS.automation" /><span class="nav-label">Automation</span></router-link>
        <template v-if="auth.canAnyAdmin()">
          <div class="nav-section-header"><span class="nav-label">Admin</span></div>
          <router-link v-if="auth.can('admin.users')"              to="/admin/users"              class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.users" /><span class="nav-label">Users &amp; Groups</span></router-link>
          <router-link v-if="auth.can('admin.roles')"              to="/admin/roles"              class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.shield" /><span class="nav-label">Roles</span></router-link>
          <router-link v-if="auth.can('admin.authorizations')"     to="/admin/authorizations"     class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.lock" /><span class="nav-label">Authorizations</span></router-link>
          <router-link v-if="auth.can('admin.credentials')"        to="/admin/credentials"        class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.key" /><span class="nav-label">Credentials</span></router-link>
          <router-link v-if="auth.can('admin.zones')"              to="/admin/zones"              class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.globe" /><span class="nav-label">Zones</span></router-link>
          <router-link v-if="auth.can('admin.security')"           to="/admin/security"           class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.shield" /><span class="nav-label">Security</span></router-link>
          <router-link v-if="auth.can('admin.automation')"         to="/admin/automation"         class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.gear" /><span class="nav-label">Automation</span></router-link>
          <router-link v-if="auth.can('admin.zabbix-integration')" to="/admin/zabbix-integration" class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.bell" /><span class="nav-label">Zabbix Integration</span></router-link>
          <router-link v-if="auth.can('admin.integration')"        to="/admin/integration"        class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.globe" /><span class="nav-label">Integration</span></router-link>
          <router-link v-if="auth.can('admin.health')"             to="/admin/health"             class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.clipboard" /><span class="nav-label">Health</span></router-link>
          <router-link v-if="auth.can('admin.housekeeping')"       to="/admin/housekeeping"       class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.gear" /><span class="nav-label">Housekeeping</span></router-link>
          <router-link v-if="auth.can('admin.log-backend')"        to="/admin/log-backend"        class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.clipboard" /><span class="nav-label">Log Backend</span></router-link>
          <router-link v-if="auth.can('admin.audit')"              to="/admin/audit"              class="nav-item nav-sub" active-class="active"><span class="nav-icon" v-html="ICONS.clipboard" /><span class="nav-label">Audit Logs</span></router-link>
        </template>
      </div>
      <div class="sidebar-user">
        <div class="avatar">{{ (auth.user?.username || '?').charAt(0).toUpperCase() }}</div>
        <div class="user-meta">
          <div class="user-name">{{ auth.user?.username }}</div>
          <div class="user-role">{{ auth.roles.join(', ') || auth.user?.role_name }}</div>
        </div>
      </div>
      <div class="sidebar-logout">
        <button class="btn btn-sm" @click="doLogout">
          <span class="nav-label">Logout</span>
        </button>
      </div>
    </nav>

    <!-- Main -->
    <div class="main-content">
      <div v-if="!isEmbedded" class="topbar">
        <span class="topbar-title">{{ $route.meta.title || 'SeyalRun' }}</span>
        <button class="topbar-btn" @click="openTerminal" title="SSH Terminal">
          <span v-html="ICONS.terminal" style="display:flex;align-items:center;" />
          SSH Terminal
        </button>
        <a class="topbar-link" :href="zabbixUrl" target="_blank" title="Back to Zabbix">
          <span v-html="ICONS.arrowUpRight" style="display:flex;align-items:center;" />
          Zabbix
        </a>
      </div>
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api, { terminalUrl } from '@/api/client'

const auth = useAuthStore()
const router = useRouter()

// ── SF Symbol-style SVG icon set (24×24, stroke-based, Apple thin-line aesthetic) ──
function _svg(body: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`
}
const ICONS = {
  logo:        _svg('<path d="M12 2.25 4.5 5.063v6.562a8.25 8.25 0 007.5 8.25 8.25 8.25 0 007.5-8.25V5.063L12 2.25z"/><path d="m9 12.75 2.25 2.25 3.75-5.25"/>'),
  dashboard:   _svg('<path d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"/>'),
  hosts:       _svg('<path d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25"/>'),
  assets:      _svg('<path d="M21 7.5l-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9"/>'),
  sessions:    _svg('<path d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z"/>'),
  jobRuns:     _svg('<path d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z"/>'),
  automation:  _svg('<path d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"/>'),
  users:       _svg('<path d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>'),
  lock:        _svg('<path d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>'),
  key:         _svg('<path d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.175.659-1.597l6.41-6.409c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"/>'),
  globe:       _svg('<path d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418"/>'),
  shield:      _svg('<path d="M12 2.25 4.5 5.063v6.562a8.25 8.25 0 007.5 8.25 8.25 8.25 0 007.5-8.25V5.063L12 2.25z"/><path d="m9 12.75 2.25 2.25 3.75-5.25"/>'),
  gear:        _svg('<path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065zM15 12a3 3 0 11-6 0 3 3 0 016 0z"/>'),
  bell:        _svg('<path d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"/>'),
  clipboard:   _svg('<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>'),
  terminal:    _svg('<path d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z"/>'),
  arrowUpRight: _svg('<path d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/>'),
  chevronRight: _svg('<path d="M8.25 4.5l7.5 7.5-7.5 7.5"/>'),
  chevronLeft:  _svg('<path d="M15.75 19.5L8.25 12l7.5-7.5"/>'),
}

// When loaded inside the Zabbix "Manage SeyalRun" iframe, Zabbix's own
// sidebar already provides navigation — rendering ours on top causes
// the two menus to visually overlap. Detect the iframe and hide ours.
const isEmbedded = window.self !== window.top
const collapsed = ref(false)

// Zabbix link: prefer the URL configured in .env (Admin → Integration); fall back to the
// same-host /zabbix path. Fetched once so the header button matches the Integration page.
const zabbixUrl = ref(`${location.protocol}//${location.host}/zabbix/`)
onMounted(async () => {
  try {
    const { data } = await api.get('/integration/info')
    if (data?.zabbix_url) zabbixUrl.value = data.zabbix_url
  } catch { /* keep fallback */ }
})

async function doLogout() {
  await auth.logout()
  router.push('/login')
}

function openTerminal() {
  window.open(terminalUrl(), '_blank')
}
</script>

<style scoped>
/* ── SVG icon sizing ────────────────────────────────────────────────────────── */
.nav-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.nav-icon :deep(svg) {
  width: 18px;
  height: 18px;
  display: block;
}

.logo-icon {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent2);
}
.logo-icon :deep(svg) { width: 22px; height: 22px; }

.sidebar-collapse-btn :deep(svg) { width: 14px; height: 14px; }

/* ── Topbar buttons ─────────────────────────────────────────────────────────── */
.topbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.topbar-btn:hover {
  background: var(--bg2);
  border-color: var(--accent2);
  color: var(--accent2);
}
.topbar-btn :deep(svg) { width: 15px; height: 15px; }
</style>
