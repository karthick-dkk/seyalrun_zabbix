import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { setToken } from '@/api/client'

export const VALID_ADMIN_SECTIONS = ['users', 'roles', 'authorizations', 'credentials', 'zones', 'security', 'audit', 'integration', 'platform', 'health', 'housekeeping', 'log-backend']

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
    },
    {
      path: '/assets',
      name: 'assets',
      component: () => import('@/views/AssetsView.vue'),
    },
    {
      path: '/admin/:section',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { requiresAdmin: true },
      beforeEnter: (to) => {
        const section = to.params.section as string
        if (!VALID_ADMIN_SECTIONS.includes(section)) {
          return { path: '/admin/users' }
        }
        return true
      },
    },
    {
      path: '/admin',
      redirect: '/admin/users',
    },
    {
      path: '/hosts',
      name: 'hosts',
      component: () => import('@/views/HostsView.vue'),
    },
    {
      path: '/terminal',
      name: 'terminal',
      component: () => import('@/views/TerminalView.vue'),
    },
    {
      path: '/sessions',
      name: 'sessions',
      component: () => import('@/views/SessionsView.vue'),
    },
    {
      path: '/sessions/:id',
      name: 'session-playback',
      component: () => import('@/views/SessionPlaybackView.vue'),
    },
    {
      path: '/dashboard',
      redirect: '/',
    },
    {
      path: '/recordings',
      redirect: '/sessions',
    },
    {
      path: '/recordings/:id',
      redirect: to => ({ path: `/sessions/${to.params.id}` }),
    },
    {
      // The standalone Jobs list moved into Automation's "Recent Runs" tab — this
      // redirect just keeps old bookmarks/links working, same pattern as /recordings.
      path: '/jobs',
      redirect: '/automation?tab=runs',
    },
    {
      path: '/jobs/:id',
      name: 'job-run',
      component: () => import('@/views/JobRunView.vue'),
    },
    {
      path: '/automation',
      name: 'automation',
      component: () => import('@/views/AutomationView.vue'),
    },
    {
      path: '/zbx/run',
      name: 'zbx-run',
      component: () => import('@/views/ZbxRunView.vue'),
    },
  ],
})

// Map a target route to its RBAC nav area (matches the gateway's nav_permissions keys).
function areaFor(to: any): string | null {
  const p = to.path as string
  if (p === '/') return 'dashboard'
  if (p.startsWith('/hosts')) return 'hosts'
  if (p.startsWith('/assets')) return 'assets'
  if (p.startsWith('/sessions')) return 'sessions'
  if (p.startsWith('/terminal')) return 'terminal'
  if (p.startsWith('/recordings')) return 'recordings'
  if (p.startsWith('/jobs')) return 'jobs'
  if (p.startsWith('/automation')) return 'automation'
  if (p.startsWith('/zbx')) return 'jobs'   // 'Run from Zabbix' console page is gated with jobs
  if (p.startsWith('/admin/')) {
    const section = (to.params?.section as string) || p.split('/')[2] || ''
    return section ? `admin.${section}` : null
  }
  return null
}

// First top-level page the caller is allowed to open (used to redirect away from forbidden ones).
function firstAllowedPath(auth: ReturnType<typeof useAuthStore>): string | null {
  const order: [string, string][] = [
    ['dashboard', '/'], ['hosts', '/hosts'], ['assets', '/assets'],
    ['sessions', '/sessions'], ['recordings', '/recordings'], ['jobs', '/jobs'],
    ['terminal', '/terminal'], ['automation', '/automation'],
  ]
  for (const [area, path] of order) if (auth.can(area)) return path
  return null
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // Session handoff: a terminal tab opened from the app (or the Zabbix iframe) carries the
  // session token in the URL fragment so it works despite browser storage partitioning.
  // Adopt it, then redirect to the same route without the token so it doesn't linger.
  const handoff = to.query._session as string | undefined
  if (handoff) {
    setToken(handoff)
    auth.ready = false
    await auth.init()
    const q = { ...to.query }
    delete q._session
    return { path: to.path, query: q, hash: to.hash }
  }

  if (!auth.ready) {
    await auth.init()
  }

  // An unconsumed sso_code in the URL is a fresh, explicit identity assertion from
  // Zabbix (e.g. a "Terminal" link opened as a new top-level tab) and must always get
  // a chance to be exchanged — even if auth.init() just authenticated this browser via
  // an unrelated sr_session cookie left over from an earlier standalone login. Without
  // this, a tab that inherits that ambient cookie session never even mounts LoginView
  // (the only place sso_code is read), so it silently proceeds as the cookie's identity
  // instead of the one Zabbix actually asserted for this click.
  const hasUnconsumedSsoCode = !!new URLSearchParams(window.location.search).get('sso_code')
  if (hasUnconsumedSsoCode) {
    return to.path === '/login' ? true : { path: '/login', query: { redirect: to.fullPath } }
  }

  if (!to.meta.public && !auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.meta.public && auth.isAuthenticated) {
    return { path: firstAllowedPath(auth) || '/' }
  }

  // Per-area RBAC: never render a page the caller's role can't open — redirect to the
  // first page they can (the gateway is still the authoritative enforcer).
  if (!to.meta.public && auth.isAuthenticated) {
    const area = areaFor(to)
    if (area && !auth.can(area)) {
      const dest = firstAllowedPath(auth)
      return dest && dest !== to.path ? { path: dest } : true
    }
  }

  return true
})

export default router
