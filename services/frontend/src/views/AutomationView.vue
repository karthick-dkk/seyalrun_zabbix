<template>
  <AppShell>
    <div class="page">

      <!-- ── Page header ──────────────────────────────────────────────────── -->
      <div class="page-header">
        <div>
          <div class="page-title">Automation</div>
          <div class="page-subtitle">Run Ansible playbooks and scripts against your hosts</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <button v-if="auth.isAdminOrSupport && autoTab === 'playbooks'" class="btn btn-primary" @click="openCreate">+ New Playbook</button>
          <button v-if="auth.isAdminOrSupport && autoTab === 'templates'" class="btn btn-primary" @click="openCreateTemplate">+ New Template</button>
          <button v-if="auth.isAdminOrSupport && autoTab === 'schedules'" class="btn btn-primary" @click="openCreateSchedule">+ New Schedule</button>
          <button class="btn btn-icon" @click="loadAll" title="Refresh">↺</button>
        </div>
      </div>

      <!-- ── Service unavailable banner ───────────────────────────────────── -->
      <div v-if="!serviceAvailable && !serviceLoading" class="svc-unavailable">
        <div class="svc-icon">⚙</div>
        <div>
          <div class="svc-title">Automation Service Not Available</div>
          <div class="svc-desc">The automation service is not running or not yet deployed. Start the <code>automation-service</code> container to enable this feature.</div>
        </div>
        <button class="btn" @click="loadAll" style="margin-left:auto;flex-shrink:0">Retry</button>
      </div>

      <!-- ── Tabs ──────────────────────────────────────────────────────────── -->
      <div v-if="serviceAvailable" class="auto-tabs">
        <button :class="['auto-tab', { active: autoTab === 'playbooks' }]" @click="autoTab = 'playbooks'">
          <span>📜</span> Playbooks &amp; Scripts
          <span v-if="playbookTemplates.length" class="tab-badge">{{ playbookTemplates.length }}</span>
        </button>
        <button v-if="auth.isAdminOrSupport" :class="['auto-tab', { active: autoTab === 'templates' }]" @click="autoTab = 'templates'">
          <span>⚙</span> All Templates
          <span v-if="allTemplates.length" class="tab-badge">{{ allTemplates.length }}</span>
        </button>
        <button v-if="auth.isAdminOrSupport" :class="['auto-tab', { active: autoTab === 'schedules' }]" @click="autoTab = 'schedules'">
          <span>📅</span> Schedules
          <span v-if="schedules.length" class="tab-badge">{{ schedules.length }}</span>
        </button>
        <button :class="['auto-tab', { active: autoTab === 'runs' }]" @click="autoTab = 'runs'; loadRuns()">
          <span>▦</span> Recent Runs
        </button>
      </div>

      <!-- ── Loading state ─────────────────────────────────────────────────── -->
      <div v-if="serviceLoading" class="cards-empty">Loading automation service…</div>

      <!-- ══════════════════════════════════════════════════════════════════ -->
      <!-- ANSIBLE PLAYBOOKS tab                                              -->
      <!-- ══════════════════════════════════════════════════════════════════ -->
      <div v-if="serviceAvailable && autoTab === 'playbooks'">
        <div class="pb-toolbar">
          <input v-model="templateSearch" class="input" placeholder="Search name or description…" style="max-width:260px;font-size:13px" />
          <select v-model="templateProjectFilter" class="input" style="max-width:180px;font-size:13px">
            <option value="">All projects</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <div class="view-toggle">
            <button :class="['view-toggle-btn', { active: templateViewMode === 'list' }]" title="List view" @click="templateViewMode = 'list'">☰ List</button>
            <button :class="['view-toggle-btn', { active: templateViewMode === 'grid' }]" title="Grid view" @click="templateViewMode = 'grid'">▦ Grid</button>
          </div>
        </div>

        <div v-if="!playbookTemplates.length" class="cards-empty">
          <div style="font-size:28px;margin-bottom:10px">📜</div>
          <div>No playbooks or scripts yet.</div>
          <div v-if="auth.isAdminOrSupport" style="margin-top:8px"><button class="btn btn-primary" @click="openCreate">+ Create your first template</button></div>
        </div>
        <div v-else-if="!filteredPlaybookTemplates.length" class="cards-empty">No templates match this search/project filter.</div>

        <!-- ── List view (default) ──────────────────────────────────────── -->
        <div v-else-if="templateViewMode === 'list'" class="card" style="margin-top:0">
          <table class="table">
            <thead>
              <tr>
                <th>Name</th><th>Type</th><th>Project</th><th>Content</th><th>Created by</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in filteredPlaybookTemplates" :key="t.id">
                <td style="font-weight:600">{{ t.action_type === 'bash_script' ? '⌨' : '📜' }} {{ t.name }}
                  <span v-if="t.default_params?.use_sudo" class="badge badge-orange" style="font-size:9px;margin-left:4px">sudo</span>
                  <span v-if="t.quick_action" class="badge badge-blue" style="font-size:9px;margin-left:4px">Quick Action</span>
                </td>
                <td><span class="badge" :class="t.action_type === 'bash_script' ? 'badge-blue' : 'badge-green'" style="font-size:10px">{{ t.action_type === 'bash_script' ? 'Bash Script' : 'Ansible Playbook' }}</span></td>
                <td style="color:var(--text2);font-size:13px">{{ projectName(t.project_id) || '—' }}</td>
                <td style="color:var(--text2);font-size:12px">{{ t.script_content ? `${t.script_content.split('\n').length} lines` : '—' }}</td>
                <td style="color:var(--text2);font-size:12px">{{ userName(t.created_by) || '—' }}</td>
                <td><span v-if="t.enabled" style="color:#3fb950;font-size:12px">✓ Active</span><span v-else style="color:var(--text2);font-size:12px">Disabled</span></td>
                <td>
                  <div style="display:flex;gap:6px;justify-content:flex-end">
                    <button class="btn-pill btn-pill-outline" style="font-size:11px" :disabled="!t.enabled" @click="openRunModal(t)">▶ Run</button>
                    <template v-if="auth.isAdminOrSupport">
                      <button class="btn-pill btn-pill-outline" style="font-size:11px" @click="openEdit(t)">✎</button>
                      <button class="btn-pill btn-pill-outline" style="font-size:11px;color:var(--danger);border-color:var(--danger)" @click="deleteTemplate(t)">🗑</button>
                    </template>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- ── Grid view ─────────────────────────────────────────────────── -->
        <div v-else class="playbook-grid">
          <div v-for="t in filteredPlaybookTemplates" :key="t.id" class="playbook-card">
            <div class="pb-header">
              <div class="pb-icon">{{ t.action_type === 'bash_script' ? '⌨' : '📜' }}</div>
              <div class="pb-meta">
                <div class="pb-name">{{ t.name }}</div>
                <div class="pb-type-badge">
                  <span class="badge" :class="t.action_type === 'bash_script' ? 'badge-blue' : 'badge-green'" style="font-size:10px">{{ t.action_type === 'bash_script' ? 'Bash Script' : 'Ansible Playbook' }}</span>
                  <span v-if="t.default_params?.use_sudo" class="badge badge-orange" style="font-size:10px;margin-left:4px">sudo</span>
                  <span v-if="t.quick_action" class="badge badge-blue" style="font-size:10px;margin-left:4px">Quick Action</span>
                </div>
              </div>
              <div v-if="!t.enabled" class="pb-disabled-tag">Disabled</div>
            </div>
            <div v-if="t.description" class="pb-desc">{{ t.description }}</div>
            <div class="pb-details">
              <div v-if="t.script_content" class="pb-detail-row">
                <span class="pb-detail-label">Content</span>
                <span class="pb-detail-val" style="color:var(--text2)">{{ t.action_type === 'bash_script' ? 'Bash script' : 'Inline YAML' }} ({{ t.script_content.split('\n').length }} lines)</span>
              </div>
              <div v-if="t.default_params?.imported_from" class="pb-detail-row"><span class="pb-detail-label">Source</span><a :href="t.default_params.imported_from" target="_blank" rel="noopener" class="pb-detail-val" style="color:var(--accent2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:220px;display:inline-block;vertical-align:bottom">{{ t.default_params.imported_from }}</a></div>
              <div v-if="t.credential_id" class="pb-detail-row"><span class="pb-detail-label">Credential</span><span class="pb-detail-val">{{ credName(t.credential_id) }}</span></div>
              <div v-if="(t.target_host_ids || []).length" class="pb-detail-row"><span class="pb-detail-label">Default targets</span><span class="pb-detail-val">{{ t.target_host_ids.length }} host{{ t.target_host_ids.length === 1 ? '' : 's' }}</span></div>
              <div v-if="projectName(t.project_id)" class="pb-detail-row"><span class="pb-detail-label">Project</span><span class="pb-detail-val">{{ projectName(t.project_id) }}</span></div>
              <div v-if="userName(t.created_by)" class="pb-detail-row"><span class="pb-detail-label">Created by</span><span class="pb-detail-val">{{ userName(t.created_by) }}</span></div>
            </div>
            <div class="pb-footer">
              <button class="btn btn-primary btn-sm" :disabled="!t.enabled" @click="openRunModal(t)">▶ Run</button>
              <template v-if="auth.isAdminOrSupport">
                <button class="btn btn-sm" @click="openEdit(t)">✎ Edit</button>
                <button class="btn btn-sm" style="color:var(--danger)" @click="deleteTemplate(t)">🗑</button>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════ -->
      <!-- ALL TEMPLATES tab (admin only)                                    -->
      <!-- ══════════════════════════════════════════════════════════════════ -->
      <div v-if="serviceAvailable && autoTab === 'templates' && auth.isAdminOrSupport" class="card" style="margin-top:0">
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Project</th>
              <th>Credential</th>
              <th>Quick Action</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in allTemplates" :key="t.id">
              <td style="font-weight:600">{{ t.name }}</td>
              <td><span class="badge" :class="actionTypeBadgeClass(t.action_type)" style="font-size:10px">{{ t.action_type }}</span></td>
              <td style="color:var(--text2);font-size:13px">{{ projectName(t.project_id) || '—' }}</td>
              <td style="font-size:13px">{{ credName(t.credential_id) || '—' }}</td>
              <td><span v-if="t.quick_action" class="badge badge-blue" style="font-size:10px">Yes</span><span v-else style="color:var(--text2);font-size:12px">—</span></td>
              <td><span v-if="t.enabled" style="color:#3fb950;font-size:12px">✓ Active</span><span v-else style="color:var(--text2);font-size:12px">Disabled</span></td>
              <td>
                <div style="display:flex;gap:8px;justify-content:flex-end">
                  <button class="btn-pill btn-pill-outline" style="font-size:11px" @click="openRunModal(t)" :disabled="!t.enabled">▶ Run</button>
                  <button class="btn-pill btn-pill-outline" style="font-size:11px" @click="openEditRaw(t)">✎</button>
                  <button class="btn-pill btn-pill-outline" style="font-size:11px;color:var(--danger);border-color:var(--danger)" @click="deleteTemplate(t)">🗑</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!allTemplates.length" style="padding:32px;text-align:center;color:var(--text2)">No job templates yet.</div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════ -->
      <!-- SCHEDULES tab (admin only)                                         -->
      <!-- ══════════════════════════════════════════════════════════════════ -->
      <div v-if="serviceAvailable && autoTab === 'schedules' && auth.isAdminOrSupport" class="card" style="margin-top:0">
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Job Template</th>
              <th>Cron</th>
              <th>Next Run</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in schedules" :key="s.id">
              <td style="font-weight:600">{{ s.name }}</td>
              <td style="font-size:13px">{{ templateName(s.job_template_id) || '—' }}</td>
              <td><code style="font-size:12px;color:#58a6ff">{{ s.cron_expression }}</code></td>
              <td style="font-size:12px;color:var(--text2)">{{ s.next_run_at ? new Date(s.next_run_at).toLocaleString() : '—' }}</td>
              <td><span v-if="s.enabled" style="color:#3fb950;font-size:12px">✓ Active</span><span v-else style="color:var(--text2);font-size:12px">Disabled</span></td>
              <td>
                <div style="display:flex;gap:8px;justify-content:flex-end">
                  <button class="btn-pill btn-pill-outline" style="font-size:11px" @click="openEditSchedule(s)">✎ Edit</button>
                  <button class="btn-pill btn-pill-outline" style="font-size:11px;color:var(--danger);border-color:var(--danger)" @click="deleteSchedule(s)">🗑 Delete</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!schedules.length" style="padding:32px;text-align:center;color:var(--text2)">No schedules yet.</div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════ -->
      <!-- RECENT RUNS tab                                                    -->
      <!-- ══════════════════════════════════════════════════════════════════ -->
      <div v-if="serviceAvailable && autoTab === 'runs'" class="card" style="margin-top:0">
        <div class="card-header">Recent Runs <button class="btn btn-sm" @click="loadRuns">Refresh</button></div>
        <table class="table">
          <thead>
            <tr>
              <th>Template</th>
              <th>Action</th>
              <th>Triggered by</th>
              <th>Hosts</th>
              <th>Login</th>
              <th>Status</th>
              <th>Started</th>
              <th>Duration</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in runs" :key="r.id" style="cursor:pointer" @click="$router.push(`/jobs/${r.id}`)">
              <td style="font-weight:500">{{ r.job_template_name || templateName(r.job_template_id) || '—' }}</td>
              <td><span class="badge badge-gray" style="font-size:11px">{{ r.action_type || '—' }}</span></td>
              <td style="font-size:12px;color:var(--text2)">{{ triggeredByLabel(r) }}</td>
              <td style="font-size:12px;color:var(--text2)" :title="runHostsTitle(r)">{{ runHostsLabel(r) }}</td>
              <td style="font-size:12px;color:var(--text2)">{{ runCredentialLabel(r) }}</td>
              <td><span class="run-status-badge" :class="`run-status--${r.status}`">{{ r.status }}</span></td>
              <td style="font-size:12px;color:var(--text2)">{{ r.started_at ? new Date(r.started_at).toLocaleString() : '—' }}</td>
              <td style="font-size:12px;color:var(--text2)">{{ runDuration(r) }}</td>
              <td>
                <button class="btn-pill btn-pill-outline" style="font-size:11px" @click.stop="$router.push(`/jobs/${r.id}`)">View</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!runs.length" style="padding:32px;text-align:center;color:var(--text2)">No recent runs.</div>
      </div>

    </div><!-- /page -->

    <!-- ── Run Modal ─────────────────────────────────────────────────────── -->
    <div v-if="runDlg.visible" class="modal-overlay" @click.self="runDlg.visible = false">
      <div class="modal modal--lg">
        <div class="modal-header">
          <div>
            <div style="font-size:15px;font-weight:700">▶ Run Playbook</div>
            <div style="font-size:12px;color:var(--text2);margin-top:2px">{{ runDlg.template?.name }}</div>
          </div>
          <button class="btn btn-sm btn-icon" @click="runDlg.visible = false">✕</button>
        </div>
        <div class="modal-body">
          <!-- Subject account: WHAT gets created / managed (account ops only) -->
          <div v-if="isAccountOp" class="form-group subject-box">
            <label class="form-label">Account to {{ accountVerb }} <span style="color:var(--text2);font-weight:400">— the user managed on each host</span></label>
            <select v-model="runDlg.subjectCred" class="input">
              <option value="">{{ runDlg.template?.subject_credential_id ? '— Use template default —' : 'Select an account credential…' }}</option>
              <option v-for="c in allCredentials" :key="c.id" :value="c.id">{{ c.name }}{{ c.username ? ' → user “' + c.username + '”' : '' }}</option>
            </select>
            <div style="font-size:11px;color:var(--text2);margin-top:6px">
              This credential's <b>username</b> is the account created/managed; its secret becomes that account's password/key. Create &amp; manage these under <b>Admin → Credentials</b>, or pin a default on the template in <b>Admin → Automation</b>.
            </div>
            <div v-if="!allCredentials.length" style="font-size:12px;color:var(--text2);margin-top:4px">No credentials available (admin-managed).</div>
          </div>

          <div class="run-grid">
            <!-- ── Targets column ─────────────────────────────────────────── -->
            <div class="run-col">
              <div class="form-group">
                <label class="form-label">Run against</label>
                <div class="radio-row">
                  <label class="radio-opt" :class="{ active: runDlg.targetMode === 'hosts' }"><input type="radio" v-model="runDlg.targetMode" value="hosts" /> Hosts</label>
                  <label class="radio-opt" :class="{ active: runDlg.targetMode === 'groups' }"><input type="radio" v-model="runDlg.targetMode" value="groups" /> Host Groups</label>
                </div>
              </div>

              <!-- Hosts: checkbox list with filter + select-all -->
              <div v-if="runDlg.targetMode === 'hosts'" class="form-group">
                <label class="form-label">Hosts <span style="color:var(--text2);font-weight:400">(none = template defaults)</span></label>
                <input v-model="runDlg.hostFilter" class="input" placeholder="Filter hosts…" style="margin-bottom:8px" />
                <div v-if="!allHosts.length" style="font-size:12px;color:var(--text2)">No hosts available.</div>
                <div v-else class="chk-list chk-list--tall">
                  <label class="chk-row chk-row--head">
                    <input type="checkbox" :checked="allFilteredSelected" @change="toggleAllHosts" />
                    <span style="flex:1;font-weight:600">Select all{{ runDlg.hostFilter ? ' (filtered)' : '' }}</span>
                    <span style="font-size:11px;color:var(--text2)">{{ runDlg.targetHostIds.length }} selected</span>
                  </label>
                  <label v-for="h in filteredHosts" :key="h.id" class="chk-row">
                    <input type="checkbox" :value="h.id" v-model="runDlg.targetHostIds" />
                    <span style="flex:1">{{ h.name }}</span>
                    <span style="font-size:11px;color:var(--text2)">{{ h.ip }}</span>
                  </label>
                  <div v-if="!filteredHosts.length" style="padding:10px;font-size:12px;color:var(--text2)">No hosts match “{{ runDlg.hostFilter }}”.</div>
                </div>
              </div>

              <!-- Host Groups: checkbox list -->
              <div v-else class="form-group">
                <label class="form-label">Host Groups</label>
                <div v-if="!allHostGroups.length" style="font-size:12px;color:var(--text2)">No host groups defined.</div>
                <div v-else class="chk-list chk-list--tall">
                  <label v-for="g in allHostGroups" :key="g.id" class="chk-row">
                    <input type="checkbox" :value="g.id" v-model="runDlg.targetGroups" />
                    <span style="flex:1">{{ g.name }}</span>
                    <span style="font-size:11px;color:var(--text2)">{{ groupHostCount(g.id) }} host{{ groupHostCount(g.id) === 1 ? '' : 's' }}</span>
                  </label>
                </div>
              </div>

              <div class="run-summary">▸ {{ resolvedTargetHosts.length }} host{{ resolvedTargetHosts.length === 1 ? '' : 's' }} targeted</div>
            </div>

            <!-- ── Connection credential column (the login used to reach hosts) ── -->
            <div class="run-col">
              <div class="form-group">
                <label class="form-label">Connection login <span style="color:var(--text2);font-weight:400">— how SeyalRun signs in (needs root/sudo)</span></label>
                <div class="radio-row">
                  <label class="radio-opt" :class="{ active: runDlg.credMode === 'default' }"><input type="radio" v-model="runDlg.credMode" value="default" /> Default</label>
                  <label class="radio-opt" :class="{ active: runDlg.credMode === 'all' }"><input type="radio" v-model="runDlg.credMode" value="all" /> One for all</label>
                  <label class="radio-opt" :class="{ active: runDlg.credMode === 'per_host' }"><input type="radio" v-model="runDlg.credMode" value="per_host" /> Per-host</label>
                </div>
                <div v-if="runDlg.credMode === 'default'" style="font-size:12px;color:var(--text2);margin-top:8px">Each host connects with its own configured push account (the server credential).</div>
              </div>

              <!-- One credential for all hosts: select from a list -->
              <div v-if="runDlg.credMode === 'all'" class="form-group">
                <label class="form-label">Credential for all hosts</label>
                <input v-if="allCredentials.length > 6" v-model="runDlg.credFilter" class="input" placeholder="Filter credentials…" style="margin-bottom:8px" />
                <div v-if="!allCredentials.length" style="font-size:12px;color:var(--text2)">No credentials available (admin-managed).</div>
                <div v-else class="chk-list chk-list--tall">
                  <label v-for="c in filteredCreds" :key="c.id" class="chk-row">
                    <input type="checkbox" :checked="runDlg.credAll === c.id" @change="runDlg.credAll = (runDlg.credAll === c.id ? '' : c.id)" />
                    <span style="flex:1">{{ c.name }}</span>
                    <span style="font-size:11px;color:var(--text2)">{{ c.username || '' }}</span>
                  </label>
                </div>
              </div>

              <!-- Per-host credential: checkbox toggle per host + credential picker -->
              <div v-if="runDlg.credMode === 'per_host'" class="form-group">
                <label class="form-label">Credential per host</label>
                <div v-if="!resolvedTargetHosts.length" style="font-size:12px;color:var(--text2)">Select targets first.</div>
                <div v-else class="chk-list chk-list--tall">
                  <div v-for="h in resolvedTargetHosts" :key="h.id" class="ph-row">
                    <span class="ph-host">{{ h.name }}</span>
                    <select v-model="runDlg.hostCreds[h.id]" class="input input--sm">
                      <option value="">Default (push account)</option>
                      <option v-for="c in allCredentials" :key="c.id" :value="c.id">{{ c.name }}</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="form-group" style="margin-top:8px">
            <label class="form-label">Extra Variables <span style="color:var(--text2);font-weight:400">(JSON, optional)</span></label>
            <textarea
              v-model="runDlg.extraVars"
              class="input code-input"
              rows="3"
              placeholder='{"env": "production", "version": "1.0.0"}'
              spellcheck="false"
            ></textarea>
            <div v-if="runDlg.extraVarsError" style="color:var(--danger);font-size:12px;margin-top:4px">{{ runDlg.extraVarsError }}</div>
          </div>
          <div v-if="runDlg.error" style="color:var(--danger);font-size:13px;margin-top:4px;padding:10px;background:rgba(248,81,73,0.08);border-radius:6px;border:1px solid rgba(248,81,73,0.3)">{{ runDlg.error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="runDlg.visible = false">Cancel</button>
          <button class="btn btn-primary" :disabled="runDlg.running" @click="submitRun">
            {{ runDlg.running ? 'Starting…' : '▶ Run Now' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Create / Edit Playbook Modal ──────────────────────────────────── -->
    <div v-if="editDlg.visible" class="modal-overlay" @click.self="editDlg.visible = false">
      <div class="modal modal--lg">
        <div class="modal-header">
          <div style="font-size:15px;font-weight:700">{{ editDlg.isEdit ? 'Edit Job Template' : 'New Job Template' }}</div>
          <button class="btn btn-sm btn-icon" @click="editDlg.visible = false">✕</button>
        </div>
        <div class="modal-body" style="display:flex;flex-direction:column;gap:14px">
          <div class="form-group">
            <label class="form-label">Type</label>
            <div class="radio-row">
              <label class="radio-opt" :class="{ active: editDlg.form.action_type === 'ansible_playbook' }"><input type="radio" v-model="editDlg.form.action_type" value="ansible_playbook" /> Ansible Playbook</label>
              <label class="radio-opt" :class="{ active: editDlg.form.action_type === 'bash_script' }"><input type="radio" v-model="editDlg.form.action_type" value="bash_script" /> Bash Script</label>
            </div>
          </div>
          <div class="inline-form-row">
            <div class="form-group" style="flex:2">
              <label class="form-label">Name <span style="color:var(--danger)">*</span></label>
              <input v-model="editDlg.form.name" class="input" :placeholder="editDlg.form.action_type === 'bash_script' ? 'e.g. Restart nginx' : 'e.g. Deploy App Stack'" />
            </div>
            <div class="form-group" style="flex:1">
              <label class="form-label">Project <span style="color:var(--danger)">*</span></label>
              <select v-model="editDlg.form.project_id" class="input">
                <option value="">— Select Project —</option>
                <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input v-model="editDlg.form.description" class="input" placeholder="Brief description of what this does" />
          </div>

          <!-- ── Settings (credential / targets / sudo / quick action / status) ── -->
          <div class="inline-form-row">
            <div class="form-group" style="flex:1">
              <label class="form-label">Execution Credential</label>
              <select v-model="editDlg.form.credential_id" class="input">
                <option value="">— None —</option>
                <option v-for="c in allCredentials" :key="c.id" :value="c.id">{{ c.name }} ({{ c.username }})</option>
              </select>
            </div>
            <div class="form-group" style="flex:1">
              <label class="form-label">Default Target Hosts</label>
              <AsyncPicker v-model="editDlg.form.targetHosts" :search-fn="searchHosts" placeholder="Select default hosts…" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label"><input type="checkbox" v-model="editDlg.form.use_sudo" style="margin-right:6px;accent-color:#58a6ff" />Run with sudo</label>
            <div v-if="editDlg.form.use_sudo" style="margin-top:8px">
              <select v-model="editDlg.form.sudo_credential_id" class="input">
                <option value="">— Use the login credential's own password —</option>
                <option v-for="c in allCredentials" :key="c.id" :value="c.id">{{ c.name }} ({{ c.username }})</option>
              </select>
              <div style="font-size:11.5px;color:var(--text2);margin-top:4px">
                The sudo password always comes from a stored credential, never typed here — it's never written into job history. Leave as-is to reuse the same password used to log in over SSH; pick a specific credential only if sudo needs a different password (must be a password-type credential, not an SSH key).
              </div>
            </div>
          </div>
          <div class="inline-form-row">
            <div class="form-group" style="flex:1">
              <label class="form-label"><input type="checkbox" v-model="editDlg.form.quick_action" style="margin-right:6px;accent-color:#58a6ff" />Quick Action button on host cards</label>
            </div>
            <div class="form-group" style="flex:1">
              <label class="form-label">Status</label>
              <select v-model="editDlg.form.enabled" class="input"><option :value="true">Active</option><option :value="false">Disabled</option></select>
            </div>
          </div>
          <div v-if="editDlg.form.action_type === 'bash_script'" class="form-group">
            <label class="form-label">Options / Arguments</label>
            <input v-model="editDlg.form.script_args" class="input" placeholder="e.g. -v --dry-run (passed to the script as $1, $2, … — quote args with spaces)" />
          </div>

          <!-- ── Code (last): the full code editor ────────────────────────── -->
          <div class="form-group">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
              <label class="form-label" style="margin:0">{{ editDlg.form.action_type === 'bash_script' ? 'Script' : 'Inline Playbook YAML' }}</label>
              <button type="button" class="btn btn-sm" :disabled="githubImport.loading" @click="githubImport.visible = true">
                {{ githubImport.loading ? 'Importing…' : '⇩ Import from GitHub' }}
              </button>
            </div>
            <div class="code-editor-wrap">
              <div ref="codeGutterEl" class="code-gutter">{{ codeLineNumbers }}</div>
              <textarea
                ref="codeTextareaEl"
                v-model="editDlg.form.script_content"
                class="input code-input code-input--lg"
                rows="20"
                :placeholder="editDlg.form.action_type === 'bash_script' ? '#!/bin/bash\nset -e\nsystemctl restart nginx' : '---\n- hosts: all\n  tasks:\n    - name: Check connectivity\n      ping:'"
                spellcheck="false"
                @scroll="syncGutterScroll"
              ></textarea>
            </div>
            <div v-if="editDlg.form.imported_from" class="code-source-note">Imported from <a :href="editDlg.form.imported_from" target="_blank" rel="noopener">{{ editDlg.form.imported_from }}</a></div>
            <div v-if="lintErrors.length" class="lint-panel">
              <div v-for="(err, i) in lintErrors" :key="i" class="lint-error">⚠ Line {{ err.line }}: {{ err.message }}</div>
            </div>
            <div v-else-if="editDlg.form.script_content.trim()" class="lint-ok">{{ editDlg.form.action_type === 'bash_script' ? '✓ No unmatched quotes, brackets, or block keywords found' : '✓ Valid YAML — parses as a list of plays' }}</div>
          </div>

          <div v-if="editDlg.error" style="color:var(--danger);font-size:13px;padding:10px;background:rgba(248,81,73,0.08);border-radius:6px;border:1px solid rgba(248,81,73,0.3)">{{ editDlg.error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="editDlg.visible = false">Cancel</button>
          <button class="btn btn-primary" :disabled="editDlg.saving" @click="saveTemplate">{{ editDlg.saving ? 'Saving…' : (editDlg.isEdit ? 'Save' : 'Create') }}</button>
        </div>
      </div>
    </div>

    <!-- ── Import Playbook from GitHub ──────────────────────────────────── -->
    <div v-if="githubImport.visible" class="modal-overlay" @click.self="githubImport.visible = false">
      <div class="modal">
        <div class="modal-header">
          <div style="font-size:15px;font-weight:700">Import {{ editDlg.form.action_type === 'bash_script' ? 'Script' : 'Playbook' }} from GitHub</div>
          <button class="btn btn-sm btn-icon" @click="githubImport.visible = false">✕</button>
        </div>
        <div class="modal-body" style="display:flex;flex-direction:column;gap:14px">
          <div class="form-group">
            <label class="form-label">GitHub URL</label>
            <input v-model="githubImport.url" class="input" :placeholder="editDlg.form.action_type === 'bash_script' ? 'https://github.com/owner/repo/blob/main/script.sh' : 'https://github.com/owner/repo/blob/main/playbook.yml'" @keydown.enter="doGithubImport" />
            <div style="font-size:11.5px;color:var(--text2);margin-top:4px">A github.com file link (blob URL) or a raw.githubusercontent.com link. Replaces the current content below — nothing is saved until you click Save on the template. The URL is kept with the template afterward for reference.</div>
          </div>
          <div v-if="githubImport.error" style="color:var(--danger);font-size:13px;padding:10px;background:rgba(248,81,73,0.08);border-radius:6px;border:1px solid rgba(248,81,73,0.3)">{{ githubImport.error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="githubImport.visible = false">Cancel</button>
          <button class="btn btn-primary" :disabled="githubImport.loading || !githubImport.url.trim()" @click="doGithubImport">{{ githubImport.loading ? 'Importing…' : 'Import' }}</button>
        </div>
      </div>
    </div>

    <!-- ── Schedule Modal ────────────────────────────────────────────────── -->
    <div v-if="schedDlg.visible" class="modal-overlay" @click.self="schedDlg.visible = false">
      <div class="modal">
        <div class="modal-header">
          <div style="font-size:15px;font-weight:700">{{ schedDlg.isEdit ? 'Edit Schedule' : 'New Schedule' }}</div>
          <button class="btn btn-sm btn-icon" @click="schedDlg.visible = false">✕</button>
        </div>
        <div class="modal-body" style="display:flex;flex-direction:column;gap:14px">
          <div class="form-group">
            <label class="form-label">Schedule Name <span style="color:var(--danger)">*</span></label>
            <input v-model="schedDlg.form.name" class="input" placeholder="e.g. Nightly Deploy" />
          </div>
          <div class="form-group">
            <label class="form-label">Job Template <span style="color:var(--danger)">*</span></label>
            <select v-model="schedDlg.form.job_template_id" class="input">
              <option value="">— Select Template —</option>
              <option v-for="t in allTemplates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Cron Expression <span style="color:var(--danger)">*</span></label>
            <input v-model="schedDlg.form.cron_expression" class="input" placeholder="0 2 * * *" />
            <div style="font-size:12px;color:var(--text2);margin-top:4px">{{ cronHuman(schedDlg.form.cron_expression) }}</div>
          </div>
          <div class="form-group">
            <label class="form-label">Status</label>
            <select v-model="schedDlg.form.enabled" class="input"><option :value="true">Active</option><option :value="false">Disabled</option></select>
          </div>
          <div v-if="schedDlg.error" style="color:var(--danger);font-size:13px;padding:10px;background:rgba(248,81,73,0.08);border-radius:6px;border:1px solid rgba(248,81,73,0.3)">{{ schedDlg.error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="schedDlg.visible = false">Cancel</button>
          <button class="btn btn-primary" :disabled="schedDlg.saving" @click="saveSchedule">{{ schedDlg.saving ? 'Saving…' : (schedDlg.isEdit ? 'Save' : 'Create') }}</button>
        </div>
      </div>
    </div>

  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import yaml from 'js-yaml'
import AppShell from '@/components/layout/AppShell.vue'
import AsyncPicker, { type PickerItem } from '@/components/common/AsyncPicker.vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useConfirm } from '@/composables/useConfirm'

const route   = useRoute()
const router  = useRouter()
const auth    = useAuthStore()
const { confirm } = useConfirm()

// ── Service availability ───────────────────────────────────────────────────
const serviceAvailable = ref(false)
const serviceLoading   = ref(false)

// ── Data ───────────────────────────────────────────────────────────────────
const autoTab      = ref<'playbooks' | 'templates' | 'schedules' | 'runs'>('playbooks')
const projects     = ref<any[]>([])
const allTemplates = ref<any[]>([])
const schedules    = ref<any[]>([])
const runs         = ref<any[]>([])

const allCredentials = ref<any[]>([])
const allHosts       = ref<any[]>([])
const allHostGroups  = ref<any[]>([])
// Best-effort — /users degrades to raw ids for callers without list access, same pattern
// already used by JobRunsListView/JobRunView for "triggered by" and now "created by".
const allUsers        = ref<any[]>([])

// ── Playbooks & Scripts toolbar (search / project filter / view mode) ─────────
const templateSearch      = ref('')
const templateProjectFilter = ref('')
const templateViewMode    = ref<'list' | 'grid'>('list')

// ── Computed ───────────────────────────────────────────────────────────────
const playbookTemplates = computed(() => allTemplates.value.filter(t => t.action_type === 'ansible_playbook' || t.action_type === 'bash_script'))

const filteredPlaybookTemplates = computed(() => {
  const q = templateSearch.value.trim().toLowerCase()
  return playbookTemplates.value.filter((t) => {
    if (templateProjectFilter.value && t.project_id !== templateProjectFilter.value) return false
    if (!q) return true
    return t.name.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q)
  })
})

const projectMap  = computed(() => new Map(projects.value.map(p => [p.id, p])))
const templateMap = computed(() => new Map(allTemplates.value.map(t => [t.id, t])))
const credMap     = computed(() => new Map(allCredentials.value.map(c => [c.id, c])))
const hostMap     = computed(() => new Map(allHosts.value.map(h => [h.id, h.name])))
const userMap     = computed(() => new Map(allUsers.value.map(u => [u.id, u.username || u.name || u.id])))

function projectName(id: string | null): string { return id ? (projectMap.value.get(id)?.name || id) : '' }
function templateName(id: string | null): string { return id ? (templateMap.value.get(id)?.name || id) : '' }
function credName(id: string | null): string { return id ? (credMap.value.get(id)?.name || id) : '' }
function userName(id: string | null): string { return id ? (userMap.value.get(id) || id) : '' }

function actionTypeBadgeClass(t: string): string {
  return { ansible_playbook: 'badge-green', bash_script: 'badge-blue', account_push: 'badge-orange', rotate_secret: 'badge-red' }[t] || 'badge-blue'
}
// Ported from the standalone Jobs page (JobRunsListView.vue) when its list moved into
// this tab — resolves the actual username instead of just showing "👤 User".
function triggeredByLabel(run: any): string {
  if (run.triggered_by_kind === 'user' && run.triggered_by_user_id) {
    return '👤 ' + userName(run.triggered_by_user_id)
  }
  const tb = run.triggered_by || ''
  if (tb.startsWith('schedule:')) return '📅 Schedule'
  if (tb.startsWith('zabbix_event:')) return '🔔 Zabbix'
  if (tb.startsWith('manual_trigger:')) return '🖱 Manual'
  return tb || '—'
}
function runHostsLabel(run: any): string {
  const ids: string[] = run.target_host_ids || []
  if (!ids.length) return '—'
  const names = ids.map((id) => hostMap.value.get(id) || id)
  if (names.length <= 2) return names.join(', ')
  return `${names[0]}, ${names[1]} +${names.length - 2}`
}
function runHostsTitle(run: any): string {
  return (run.target_host_ids || []).map((id: string) => hostMap.value.get(id) || id).join(', ')
}
function runCredentialLabel(run: any): string {
  if (Object.keys(run.host_credentials || {}).length) return 'Per-host'
  const cid = run.credential_id
  if (!cid) return 'Default (push acct)'
  return credName(cid) || cid
}
function runDuration(r: any): string {
  if (!r.started_at) return '—'
  const end = r.ended_at ? new Date(r.ended_at).getTime() : Date.now()
  const secs = Math.floor((end - new Date(r.started_at).getTime()) / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}
function cronHuman(cron: string): string {
  if (!cron.trim()) return ''
  const p = cron.trim().split(/\s+/)
  if (p.length !== 5) return ''
  const [min, hr, dom, mon, dow] = p
  if (min === '0' && hr === '*' && dom === '*' && mon === '*' && dow === '*') return 'Every hour, on the hour'
  if (dom === '*' && mon === '*' && dow === '*') { if (min !== '*' && hr !== '*') return `Daily at ${hr.padStart(2,'0')}:${min.padStart(2,'0')}` }
  if (dom === '*' && mon === '*' && dow !== '*') { const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']; return `Every ${days[parseInt(dow)] || dow} at ${hr.padStart(2,'0')}:${min.padStart(2,'0')}` }
  return cron
}

// ── Data loading ───────────────────────────────────────────────────────────
async function loadAll() {
  serviceLoading.value = true; serviceAvailable.value = false
  try {
    const [t, p] = await Promise.all([
      api.get('/job-templates').then(r => r.data),
      api.get('/projects').then(r => r.data),
    ])
    allTemplates.value = t; projects.value = p; serviceAvailable.value = true

    const [sched, creds, hosts, groups, users] = await Promise.all([
      auth.isAdminOrSupport ? api.get('/schedules').then(r => r.data).catch(() => []) : Promise.resolve([]),
      auth.isAdminOrSupport ? api.get('/credentials').then(r => r.data).catch(() => []) : Promise.resolve([]),
      api.get('/hosts').then(r => r.data).catch(() => []),
      api.get('/host-groups').then(r => r.data).catch(() => []),
      api.get('/users').then(r => r.data).catch(() => []),
    ])
    schedules.value = sched; allCredentials.value = creds; allHosts.value = hosts; allHostGroups.value = groups; allUsers.value = users
  } catch {
    serviceAvailable.value = false
  } finally { serviceLoading.value = false }
}

async function loadRuns() {
  if (!serviceAvailable.value) return
  try { runs.value = await api.get('/job-runs').then(r => r.data) }
  catch { runs.value = [] }
}

// ── Host search for AsyncPicker ────────────────────────────────────────────
async function searchHosts(query: string): Promise<PickerItem[]> {
  const q = query.trim().toLowerCase()
  return allHosts.value.filter(h => !q || h.name.toLowerCase().includes(q) || h.ip.includes(q)).slice(0, 20).map(h => ({ id: h.id, label: h.name, sublabel: h.ip }))
}

// ── Run modal ──────────────────────────────────────────────────────────────
const runDlg = reactive({
  visible: false, template: null as any,
  subjectCred: '',                              // account_push/rotate/disable/remove: account to manage
  targetMode: 'hosts' as 'hosts' | 'groups',
  targetHostIds: [] as string[],                // selected host ids (checkbox list)
  hostFilter: '',
  targetGroups: [] as string[],                 // host-group ids
  credMode: 'default' as 'default' | 'all' | 'per_host',
  credAll: '',                                  // credential id when credMode === 'all'
  credFilter: '',
  hostCreds: {} as Record<string, string>,      // host_id → credential_id (per_host)
  extraVars: '', extraVarsError: '', error: '', running: false,
})

// Account-lifecycle ops act on a "subject" account (the user created/managed on hosts),
// distinct from the connection login used to SSH in.
const ACCOUNT_OPS = ['account_push', 'rotate_secret', 'disable_account', 'remove_account']
const isAccountOp = computed(() => ACCOUNT_OPS.includes(runDlg.template?.action_type))
const accountVerb = computed(() => ({
  account_push: 'create / push', rotate_secret: 'rotate secret for',
  disable_account: 'disable', remove_account: 'remove',
}[runDlg.template?.action_type as string] || 'manage'))

function groupHostCount(gid: string): number {
  return allHosts.value.filter((h: any) => (h.group_ids || []).includes(gid)).length
}

// Host checkbox list (filtered) + select-all helpers.
const filteredHosts = computed<any[]>(() => {
  const q = runDlg.hostFilter.trim().toLowerCase()
  return allHosts.value.filter((h: any) => !q || h.name.toLowerCase().includes(q) || (h.ip || '').includes(q))
})
const allFilteredSelected = computed<boolean>(() =>
  filteredHosts.value.length > 0 && filteredHosts.value.every((h: any) => runDlg.targetHostIds.includes(h.id)),
)
function toggleAllHosts() {
  const ids = filteredHosts.value.map((h: any) => h.id)
  if (allFilteredSelected.value) {
    runDlg.targetHostIds = runDlg.targetHostIds.filter(id => !ids.includes(id))
  } else {
    runDlg.targetHostIds = Array.from(new Set([...runDlg.targetHostIds, ...ids]))
  }
}

const filteredCreds = computed<any[]>(() => {
  const q = runDlg.credFilter.trim().toLowerCase()
  return allCredentials.value.filter((c: any) => !q || c.name.toLowerCase().includes(q) || (c.username || '').toLowerCase().includes(q))
})

// Effective target hosts from the current selection (host checkboxes → host groups →
// template defaults), used for the per-host credential list and the summary count.
const resolvedTargetHosts = computed<{ id: string; name: string }[]>(() => {
  if (runDlg.targetMode === 'groups') {
    const gids = new Set(runDlg.targetGroups)
    return allHosts.value
      .filter((h: any) => (h.group_ids || []).some((g: string) => gids.has(g)))
      .map((h: any) => ({ id: h.id, name: h.name }))
  }
  if (runDlg.targetHostIds.length) {
    return runDlg.targetHostIds.map(id => ({ id, name: allHosts.value.find((h: any) => h.id === id)?.name || id }))
  }
  return (runDlg.template?.target_host_ids || []).map((id: string) => ({
    id, name: allHosts.value.find((h: any) => h.id === id)?.name || id,
  }))
})

function openRunModal(t: any) {
  runDlg.template = t
  runDlg.subjectCred = ''
  runDlg.targetMode = 'hosts'
  runDlg.targetHostIds = [...(t.target_host_ids || [])]
  runDlg.hostFilter = ''; runDlg.credFilter = ''
  runDlg.targetGroups = []
  runDlg.credMode = 'default'; runDlg.credAll = ''; runDlg.hostCreds = {}
  runDlg.extraVars = ''; runDlg.extraVarsError = ''; runDlg.error = ''; runDlg.running = false; runDlg.visible = true
}

async function submitRun() {
  runDlg.extraVarsError = ''; runDlg.error = ''
  let params: any = {}
  if (runDlg.extraVars.trim()) {
    try { params = JSON.parse(runDlg.extraVars) }
    catch { runDlg.extraVarsError = 'Invalid JSON'; return }
  }
  if (runDlg.credMode === 'all' && !runDlg.credAll) { runDlg.error = 'Select a credential for all hosts'; return }
  // The subject account (which user to create/manage); empty falls back to the template default.
  if (isAccountOp.value && runDlg.subjectCred) params.subject_credential_id = runDlg.subjectCred
  runDlg.running = true
  try {
    const body: any = { params, credential_mode: runDlg.credMode }
    // Only send explicit targets when the user picked some; empty lets the backend
    // fall back to the template defaults.
    if (runDlg.targetMode === 'groups') {
      body.target_host_ids = resolvedTargetHosts.value.map(h => h.id)
      if (runDlg.targetGroups.length === 1) body.target_host_group_id = runDlg.targetGroups[0]
    } else if (runDlg.targetHostIds.length) {
      body.target_host_ids = [...runDlg.targetHostIds]
    }
    if (runDlg.credMode === 'all') body.credential_id = runDlg.credAll
    if (runDlg.credMode === 'per_host') {
      body.host_credentials = Object.fromEntries(
        Object.entries(runDlg.hostCreds).filter(([, v]) => v),
      )
    }
    const r = await api.post(`/job-templates/${runDlg.template.id}/run`, body)
    const runId = r.data?.run_id
    runDlg.visible = false
    if (runId) router.push(`/jobs/${runId}`)
  } catch (e: any) { runDlg.error = e?.response?.data?.detail || 'Failed to start run'
  } finally { runDlg.running = false }
}

// ── Create / Edit Job Template modal (Ansible Playbook or Bash Script) ─────
const _blankPlaybookForm = () => ({
  name: '', description: '', project_id: '', action_type: 'ansible_playbook' as 'ansible_playbook' | 'bash_script',
  script_content: '', script_args: '', imported_from: '',
  use_sudo: false, sudo_credential_id: '',
  credential_id: '', targetHosts: [] as PickerItem[],
  quick_action: false, enabled: true,
})
const editDlg = reactive({ visible: false, isEdit: false, editingId: '', form: _blankPlaybookForm(), saving: false, error: '' })
const githubImport = reactive({ visible: false, url: '', loading: false, error: '' })
// Any default_params keys this dialog doesn't manage (e.g. survey-driven params set via
// the API on templates not created through this form) — preserved and merged back in on
// save so editing sudo/script_args here can never silently drop unrelated params.
let _otherDefaultParams: Record<string, any> = {}

function openCreate() {
  editDlg.isEdit = false; editDlg.editingId = ''
  Object.assign(editDlg.form, _blankPlaybookForm()); editDlg.error = ''; editDlg.visible = true
  _otherDefaultParams = {}
}
function openEdit(t: any) {
  editDlg.isEdit = true; editDlg.editingId = t.id
  Object.assign(editDlg.form, {
    name: t.name, description: t.description || '', project_id: t.project_id || '',
    action_type: t.action_type === 'bash_script' ? 'bash_script' : 'ansible_playbook',
    script_content: t.script_content || '',
    script_args: t.default_params?.script_args || '', imported_from: t.default_params?.imported_from || '',
    use_sudo: !!t.default_params?.use_sudo, sudo_credential_id: t.default_params?.sudo_credential_id || '',
    credential_id: t.credential_id || '', quick_action: t.quick_action, enabled: t.enabled,
    targetHosts: (t.target_host_ids || []).map((id: string) => ({ id, label: allHosts.value.find((h: any) => h.id === id)?.name || id })).filter((h: PickerItem) => h.label),
  })
  const { script_args, use_sudo, sudo_credential_id, imported_from, ...rest } = t.default_params || {}
  _otherDefaultParams = rest
  editDlg.error = ''; editDlg.visible = true
}
function openCreateTemplate() { openCreate() }
function openEditRaw(t: any) { openEdit(t) }

async function doGithubImport() {
  if (!githubImport.url.trim()) return
  githubImport.loading = true; githubImport.error = ''
  try {
    const r = await api.post('/job-templates/import-playbook', { url: githubImport.url.trim() })
    editDlg.form.script_content = r.data.content
    editDlg.form.imported_from = r.data.source_url || githubImport.url.trim()
    // Auto-detect type from the imported file's extension so the right linter runs.
    // Without this, importing a .sh file while "Ansible Playbook" was still selected
    // ran the YAML parser against real bash and reported false syntax errors — the
    // script was fine, it just was never valid YAML to begin with.
    const importedUrl = (r.data.source_url || githubImport.url).toLowerCase()
    editDlg.form.action_type = /\.(sh|bash)(\?|#|$)/.test(importedUrl) ? 'bash_script' : 'ansible_playbook'
    githubImport.visible = false; githubImport.url = ''
  } catch (e: any) { githubImport.error = e?.response?.data?.detail || 'Import failed'
  } finally { githubImport.loading = false }
}

// ── Code editor line-number gutter (synced scroll with the textarea) ──────
const codeGutterEl = ref<HTMLElement | null>(null)
const codeTextareaEl = ref<HTMLTextAreaElement | null>(null)
const codeLineNumbers = computed(() => {
  const n = (editDlg.form.script_content.match(/\n/g)?.length ?? 0) + 1
  return Array.from({ length: n }, (_, i) => i + 1).join('\n')
})
function syncGutterScroll() {
  if (codeGutterEl.value && codeTextareaEl.value) codeGutterEl.value.scrollTop = codeTextareaEl.value.scrollTop
}

// ── Live syntax checking ────────────────────────────────────────────────
// Ansible: real YAML parsing via js-yaml — catches genuine syntax errors (bad
// indentation, unclosed quotes, tabs, etc.) with accurate line/column numbers.
// Bash: no in-browser shell parser exists, so this is a heuristic scan (quote
// balance, bracket balance, if/fi-for/done-case/esac pairing) — it catches real
// structural mistakes but isn't a full shellcheck replacement.
interface LintError { line: number; message: string }
const lintErrors = ref<LintError[]>([])

function lintYaml(content: string): LintError[] {
  if (!content.trim()) return []
  try {
    const doc = yaml.load(content)
    if (!Array.isArray(doc)) {
      return [{ line: 1, message: 'An Ansible playbook must be a YAML list of plays (starts with "- hosts: …")' }]
    }
    return []
  } catch (e: any) {
    return [{ line: (e?.mark?.line ?? 0) + 1, message: e?.reason || e?.message || 'YAML syntax error' }]
  }
}

// Blanks out quoted-string interiors and comments (preserving line breaks and
// overall length so line numbers stay accurate), using the same \-escape and
// #-comment rules as the quote/bracket balance passes below. Used before
// keyword tokenizing so words that only appear inside a string/comment never
// get parsed as real shell syntax.
function stripStringsAndComments(content: string): string {
  let out = ''
  let inSingle = false, inDouble = false
  for (let i = 0; i < content.length; i++) {
    const c = content[i]
    if (c === '\n') { out += '\n'; continue }
    if (!inSingle && !inDouble && c === '#') {
      while (i < content.length && content[i] !== '\n') { out += ' '; i++ }
      i--
      continue
    }
    if (inDouble) {
      if (c === '\\') { out += '  '; i++; continue }
      if (c === '"') { inDouble = false; out += ' '; continue }
      out += ' '
      continue
    }
    if (inSingle) {
      if (c === "'") { inSingle = false; out += ' '; continue }
      out += ' '
      continue
    }
    if (c === '\\') { out += '  '; i++; continue }
    if (c === '"') { inDouble = true; out += ' '; continue }
    if (c === "'") { inSingle = true; out += ' '; continue }
    out += c
  }
  return out
}

function lintBash(content: string): LintError[] {
  if (!content.trim()) return []
  const errors: LintError[] = []

  // Quote balance (spans lines; respects \-escaping and # comments outside quotes).
  // The comment-skip loop stops ON the newline (not past it) so `continue`'s
  // implicit i++ lands past it too — otherwise that newline never reaches the
  // `c === '\n'` check below and every line-number report after a comment drifts.
  let inSingle = false, inDouble = false, line = 1, quoteLine = 0
  for (let i = 0; i < content.length; i++) {
    const c = content[i]
    if (c === '\n') { line++; continue }
    if (!inSingle && !inDouble && c === '#') { while (i < content.length && content[i] !== '\n') i++; i--; continue }
    if (inDouble) { if (c === '\\') { i++; continue } if (c === '"') inDouble = false; continue }
    if (inSingle) { if (c === "'") inSingle = false; continue }
    if (c === '\\') { i++; continue }
    if (c === '"') { inDouble = true; quoteLine = line }
    else if (c === "'") { inSingle = true; quoteLine = line }
  }
  if (inDouble) errors.push({ line: quoteLine, message: 'Unclosed double quote (")' })
  if (inSingle) errors.push({ line: quoteLine, message: "Unclosed single quote (')" })

  // Quoted-string contents and comments are blanked out (preserving line breaks)
  // once here and reused below, so a plain-English "for"/"if"/"case"/"until"
  // inside an echo/printf message — e.g. echo "checking for host" — is never
  // mistaken for real shell syntax, and so line numbers can be read straight
  // off codeOnly's own line breaks without re-deriving them (avoiding the same
  // comment/newline drift the quote-balance pass above has to guard against).
  const codeOnly = stripStringsAndComments(content)
  const codeLines = codeOnly.split('\n')

  // Bracket balance: (), [], {}. Case-statement patterns (e.g. `"-f "*)`) use a
  // bare `)` that closes the pattern, not a paired bracket — with no case/esac
  // awareness this reads as an unmatched `)` on every single pattern arm, so a
  // stray close while inside a case block is treated as a pattern terminator
  // (silently accepted) rather than a real bracket error.
  const closerFor: Record<string, string> = { ')': '(', ']': '[', '}': '{' }
  const stack: { ch: string; line: number }[] = []
  let caseDepth = 0
  codeLines.forEach((codePart, idx) => {
    for (const tok of codePart.match(/\b[a-zA-Z_]+\b/g) || []) {
      if (tok === 'case') caseDepth++
      else if (tok === 'esac') caseDepth = Math.max(0, caseDepth - 1)
    }
    for (const c of codePart) {
      if (c === '(' || c === '[' || c === '{') stack.push({ ch: c, line: idx + 1 })
      else if (c === ')' || c === ']' || c === '}') {
        const top = stack[stack.length - 1]
        if (top && top.ch === closerFor[c]) { stack.pop(); continue }
        if (c === ')' && caseDepth > 0) continue // case-pattern terminator, not a bracket
        errors.push({ line: idx + 1, message: `Unexpected "${c}" — no matching "${closerFor[c]}"` })
      }
    }
  })
  for (const u of stack) errors.push({ line: u.line, message: `Unclosed "${u.ch}"` })

  // Block-keyword pairing: if/fi, for|while|until/done, case/esac.
  const closerKw: Record<string, string> = { if: 'fi', for: 'done', while: 'done', until: 'done', case: 'esac' }
  const kwStack: { kw: string; line: number }[] = []
  codeLines.forEach((codePart, idx) => {
    const tokens = codePart.match(/\b[a-zA-Z_]+\b/g) || []
    for (const tok of tokens) {
      if (closerKw[tok]) kwStack.push({ kw: tok, line: idx + 1 })
      else if (Object.values(closerKw).includes(tok)) {
        const top = kwStack.pop()
        if (!top) errors.push({ line: idx + 1, message: `Unexpected "${tok}" — no matching opener` })
        else if (closerKw[top.kw] !== tok) errors.push({ line: idx + 1, message: `"${tok}" doesn't match "${top.kw}" opened at line ${top.line} (expected "${closerKw[top.kw]}")` })
      }
    }
  })
  for (const u of kwStack) errors.push({ line: u.line, message: `"${u.kw}" is never closed with "${closerKw[u.kw]}"` })

  return errors.sort((a, b) => a.line - b.line)
}

let lintTimer: ReturnType<typeof setTimeout> | null = null
function runLint() {
  lintErrors.value = editDlg.form.action_type === 'bash_script'
    ? lintBash(editDlg.form.script_content)
    : lintYaml(editDlg.form.script_content)
}
watch(
  () => [editDlg.form.script_content, editDlg.form.action_type, editDlg.visible],
  () => {
    if (lintTimer) clearTimeout(lintTimer)
    lintTimer = setTimeout(runLint, 300)
  },
)

async function saveTemplate() {
  editDlg.error = ''
  if (!editDlg.form.name.trim()) { editDlg.error = 'Name required.'; return }
  if (!editDlg.form.project_id) { editDlg.error = 'Project required.'; return }
  editDlg.saving = true
  try {
    const isBash = editDlg.form.action_type === 'bash_script'
    const p = {
      name: editDlg.form.name.trim(), description: editDlg.form.description,
      project_id: editDlg.form.project_id, action_type: editDlg.form.action_type,
      playbook_path: '',
      script_content: editDlg.form.script_content,
      credential_id: editDlg.form.credential_id || null,
      target_host_ids: editDlg.form.targetHosts.map(h => h.id),
      target_scope: 'hosts', quick_action: editDlg.form.quick_action, enabled: editDlg.form.enabled,
      default_params: {
        ..._otherDefaultParams,
        ...(isBash && editDlg.form.script_args ? { script_args: editDlg.form.script_args } : {}),
        ...(editDlg.form.use_sudo ? { use_sudo: true, sudo_credential_id: editDlg.form.sudo_credential_id || null } : {}),
        ...(editDlg.form.imported_from ? { imported_from: editDlg.form.imported_from } : {}),
      },
    }
    editDlg.isEdit ? await api.put(`/job-templates/${editDlg.editingId}`, p) : await api.post('/job-templates', p)
    editDlg.visible = false; loadAll()
  } catch (e: any) { editDlg.error = e?.response?.data?.detail || 'Save failed'
  } finally { editDlg.saving = false }
}

async function deleteTemplate(t: any) {
  if (!await confirm(`Delete template "${t.name}"?`, { title: 'Delete Template', danger: true, confirmLabel: 'Delete' })) return
  try { await api.delete(`/job-templates/${t.id}`); loadAll() }
  catch (e: any) { alert(e?.response?.data?.detail || 'Failed') }
}

// ── Bulk select/delete for the Playbooks & Scripts list view ──────────────
const selectedTemplateIds = ref<Set<string>>(new Set())
const allTemplatesSelected = computed(() =>
  filteredPlaybookTemplates.value.length > 0 && filteredPlaybookTemplates.value.every((t: any) => selectedTemplateIds.value.has(t.id))
)
function toggleTemplateSelect(id: string) {
  const s = new Set(selectedTemplateIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedTemplateIds.value = s
}
function toggleSelectAllTemplates() {
  selectedTemplateIds.value = allTemplatesSelected.value
    ? new Set()
    : new Set(filteredPlaybookTemplates.value.map((t: any) => t.id))
}
async function bulkDeleteTemplates() {
  const n = selectedTemplateIds.value.size
  if (!n) return
  if (!await confirm(`Delete ${n} selected template${n === 1 ? '' : 's'}? This cannot be undone.`, { title: 'Delete Templates', danger: true, confirmLabel: 'Delete' })) return
  const failures: string[] = []
  for (const id of selectedTemplateIds.value) {
    try { await api.delete(`/job-templates/${id}`) }
    catch (e: any) { failures.push(e?.response?.data?.detail || id) }
  }
  selectedTemplateIds.value = new Set()
  loadAll()
  if (failures.length) alert(`${failures.length} of ${n} failed:\n${failures.join('\n')}`)
}

// ── Schedules modal ────────────────────────────────────────────────────────
const _blankSchedForm = () => ({ name: '', job_template_id: '', cron_expression: '0 2 * * *', enabled: true })
const schedDlg = reactive({ visible: false, isEdit: false, editingId: '', form: _blankSchedForm(), saving: false, error: '' })

function openCreateSchedule() {
  schedDlg.isEdit = false; schedDlg.editingId = ''
  Object.assign(schedDlg.form, _blankSchedForm()); schedDlg.error = ''; schedDlg.visible = true
}
function openEditSchedule(s: any) {
  schedDlg.isEdit = true; schedDlg.editingId = s.id
  Object.assign(schedDlg.form, { name: s.name, job_template_id: s.job_template_id, cron_expression: s.cron_expression, enabled: s.enabled })
  schedDlg.error = ''; schedDlg.visible = true
}
async function saveSchedule() {
  schedDlg.error = ''
  if (!schedDlg.form.name.trim()) { schedDlg.error = 'Name required.'; return }
  if (!schedDlg.form.job_template_id) { schedDlg.error = 'Job template required.'; return }
  if (!schedDlg.form.cron_expression.trim()) { schedDlg.error = 'Cron expression required.'; return }
  schedDlg.saving = true
  try {
    const p = { name: schedDlg.form.name, job_template_id: schedDlg.form.job_template_id, cron_expression: schedDlg.form.cron_expression, enabled: schedDlg.form.enabled, params_override: {} }
    schedDlg.isEdit ? await api.put(`/schedules/${schedDlg.editingId}`, p) : await api.post('/schedules', p)
    schedDlg.visible = false; loadAll()
  } catch (e: any) { schedDlg.error = e?.response?.data?.detail || 'Save failed'
  } finally { schedDlg.saving = false }
}
async function deleteSchedule(s: any) {
  if (!await confirm(`Delete schedule "${s.name}"?`, { title: 'Delete Schedule', danger: true, confirmLabel: 'Delete' })) return
  try { await api.delete(`/schedules/${s.id}`); loadAll() }
  catch (e: any) { alert(e?.response?.data?.detail || 'Failed') }
}

onMounted(async () => {
  // loadRuns() itself no-ops while serviceAvailable is still false (its own guard,
  // to avoid firing before the service is confirmed up) — loadAll() is what flips
  // that flag, so it must run and finish FIRST or the initial fetch silently does
  // nothing and the tab just sits empty until a manual Refresh click.
  await loadAll()
  // The old standalone /jobs page now redirects here with ?tab=runs so existing
  // bookmarks/links still land on the right tab instead of just the default.
  if (route.query.tab === 'runs') { autoTab.value = 'runs'; loadRuns() }
})
</script>

<style scoped>
/* ── Tabs ─────────────────────────────────────────────────────────────────── */
.auto-tabs {
  display: flex; gap: 4px; margin-bottom: 20px;
  border-bottom: 2px solid var(--border); padding-bottom: 0;
}
.auto-tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 18px; font-size: 13px; font-weight: 600;
  background: none; border: none; border-bottom: 2px solid transparent;
  margin-bottom: -2px; color: var(--text2); cursor: pointer; border-radius: 6px 6px 0 0;
  transition: color 0.15s, border-color 0.15s;
}
.auto-tab:hover { color: var(--text1); }
.auto-tab.active { color: var(--accent, #58a6ff); border-bottom-color: var(--accent, #58a6ff); }
.tab-badge { background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: 0 6px; font-size: 11px; font-weight: 700; min-width: 18px; text-align: center; color: var(--text2); }
.auto-tab.active .tab-badge { background: rgba(88,166,255,0.12); border-color: rgba(88,166,255,0.3); color: #58a6ff; }

/* ── Run modal: two-column targets / credentials with checkbox lists ───────── */
.subject-box { background: rgba(88,166,255,0.06); border: 1px solid rgba(88,166,255,0.25); border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; }
.run-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
@media (max-width: 720px) { .run-grid { grid-template-columns: 1fr; } }
.run-col { min-width: 0; }
.run-summary { font-size: 12px; color: var(--text2); margin-top: 8px; padding: 6px 10px; background: var(--surface1); border: 1px solid var(--border); border-radius: 6px; }
.chk-list { display: flex; flex-direction: column; gap: 2px; max-height: 180px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; padding: 4px; }
.chk-list--tall { max-height: 280px; }
.chk-row { display: flex; align-items: center; gap: 10px; font-size: 13px; padding: 8px 10px; border-radius: 6px; cursor: pointer; }
.chk-row:hover { background: var(--surface2); }
.chk-row input { accent-color: #58a6ff; width: 16px; height: 16px; flex-shrink: 0; }
.chk-row--head { position: sticky; top: -4px; background: var(--bg2); border-bottom: 1px solid var(--border); border-radius: 0; z-index: 1; }
.ph-row { display: flex; align-items: center; gap: 10px; padding: 6px 8px; }
.ph-host { flex: 0 0 42%; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ph-row .input--sm { flex: 1; padding: 5px 8px; font-size: 12px; }

/* ── Service unavailable ──────────────────────────────────────────────────── */
.svc-unavailable {
  display: flex; align-items: center; gap: 16px;
  padding: 20px; background: var(--surface1); border: 1px solid var(--border);
  border-radius: 10px; margin-bottom: 20px;
}
.svc-icon { font-size: 28px; opacity: 0.5; }
.svc-title { font-weight: 700; font-size: 15px; margin-bottom: 4px; }
.svc-desc { font-size: 13px; color: var(--text2); }
.svc-desc code { background: var(--surface2); padding: 1px 6px; border-radius: 4px; font-family: var(--font-mono); font-size: 12px; }

/* ── Playbooks & Scripts toolbar ─────────────────────────────────────────── */
.pb-toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
.view-toggle { display: inline-flex; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; margin-left: auto; }
.view-toggle-btn { padding: 6px 12px; font-size: 12.5px; background: var(--bg2); color: var(--text2); border: none; border-right: 1px solid var(--border); cursor: pointer; }
.view-toggle-btn:last-child { border-right: none; }
.view-toggle-btn.active { background: var(--accent2); color: #fff; }
.view-toggle-btn:hover:not(.active) { background: var(--bg3); color: var(--text); }

/* ── Playbook card grid ───────────────────────────────────────────────────── */
.playbook-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}
.playbook-card {
  display: flex; flex-direction: column;
  background: var(--surface1); border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
}
.playbook-card:hover { border-color: var(--accent, #58a6ff); box-shadow: 0 4px 20px rgba(0,0,0,0.12); transform: translateY(-1px); }
.pb-header { display: flex; align-items: flex-start; gap: 12px; padding: 16px 16px 10px; }
.pb-icon { font-size: 22px; flex-shrink: 0; margin-top: 2px; }
.pb-meta { flex: 1; min-width: 0; }
.pb-name { font-size: 15px; font-weight: 700; color: var(--text1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-bottom: 4px; }
.pb-type-badge { display: flex; flex-wrap: wrap; gap: 4px; }
.pb-disabled-tag { font-size: 10px; font-weight: 700; color: var(--text2); background: var(--surface2); border: 1px solid var(--border); padding: 2px 6px; border-radius: 4px; flex-shrink: 0; align-self: flex-start; }
.pb-desc { padding: 0 16px 10px; font-size: 13px; color: var(--text2); line-height: 1.5; }
.pb-details { padding: 10px 16px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 6px; background: var(--surface2); flex: 1; }
.pb-detail-row { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; }
.pb-detail-label { color: var(--text2); min-width: 80px; flex-shrink: 0; }
.pb-detail-val { color: var(--text1); word-break: break-all; }
.pb-footer { display: flex; gap: 8px; padding: 10px 14px; border-top: 1px solid var(--border); }

/* ── Run status badges ────────────────────────────────────────────────────── */
.run-status-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }
.run-status--pending  { background: rgba(139,148,158,0.15); color: #8b949e; }
.run-status--running  { background: rgba(88,166,255,0.15); color: #58a6ff; }
.run-status--success  { background: rgba(63,185,80,0.15); color: #3fb950; }
.run-status--failed   { background: rgba(248,81,73,0.15); color: #f85149; }
.run-status--error    { background: rgba(248,81,73,0.15); color: #f85149; }
.run-status--cancelled{ background: rgba(139,148,158,0.15); color: #8b949e; }

/* ── Code input ───────────────────────────────────────────────────────────── */
.code-input { font-family: var(--font-mono, monospace) !important; font-size: 12px; resize: vertical; }
.code-input--lg { min-height: 340px; line-height: 1.55; }
.code-editor-wrap { display: flex; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.code-editor-wrap .code-input { flex: 1; border: none; border-radius: 0; }
.code-gutter {
  flex-shrink: 0; padding: 8px 10px; text-align: right; user-select: none; pointer-events: none;
  background: var(--bg3); color: var(--text2); font-family: var(--font-mono, monospace);
  font-size: 12px; line-height: 1.55; overflow: hidden; white-space: pre;
  border-right: 1px solid var(--border);
}
.code-source-note { font-size: 11.5px; color: var(--text2); margin-top: 6px; }
.code-source-note a { color: var(--accent2); }
.lint-panel { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.lint-error { font-size: 12px; color: #e3b341; background: rgba(227,179,65,0.08); border: 1px solid rgba(227,179,65,0.25); border-radius: 5px; padding: 6px 10px; font-family: var(--font-mono, monospace); }
.lint-ok { margin-top: 8px; font-size: 12px; color: #3fb950; }

/* ── Inline form row ──────────────────────────────────────────────────────── */
.inline-form-row { display: flex; gap: 14px; flex-wrap: wrap; }
.inline-form-row .form-group { flex: 1; margin-bottom: 0; min-width: 200px; }

/* ── Radio options ────────────────────────────────────────────────────────── */
.radio-row { display: flex; gap: 8px; flex-wrap: wrap; }
.radio-opt { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; padding: 5px 12px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface1); user-select: none; }
.radio-opt.active { border-color: #58a6ff; background: rgba(88,166,255,0.08); color: #58a6ff; }
.radio-opt input { accent-color: #58a6ff; }

/* ── Wide modal ───────────────────────────────────────────────────────────── */
.modal--lg { width: min(860px, 94vw); }

/* ── Extra badges ─────────────────────────────────────────────────────────── */
.badge-green  { background: rgba(63,185,80,0.12); border: 1px solid rgba(63,185,80,0.35); color: #3fb950; }
.badge-orange { background: rgba(240,136,62,0.12); border: 1px solid rgba(240,136,62,0.35); color: #f0883e; }
.badge-red    { background: rgba(248,81,73,0.12); border: 1px solid rgba(248,81,73,0.35); color: #f85149; }

.cards-empty { padding: 48px; text-align: center; color: var(--text2); font-size: 14px; }
</style>
