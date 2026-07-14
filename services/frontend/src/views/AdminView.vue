<template>
  <AppShell>
    <div class="admin-page">
      <nav class="admin-nav" :class="{ collapsed: navCollapsed }">
        <div class="admin-nav-header">
          <div v-if="!navCollapsed" class="admin-nav-heading">
            <div class="admin-nav-title">Admin</div>
            <div class="admin-nav-subtitle">Users, authorizations, credentials, zones, security policies and audit logs</div>
          </div>
          <button class="admin-nav-collapse" @click="navCollapsed = !navCollapsed" :title="navCollapsed ? 'Expand' : 'Collapse'">
            <span v-html="navCollapsed ? ICONS.chevronRight : ICONS.chevronLeft" />
          </button>
        </div>

        <template v-for="g in GROUPS" :key="g.label">
          <div v-if="g.tabs.some(t => auth.can(t.area))" class="admin-nav-group">
            <span v-if="!navCollapsed" class="admin-nav-group-label">{{ g.label }}</span>
            <router-link
              v-for="t in g.tabs.filter(t => auth.can(t.area))"
              :key="t.to"
              :to="t.to"
              class="admin-nav-item"
              active-class="active"
              :title="t.label"
            >
              <span class="admin-nav-item-icon" v-html="t.icon" />
              <span v-if="!navCollapsed" class="label">{{ t.label }}</span>
            </router-link>
          </div>
        </template>
      </nav>

      <div class="admin-content">
        <div v-if="activeLabel" class="content-title">{{ activeLabel }}</div>

        <UsersAdmin v-if="section === 'users'" />
        <RolesAdmin v-else-if="section === 'roles'" />
        <AuthorizationsAdmin v-else-if="section === 'authorizations'" />
        <CredentialsAdmin v-else-if="section === 'credentials'" />
        <ZonesAdmin v-else-if="section === 'zones'" />
        <SecurityAdmin v-else-if="section === 'security'" />
        <IntegrationAdmin v-else-if="section === 'integration'" />
        <TriggerBindingsAdmin v-else-if="section === 'trigger-bindings'" />
        <PlatformSettingsAdmin v-else-if="section === 'platform'" />
        <HealthAdmin v-else-if="section === 'health'" />
        <HousekeepingAdmin v-else-if="section === 'housekeeping'" />
        <LogBackendAdmin v-else-if="section === 'log-backend'" />
        <AuditAdmin v-else-if="section === 'audit'" />
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
import UsersAdmin from './admin/UsersAdmin.vue'
import RolesAdmin from './admin/RolesAdmin.vue'
import AuthorizationsAdmin from './admin/AuthorizationsAdmin.vue'
import CredentialsAdmin from './admin/CredentialsAdmin.vue'
import ZonesAdmin from './admin/ZonesAdmin.vue'
import SecurityAdmin from './admin/SecurityAdmin.vue'
import IntegrationAdmin from './admin/IntegrationAdmin.vue'
import TriggerBindingsAdmin from './admin/TriggerBindingsAdmin.vue'
import PlatformSettingsAdmin from './admin/PlatformSettingsAdmin.vue'
import HealthAdmin from './admin/HealthAdmin.vue'
import HousekeepingAdmin from './admin/HousekeepingAdmin.vue'
import LogBackendAdmin from './admin/LogBackendAdmin.vue'
import AuditAdmin from './admin/AuditAdmin.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const section = computed(() => route.params.section as string)

// Same technique AppShell.vue's own sidebar uses to detect the Zabbix
// iframe — start collapsed there (the iframe is narrower than a full
// browser window), expanded everywhere else. Either way it's just the
// initial state; the toggle below still works in both contexts.
const isEmbedded = window.self !== window.top
const navCollapsed = ref(isEmbedded)

function _svg(body: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`
}
const ICONS = {
  users:       _svg('<path d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>'),
  shield:      _svg('<path d="M12 2.25 4.5 5.063v6.562a8.25 8.25 0 007.5 8.25 8.25 8.25 0 007.5-8.25V5.063L12 2.25z"/>'),
  shieldCheck: _svg('<path d="M12 2.25 4.5 5.063v6.562a8.25 8.25 0 007.5 8.25 8.25 8.25 0 007.5-8.25V5.063L12 2.25z"/><path d="m9 12.75 2.25 2.25 3.75-5.25"/>'),
  lock:        _svg('<path d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>'),
  key:         _svg('<path d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.175.659-1.597l6.41-6.409c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"/>'),
  globe:       _svg('<path d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418"/>'),
  link:        _svg('<path d="M13.5 10.5 21 3m0 0h-5.25M21 3v5.25M10.5 13.5 3 21m0 0h5.25M3 21v-5.25"/>'),
  gear:        _svg('<path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065zM15 12a3 3 0 11-6 0 3 3 0 016 0z"/>'),
  pulse:       _svg('<path d="M2.25 12h3l2.25-7.5 4.5 15L14.25 9l1.5 3h6"/>'),
  trash:       _svg('<path d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>'),
  archive:     _svg('<path d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"/>'),
  list:        _svg('<path d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"/>'),
  bolt:        _svg('<path d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"/>'),
  chevronRight: _svg('<path d="M8.25 4.5l7.5 7.5-7.5 7.5"/>'),
  chevronLeft:  _svg('<path d="M15.75 19.5L8.25 12l7.5-7.5"/>'),
}

// Grouped, ordered admin sections — now rendered as a left-nav sidebar
// (collapsible to an icon-only rail) instead of a horizontal tab bar,
// which was wrapping onto 2-3 lines as sections were added.
const GROUPS = [
  { label: 'Access', tabs: [
    { area: 'admin.users', to: '/admin/users', label: 'Users & Groups', icon: ICONS.users },
    { area: 'admin.roles', to: '/admin/roles', label: 'Roles', icon: ICONS.shield },
    { area: 'admin.authorizations', to: '/admin/authorizations', label: 'Authorizations', icon: ICONS.lock },
  ] },
  { label: 'Inventory', tabs: [
    { area: 'admin.credentials', to: '/admin/credentials', label: 'Credentials', icon: ICONS.key },
    { area: 'admin.zones', to: '/admin/zones', label: 'Zones', icon: ICONS.globe },
  ] },
  { label: 'Automation', tabs: [
    { area: 'admin.integration', to: '/admin/integration', label: 'Integration', icon: ICONS.link },
    { area: 'admin.zabbix-integration', to: '/admin/trigger-bindings', label: 'Trigger Bindings', icon: ICONS.bolt },
    { area: 'admin.platform', to: '/admin/platform', label: 'SeyalRun Settings', icon: ICONS.gear },
  ] },
  { label: 'Platform', tabs: [
    { area: 'admin.health', to: '/admin/health', label: 'Health', icon: ICONS.pulse },
    { area: 'admin.security', to: '/admin/security', label: 'Security', icon: ICONS.shieldCheck },
    { area: 'admin.housekeeping', to: '/admin/housekeeping', label: 'Housekeeping', icon: ICONS.trash },
    { area: 'admin.log-backend', to: '/admin/log-backend', label: 'Log Backend', icon: ICONS.archive },
    { area: 'admin.audit', to: '/admin/audit', label: 'Audit Logs', icon: ICONS.list },
  ] },
]

const activeLabel = computed(() => {
  for (const g of GROUPS) {
    const hit = g.tabs.find(t => t.to === route.path)
    if (hit) return hit.label
  }
  return ''
})
</script>

<style scoped>
/* .page (style.css) is padding: 20px 24px inside a flex:1 column that
   already fills the available height (topbar is flex-shrink:0, .page is
   flex:1) — negative-margin out to its edges so the nav goes flush, then
   min-height:100% to match whatever height .page actually resolves to,
   rather than guessing a pixel value that'd be wrong when the topbar is
   hidden (embedded-in-Zabbix mode). */
.admin-page { display: flex; align-items: flex-start; gap: 0; margin: -20px -24px; min-height: 100%; }

.admin-nav {
  width: 240px; flex-shrink: 0; background: var(--bg2); border-right: 1px solid var(--border);
  padding: 16px 0 20px; align-self: stretch; transition: width 0.16s ease;
}
.admin-nav-header { padding: 0 20px 14px; display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.admin-nav-title { font-size: 18px; font-weight: 700; white-space: nowrap; }
.admin-nav-subtitle { font-size: 11.5px; color: var(--text2); margin-top: 3px; line-height: 1.5; }
.admin-nav-collapse { flex-shrink: 0; background: none; border: none; color: var(--text2); cursor: pointer; padding: 4px; border-radius: 4px; display: flex; margin-top: 2px; }
.admin-nav-collapse:hover { background: var(--bg3); color: var(--text); }
.admin-nav-collapse :deep(svg) { width: 15px; height: 15px; }
.admin-nav-group { margin-bottom: 4px; }
.admin-nav-group-label { display: block; font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text2); font-weight: 700; padding: 14px 20px 6px; white-space: nowrap; }
.admin-nav-item {
  display: flex; align-items: center; gap: 11px; padding: 8px 20px; margin: 0 8px; border-radius: var(--radius);
  font-size: 13.5px; color: var(--text2); text-decoration: none; position: relative; white-space: nowrap;
}
.admin-nav-item-icon :deep(svg) { width: 17px; height: 17px; flex-shrink: 0; display: block; }
.admin-nav-item:hover { background: var(--bg3); color: var(--text); }
.admin-nav-item.active { background: var(--bg3); color: var(--text); font-weight: 600; }
.admin-nav-item.active .admin-nav-item-icon { color: var(--accent2); }
.admin-nav-item.active::before { content: ""; position: absolute; left: -8px; top: 6px; bottom: 6px; width: 3px; border-radius: 2px; background: var(--accent2); }

/* Collapsed: icon-only rail, same technique as AppShell.vue's own
   .sidebar.collapsed — width shrinks, labels disappear, title attribute
   (native browser tooltip) becomes the only affordance for which item is
   which. Auto-starts collapsed inside the Zabbix iframe (see isEmbedded
   above); toggling is manual everywhere. */
.admin-nav.collapsed { width: 64px; }
.admin-nav.collapsed .admin-nav-header { justify-content: center; padding: 0 0 14px; }
.admin-nav.collapsed .admin-nav-item { justify-content: center; padding: 9px 0 9px 6px; margin: 0 10px; gap: 0; }
.admin-nav.collapsed .admin-nav-group { margin-bottom: 8px; padding-top: 8px; border-top: 1px solid var(--border); }
.admin-nav.collapsed .admin-nav-group:first-child { border-top: none; padding-top: 0; }

.admin-content { flex: 1; min-width: 0; padding: 24px 32px; }
.content-title { font-size: 20px; font-weight: 700; margin-bottom: 16px; }
</style>
