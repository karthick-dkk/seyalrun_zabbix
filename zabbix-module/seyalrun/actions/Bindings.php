<?php declare(strict_types = 1);

namespace Modules\SeyalRun\Actions;

require_once __DIR__ . '/EmbedAction.php';

class Bindings extends EmbedAction {
	// SeyalRun's existing Zabbix-integration admin page (trigger -> playbook bindings);
	// reused as-is rather than duplicating it as a second "Trigger Bindings" page.
	// SeyalRun's own router gates this route to admin/superadmin, so a plain Zabbix
	// user landing here via SSO would just hit a redirect inside the iframe — gate
	// the menu item itself to Zabbix admins so that never happens.
	protected string $route = 'admin/zabbix-integration';
	protected int $min_user_type = USER_TYPE_ZABBIX_ADMIN;
}
