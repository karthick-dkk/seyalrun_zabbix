<template>
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg)">
    <!-- Zabbix SSO exchange is a single fast round trip (~100ms) — the ENTIRE
         branding block + card is gated off during it, not just the card body,
         so nothing (not even the logo) flashes on a normal embedded page
         transition. Only the plain background shows for that brief window. -->
    <div v-if="!ssoLoading" style="width:360px">
      <div style="text-align:center;margin-bottom:32px">
        <div style="font-size:48px;margin-bottom:8px">⚡</div>
        <h1 style="font-size:24px;font-weight:700;color:var(--text)">SeyalRun</h1>
        <div style="color:var(--text2);font-size:13px;margin-top:4px">DevOps Console</div>
      </div>
      <div class="card">
        <div class="card-body">
          <template v-if="mfaPending">
            <div style="font-weight:600;color:var(--text);margin-bottom:4px">Verify your identity</div>
            <div style="color:var(--text2);font-size:12px;margin-bottom:16px">
              <template v-if="mfaMethod === 'email'">Enter the 6-digit code we emailed you.</template>
              <template v-else>Enter the 6-digit code from your authenticator app.</template>
            </div>
            <div class="form-group">
              <label class="form-label">Code</label>
              <input v-model="mfaCode" class="input" placeholder="123456" inputmode="numeric" maxlength="6" @keydown.enter="doVerifyMfa" autofocus />
            </div>
            <div v-if="error" style="color:var(--danger);font-size:12px;margin-bottom:12px">{{ error }}</div>
            <button class="btn btn-primary" style="width:100%;justify-content:center" @click="doVerifyMfa" :disabled="loading">
              {{ loading ? 'Verifying…' : 'Verify' }}
            </button>
            <button v-if="mfaMethod === 'email'" class="btn" style="width:100%;justify-content:center;margin-top:8px" @click="doResend" :disabled="resending">
              {{ resending ? 'Sending…' : 'Resend code' }}
            </button>
          </template>
          <template v-else-if="mustChange">
            <div style="font-weight:600;color:var(--text);margin-bottom:4px">Set a new password</div>
            <div style="color:var(--text2);font-size:12px;margin-bottom:16px">
              You signed in with the default password. Choose a new one (min 8
              characters) before continuing — nothing else works until you do.
            </div>
            <div class="form-group">
              <label class="form-label">New password</label>
              <input v-model="newPassword" type="password" class="input" placeholder="New password" @keydown.enter="doChangePassword" autofocus />
            </div>
            <div class="form-group">
              <label class="form-label">Confirm new password</label>
              <input v-model="confirmPassword" type="password" class="input" placeholder="Confirm new password" @keydown.enter="doChangePassword" />
            </div>
            <div v-if="error" style="color:var(--danger);font-size:12px;margin-bottom:12px">{{ error }}</div>
            <button class="btn btn-primary" style="width:100%;justify-content:center" @click="doChangePassword" :disabled="loading">
              {{ loading ? 'Saving…' : 'Change Password & Continue' }}
            </button>
          </template>
          <template v-else>
            <div class="form-group">
              <label class="form-label">Username</label>
              <input v-model="username" class="input" placeholder="Username" @keydown.enter="doLogin" autofocus />
            </div>
            <div class="form-group">
              <label class="form-label">Password</label>
              <input v-model="password" type="password" class="input" placeholder="Password" @keydown.enter="doLogin" />
            </div>
            <div v-if="error" style="color:var(--danger);font-size:12px;margin-bottom:12px">{{ error }}</div>
            <button class="btn btn-primary" style="width:100%;justify-content:center" @click="doLogin" :disabled="loading">
              {{ loading ? 'Signing in…' : 'Sign In' }}
            </button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const ssoLoading = ref(false)
const mustChange = ref(false)
const newPassword = ref('')
const confirmPassword = ref('')
const mfaPending = ref(false)
const mfaMethod = ref('')
const mfaCode = ref('')
const resending = ref(false)

onMounted(async () => {
  const params = new URLSearchParams(window.location.search)
  const code = params.get('sso_code')
  if (!code) return
  // The code is single-use and dead the moment we attempt it either way — strip it
  // from the address bar now so a later refresh of this tab doesn't resend it (the
  // router guard treats an unconsumed sso_code as always requiring a fresh exchange).
  const url = new URL(window.location.href)
  url.searchParams.delete('sso_code')
  window.history.replaceState(null, '', url.toString())
  ssoLoading.value = true
  try {
    await auth.exchangeSSO(code)
    // goIn() honors route.query.redirect — the intended page the guard bounced
    // here from (e.g. #/assets from the Zabbix module). Landing everyone on '/'
    // regardless of which SeyalRun page they clicked was the bug: every page
    // inside Zabbix rendered Dashboard.
    goIn()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'SSO sign-in failed'
    ssoLoading.value = false
  }
})

// Hash-based routing means the router's `redirect` query lives in
// window.location.hash, never window.location.search — read it via the
// router's own resolved query instead.
function goIn() {
  const redirect = (route.query.redirect as string) || '/'
  router.push(redirect)
}

// A visitor forced here by the router guard specifically to reach a Zabbix
// terminal deep-link (?zbx_host=.. or ?host_id=.., with autoconnect=1) is
// logging in for that one purpose. Extract the raw target so login can bind
// a kiosk claim to it — server-resolved and server-enforced, this is only a
// hint for the backend to attempt resolution, never trusted on its own.
function kioskTargetFromRedirect(): string | undefined {
  const redirect = route.query.redirect as string | undefined
  if (!redirect) return undefined
  const qs = redirect.split('?')[1]
  if (!qs) return undefined
  const params = new URLSearchParams(qs)
  if (params.get('autoconnect') !== '1' && params.get('autoconnect') !== 'true') return undefined
  return params.get('zbx_host') || params.get('host_id') || undefined
}

async function doLogin() {
  if (!username.value || !password.value) return
  loading.value = true
  error.value = ''
  try {
    const result = await auth.login(username.value, password.value, kioskTargetFromRedirect())
    if (result.mfaRequired) {
      mfaPending.value = true
      mfaMethod.value = result.mfaMethod || 'totp'
      return
    }
    if (auth.user?.must_change_password) {
      mustChange.value = true   // keep password.value in memory as the current password
      return
    }
    goIn()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Invalid credentials'
  } finally {
    loading.value = false
  }
}

async function doChangePassword() {
  if (!newPassword.value) return
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const result = await auth.changePassword(password.value, newPassword.value, kioskTargetFromRedirect())
    if (result.mfaRequired) {
      mustChange.value = false
      mfaPending.value = true
      mfaMethod.value = result.mfaMethod || 'totp'
      return
    }
    goIn()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Password change failed'
  } finally {
    loading.value = false
  }
}

async function doVerifyMfa() {
  if (!mfaCode.value) return
  loading.value = true
  error.value = ''
  try {
    await auth.verifyMfaLogin(mfaCode.value)
    goIn()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Invalid code'
  } finally {
    loading.value = false
  }
}

async function doResend() {
  resending.value = true
  error.value = ''
  try {
    await auth.resendMfaCode()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Failed to resend code'
  } finally {
    resending.value = false
  }
}
</script>
