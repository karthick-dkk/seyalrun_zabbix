# zabbix-senior-dev skill

Senior Zabbix developer expertise (10y equiv.) with a DevSecOps mindset, packaged as a Claude Skill.

## Layout

```
zabbix-senior-dev/
├── SKILL.md                          # main skill file — always loaded when skill triggers
├── references/                       # loaded on demand, per topic
│   ├── templates.md                  # naming, grouping, YAML round-trip, module pattern
│   ├── lld-preprocessing.md          # LLD design, JS preprocessing, singleton pattern
│   ├── api-automation.md             # Bearer auth, tokens, curl/Python, CI import
│   ├── devsecops.md                  # PSK/TLS, Vault macros, roles, hardening, audit
│   └── troubleshooting.md            # queue, caches, ES bloat, LS backlog, upgrades
├── scripts/                          # add your own reusable scripts here
└── assets/                           # add YAML template starters, JS snippets, etc.
```

## Install

### Claude Code (project scope, shared via git)

```bash
mkdir -p .claude/skills
cp -r zabbix-senior-dev .claude/skills/
git add .claude/skills/zabbix-senior-dev && git commit -m "Add zabbix-senior-dev skill"
```

### Claude Code (personal scope, all projects)

```bash
mkdir -p ~/.claude/skills
cp -r zabbix-senior-dev ~/.claude/skills/
```

### Claude.ai (Pro/Max/Team/Enterprise with code execution)

Zip the folder and upload via Settings → Features → Skills.

```bash
cd $(dirname zabbix-senior-dev)
zip -r zabbix-senior-dev.zip zabbix-senior-dev
```

## Trigger

The skill activates whenever a request mentions Zabbix, monitoring templates, LLD, item prototypes, trigger expressions, preprocessing, macros, `zabbix_sender/get`, agent2 plugins, proxies, HTTP agent, SNMP OIDs, webhooks, `api_jsonrpc.php`, or monitoring-as-code work — even if the word "Zabbix" isn't used.

## Iterate

After a few real uses, note where Claude follows the skill well and where it misses. Feed those observations back and refine the description + reference files. That's how skills get sharp.
