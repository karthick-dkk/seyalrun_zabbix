<?php declare(strict_types = 1);
/**
 * @var array $data  ['iframe_url' => string|null, 'seyalrun_url' => string, 'configured' => bool]
 */

if (!$data['configured']) {
	echo '<div class="seyalrun-embed-wrap seyalrun-embed-wrap--error">'
		. '<div class="seyalrun-error">'
		. _('The SeyalRun module is not configured yet. Copy modules/seyalrun/config.php.example to config.php and fill in seyalrun_url and module_secret.')
		. '</div></div>';
} elseif ($data['iframe_url'] === null) {
	echo '<div class="seyalrun-embed-wrap seyalrun-embed-wrap--error">'
		. '<div class="seyalrun-error">'
		. _('SeyalRun is unavailable right now (could not sign in). Check that SeyalRun is reachable at ')
		. htmlspecialchars($data['seyalrun_url'], ENT_QUOTES)
		. _(' and that ZABBIX_MODULE_SECRET matches on both sides.')
		. '</div></div>';
} else {
	echo '<div class="seyalrun-embed-wrap">'
		. '<iframe src="' . htmlspecialchars($data['iframe_url'], ENT_QUOTES)
		. '" class="seyalrun-iframe" allow="clipboard-read; clipboard-write"></iframe>'
		. '</div>';
}
?>
<style>
	.seyalrun-embed-wrap { position: relative; width: 100%; height: calc(100vh - 150px); min-height: 480px; }
	.seyalrun-iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
	.seyalrun-embed-wrap--error { display: flex; align-items: flex-start; justify-content: center; padding-top: 60px; }
	.seyalrun-error { max-width: 560px; padding: 16px 18px; border-radius: 4px; background: #fef6f6; border: 1px solid #e45959; color: #7a2020; font-size: 13px; line-height: 1.6; }
</style>
