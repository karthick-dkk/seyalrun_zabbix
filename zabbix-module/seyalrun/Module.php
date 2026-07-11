<?php declare(strict_types = 1);

namespace Modules\SeyalRun;

use APP;
use CMenu;
use CMenuItem;
use CWebUser;
use Zabbix\Core\CModule as CoreModule;

/**
 * SeyalRun module entry point.
 *
 * Inserts a "SeyalRun" top-level menu item right after Monitoring (Dashboard,
 * Assets, SSH Hosts, Sessions, Jobs, Automation, Trigger Bindings — Trigger
 * Bindings only for Zabbix admins+), and, for super admins only, a "SeyalRun"
 * item under Administration for the platform-settings page.
 *
 * NOTE (read before adjusting for your Zabbix version): the menu-manipulation
 * API (`APP::Component()->get('menu.main')`, `CMenu::insertAfter()`,
 * `CMenuItem`) is stable across 7.0/8.0 in our testing, but Zabbix does shift
 * frontend internals between minor versions occasionally. If the menu doesn't
 * appear after installing, this file — specifically the two insertAfter()
 * calls below — is the one place to adjust; everything else (SSO, controllers,
 * views) is version-independent. See zabbix-module/README.md for the
 * version-shim notes and how to verify.
 */
class Module extends CoreModule {

	public function init(): void {
		$main_menu = APP::Component()->get('menu.main');

		$main_menu->insertAfter(_('Monitoring'),
			(new CMenuItem(_('SeyalRun')))
				->setId('seyalrun')
				->setSubMenu(new CMenu([
					(new CMenuItem(_('Dashboard')))->setAction('seyalrun.dashboard'),
					(new CMenuItem(_('Assets')))->setAction('seyalrun.assets'),
					(new CMenuItem(_('SSH Hosts')))->setAction('seyalrun.hosts'),
					(new CMenuItem(_('Sessions')))->setAction('seyalrun.sessions'),
					(new CMenuItem(_('Jobs')))->setAction('seyalrun.jobs'),
					(new CMenuItem(_('Automation')))->setAction('seyalrun.automation'),
					...(CWebUser::getType() >= USER_TYPE_ZABBIX_ADMIN
						? [(new CMenuItem(_('Trigger Bindings')))->setAction('seyalrun.bindings')]
						: [])
				]))
		);

		if (CWebUser::getType() == USER_TYPE_SUPER_ADMIN) {
			$admin_menu = $main_menu->find(_('Administration'));
			if ($admin_menu !== null && $admin_menu->getSubMenu() !== null) {
				$admin_menu->getSubMenu()->add(
					(new CMenuItem(_('SeyalRun')))->setAction('seyalrun.settings')
				);
			}
		}
	}
}
