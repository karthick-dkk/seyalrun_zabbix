<?php declare(strict_types = 1);

namespace Modules\SeyalRun\Actions;

require_once __DIR__ . '/EmbedAction.php';

class Dashboard extends EmbedAction {
	protected string $route = 'dashboard';
}
