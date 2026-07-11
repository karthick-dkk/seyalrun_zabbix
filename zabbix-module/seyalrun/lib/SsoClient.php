<?php declare(strict_types = 1);

namespace Modules\SeyalRun\Lib;

/**
 * Talks to SeyalRun's POST /api/v1/auth/zbx-sso-init endpoint to mint a
 * one-time, 120-second SSO code for the currently logged-in Zabbix user, then
 * builds the iframe/link URL SeyalRun exchanges it at.
 *
 * The request body is HMAC-signed with module_secret (config.php) — this is
 * the ONE thing that lets SeyalRun trust "this Zabbix user, at this privilege
 * level" without the user having a prior SeyalRun session. Treat module_secret
 * like SeyalRun's own ZABBIX_WEBHOOK_HMAC_SECRET: required, never logged,
 * rotated only by editing config.php on both sides.
 *
 * A fresh code is minted per page load / per host row (codes are cheap and
 * single-use) so every Zabbix page — and every "Terminal" link on the SSH
 * Hosts page — stays self-contained.
 */
class SsoClient {

	private string $base_url;
	private string $secret;
	private bool $verify_tls;

	public function __construct() {
		$config_file = __DIR__ . '/../config.php';
		$config = is_file($config_file) ? require $config_file : [];

		$this->base_url = rtrim((string) ($config['seyalrun_url'] ?? ''), '/');
		$this->secret = (string) ($config['module_secret'] ?? '');
		$this->verify_tls = (bool) ($config['verify_tls'] ?? true);
	}

	public function isConfigured(): bool {
		return $this->base_url !== '' && $this->secret !== '';
	}

	public function baseUrl(): string {
		return $this->base_url;
	}

	/**
	 * @param string $username         Zabbix username of the currently logged-in user.
	 * @param int    $zabbix_user_type USER_TYPE_* constant (1 user / 2 admin / 3 super admin) —
	 *                                 SeyalRun maps this straight to its own user/admin/superadmin role.
	 * @return string|null             One-time sso_code, or null on ANY failure (not configured,
	 *                                 network error, SeyalRun down, HMAC rejected). Callers must
	 *                                 render a friendly "SeyalRun unavailable" state, never a blank iframe.
	 */
	public function mintSsoCode(string $username, int $zabbix_user_type): ?string {
		if (!$this->isConfigured()) {
			return null;
		}

		$body = json_encode(['username' => $username, 'zabbix_user_type' => $zabbix_user_type], JSON_UNESCAPED_SLASHES);
		if ($body === false) {
			return null;
		}
		$signature = hash_hmac('sha256', $body, $this->secret);

		$ch = curl_init($this->base_url . '/api/v1/auth/zbx-sso-init');
		if ($ch === false) {
			return null;
		}
		curl_setopt_array($ch, [
			CURLOPT_POST => true,
			CURLOPT_POSTFIELDS => $body,
			CURLOPT_HTTPHEADER => [
				'Content-Type: application/json',
				'X-Zabbix-Module-Signature: ' . $signature,
			],
			CURLOPT_RETURNTRANSFER => true,
			CURLOPT_CONNECTTIMEOUT => 3,
			CURLOPT_TIMEOUT => 5,
			CURLOPT_SSL_VERIFYPEER => $this->verify_tls,
			CURLOPT_SSL_VERIFYHOST => $this->verify_tls ? 2 : 0,
		]);
		$response = curl_exec($ch);
		$status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
		curl_close($ch);

		if ($response === false || $status !== 200) {
			return null;
		}
		$data = json_decode($response, true);
		return is_array($data) ? ($data['sso_code'] ?? null) : null;
	}

	/**
	 * Full URL for an embedded/linked SeyalRun route, e.g. "dashboard" or
	 * "terminal?zbx_host=123&autoconnect=1". Returns null if SSO minting
	 * failed — callers must not render an iframe/link pointing at a dead code.
	 */
	public function buildEmbedUrl(string $username, int $zabbix_user_type, string $route): ?string {
		$code = $this->mintSsoCode($username, $zabbix_user_type);
		if ($code === null) {
			return null;
		}
		return $this->base_url . '/?sso_code=' . rawurlencode($code) . '#/' . ltrim($route, '/');
	}
}
