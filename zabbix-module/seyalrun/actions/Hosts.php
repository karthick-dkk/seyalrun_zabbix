<?php declare(strict_types = 1);

namespace Modules\SeyalRun\Actions;

require_once __DIR__ . '/../lib/SsoClient.php';

use API;
use CController;
use CControllerResponseData;
use CWebUser;
use Modules\SeyalRun\Lib\SsoClient;

/**
 * Native "SeyalRun · SSH Hosts" page — NOT embedded/iframed; it calls the Zabbix
 * API directly, in-process, the same way any core Zabbix page does.
 *
 * `editable => true` restricts host.get to hosts the CURRENT Zabbix user can
 * WRITE — that permission is what decides whether a host appears here at all
 * (visibility). Clicking "Terminal" still goes through SeyalRun's own SSO and
 * PAM authorization + credential gate before it ever opens a shell — Zabbix
 * write access never bypasses that, it only controls this icon's visibility.
 *
 * Each row mints its own single-use SSO code (see SsoClient) so a link opened
 * in a brand-new tab works even for a Zabbix user who has never separately
 * logged into SeyalRun directly.
 */
class Hosts extends CController {

	protected function init(): void {
		$this->disableCsrfValidation();
	}

	protected function checkInput(): bool {
		return true;
	}

	protected function checkPermissions(): bool {
		return $this->getUserType() >= USER_TYPE_ZABBIX_USER;
	}

	protected function doAction(): void {
		$sso = new SsoClient();
		$username = (string) CWebUser::$data['username'];
		$user_type = (int) CWebUser::$data['type'];

		$hosts = API::Host()->get([
			'output' => ['hostid', 'name', 'status'],
			'selectInterfaces' => ['ip', 'dns', 'useip', 'port'],
			'selectGroups' => ['name'],
			'selectInventory' => ['os_short'],
			'editable' => true,
			'sortfield' => 'name',
		]);

		$rows = [];
		foreach ($hosts as $host) {
			$os = strtolower((string) ($host['inventory']['os_short'] ?? ''));
			$is_windows = (strpos($os, 'win') !== false);
			$iface = $host['interfaces'][0] ?? null;
			$address = $iface ? ($iface['useip'] === '1' ? $iface['ip'] : $iface['dns']) : '';

			$terminal_url = null;
			if (!$is_windows && $sso->isConfigured()) {
				$terminal_url = $sso->buildEmbedUrl(
					$username, $user_type,
					'terminal?zbx_host=' . rawurlencode($host['hostid']) . '&autoconnect=1'
				);
			}

			$rows[] = [
				'hostid' => $host['hostid'],
				'name' => $host['name'],
				'address' => $address,
				'port' => $iface['port'] ?? '',
				'os' => $is_windows ? 'Windows' : 'Linux',
				'is_linux' => !$is_windows,
				// Zabbix omits the 'groups' key entirely (not even an empty array) for a
				// host with zero group memberships on this API version — verified live.
				'groups' => array_column($host['groups'] ?? [], 'name'),
				'terminal_url' => $terminal_url,
			];
		}

		$this->setResponse(new CControllerResponseData([
			'hosts' => $rows,
			'configured' => $sso->isConfigured(),
			'seyalrun_url' => $sso->baseUrl(),
		]));
	}
}
