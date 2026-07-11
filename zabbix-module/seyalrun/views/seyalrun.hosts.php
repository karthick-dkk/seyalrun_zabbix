<?php declare(strict_types = 1);
/**
 * @var array $data  ['hosts' => array[], 'configured' => bool, 'seyalrun_url' => string]
 */
?>
<div class="seyalrun-hosts-wrap">
	<div class="seyalrun-hosts-head">
		<h2><?= _('Your hosts') ?></h2>
		<p class="seyalrun-hosts-sub"><?= _("Linux hosts you can write to, from Zabbix's own permission model.") ?></p>
	</div>

	<?php if (!$data['configured']): ?>
		<div class="seyalrun-error">
			<?= _('The SeyalRun module is not configured yet. Copy modules/seyalrun/config.php.example to config.php and fill in seyalrun_url and module_secret.') ?>
		</div>
	<?php endif; ?>

	<table class="list-table">
		<thead>
			<tr>
				<th><?= _('Zabbix host') ?></th>
				<th><?= _('Interface') ?></th>
				<th><?= _('OS') ?></th>
				<th><?= _('Host group') ?></th>
				<th><?= _('Terminal') ?></th>
			</tr>
		</thead>
		<tbody>
		<?php if (!$data['hosts']): ?>
			<tr>
				<td colspan="5" class="list-table-empty"><?= _('No hosts found, or none you have write access to.') ?></td>
			</tr>
		<?php else: foreach ($data['hosts'] as $host): ?>
			<tr>
				<td><?= htmlspecialchars($host['name'], ENT_QUOTES) ?></td>
				<td class="monospace"><?= htmlspecialchars($host['address'] . ($host['port'] !== '' ? ':' . $host['port'] : ''), ENT_QUOTES) ?></td>
				<td><?= htmlspecialchars($host['os'], ENT_QUOTES) ?></td>
				<td><?= htmlspecialchars(implode(', ', $host['groups']), ENT_QUOTES) ?></td>
				<td>
					<?php if ($host['terminal_url'] !== null): ?>
						<a href="<?= htmlspecialchars($host['terminal_url'], ENT_QUOTES) ?>" target="_blank" rel="noopener"
							class="btn-alt seyalrun-term-btn" title="<?= _('Open SSH terminal via SeyalRun') ?>">
							&#9095;&nbsp;<?= _('Terminal') ?>
						</a>
					<?php elseif ($host['is_linux']): ?>
						<span class="grey"><?= _('SeyalRun unavailable') ?></span>
					<?php else: ?>
						<span class="grey"><?= _('not Linux') ?></span>
					<?php endif; ?>
				</td>
			</tr>
		<?php endforeach; endif; ?>
		</tbody>
	</table>

	<p class="seyalrun-hosts-note">
		<b><?= _('How it decides:') ?></b>
		<?= _("Zabbix's own host write permission decides which hosts appear here. Clicking Terminal opens the SeyalRun SSH terminal, which still enforces SeyalRun's own authorization and credential check — a user without a grant sees a clear request-access message rather than a shell.") ?>
	</p>
</div>
<style>
	.seyalrun-hosts-wrap { padding: 10px 0; }
	.seyalrun-hosts-sub { color: #768d99; margin: 2px 0 14px; }
	.seyalrun-hosts-note { margin-top: 14px; color: #768d99; font-size: 12px; max-width: 900px; line-height: 1.6; }
	.seyalrun-term-btn { text-decoration: none; }
	.seyalrun-error { max-width: 700px; padding: 12px 14px; margin-bottom: 14px; border-radius: 4px; background: #fef6f6; border: 1px solid #e45959; color: #7a2020; font-size: 13px; line-height: 1.6; }
</style>
