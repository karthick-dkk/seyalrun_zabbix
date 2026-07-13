<template>
  <AppShell>
    <div class="page">
      <div class="page-header">
        <div>
          <div class="page-title">Admin</div>
          <div class="page-subtitle">Users, authorizations, credentials, zones, security policies and audit logs</div>
        </div>
      </div>

      <div class="tab-groups">
        <template v-for="g in GROUPS" :key="g.label">
          <div v-if="g.tabs.some(t => auth.can(t.area))" class="tab-group">
            <span class="tab-group-label">{{ g.label }}</span>
            <div class="tab-group-tabs">
              <router-link v-for="t in g.tabs.filter(t => auth.can(t.area))" :key="t.to" :to="t.to" class="tab" active-class="active">{{ t.label }}</router-link>
            </div>
          </div>
        </template>
      </div>

      <UsersAdmin v-if="section === 'users'" />
      <RolesAdmin v-else-if="section === 'roles'" />
      <AuthorizationsAdmin v-else-if="section === 'authorizations'" />
      <CredentialsAdmin v-else-if="section === 'credentials'" />
      <ZonesAdmin v-else-if="section === 'zones'" />
      <SecurityAdmin v-else-if="section === 'security'" />
      <IntegrationAdmin v-else-if="section === 'integration'" />
      <PlatformSettingsAdmin v-else-if="section === 'platform'" />
      <HealthAdmin v-else-if="section === 'health'" />
      <HousekeepingAdmin v-else-if="section === 'housekeeping'" />
      <LogBackendAdmin v-else-if="section === 'log-backend'" />
      <AuditAdmin v-else-if="section === 'audit'" />
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
import UsersAdmin from './admin/UsersAdmin.vue'
import RolesAdmin from './admin/RolesAdmin.vue'
import AuthorizationsAdmin from './admin/AuthorizationsAdmin.vue'
import CredentialsAdmin from './admin/CredentialsAdmin.vue'
import ZonesAdmin from './admin/ZonesAdmin.vue'
import SecurityAdmin from './admin/SecurityAdmin.vue'
import IntegrationAdmin from './admin/IntegrationAdmin.vue'
import PlatformSettingsAdmin from './admin/PlatformSettingsAdmin.vue'
import HealthAdmin from './admin/HealthAdmin.vue'
import HousekeepingAdmin from './admin/HousekeepingAdmin.vue'
import LogBackendAdmin from './admin/LogBackendAdmin.vue'
import AuditAdmin from './admin/AuditAdmin.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const section = computed(() => route.params.section as string)

// Grouped, ordered admin sections (compact, instead of one long button row).
const GROUPS = [
  { label: 'Access', tabs: [
    { area: 'admin.users', to: '/admin/users', label: 'Users & Groups' },
    { area: 'admin.roles', to: '/admin/roles', label: 'Roles' },
    { area: 'admin.authorizations', to: '/admin/authorizations', label: 'Authorizations' },
  ] },
  { label: 'Inventory', tabs: [
    { area: 'admin.credentials', to: '/admin/credentials', label: 'Credentials' },
    { area: 'admin.zones', to: '/admin/zones', label: 'Zones' },
  ] },
  { label: 'Automation', tabs: [
    { area: 'admin.integration', to: '/admin/integration', label: 'Integration' },
    { area: 'admin.platform', to: '/admin/platform', label: 'SeyalRun Settings' },
  ] },
  { label: 'Platform', tabs: [
    { area: 'admin.health', to: '/admin/health', label: 'Health' },
    { area: 'admin.security', to: '/admin/security', label: 'Security' },
    { area: 'admin.housekeeping', to: '/admin/housekeeping', label: 'Housekeeping' },
    { area: 'admin.log-backend', to: '/admin/log-backend', label: 'Log Backend' },
    { area: 'admin.audit', to: '/admin/audit', label: 'Audit Logs' },
  ] },
]
</script>

<style scoped>
.tab-groups { display: flex; flex-wrap: wrap; gap: 6px 20px; align-items: center; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
.tab-group { display: flex; align-items: center; gap: 8px; }
.tab-group-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text2); font-weight: 700; }
.tab-group-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.tab-group + .tab-group { border-left: 1px solid var(--border); padding-left: 18px; }
</style>
