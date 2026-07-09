"""P2 fix: the Ansible inventory must be built as structured YAML (yaml.safe_dump),
so a hostile host address / username / password can never inject inventory variables
or extra host entries the way hand-formatted INI text did."""

from __future__ import annotations

import tempfile

import pytest
import yaml


@pytest.fixture
def mod(load_module):
    return load_module(
        "services/automation-service/app/plugins/executors/ansible_playbook.py",
        "za_ansible_exec",
    )


def _roundtrip(mod, hosts):
    with tempfile.TemporaryDirectory() as d:
        inv = mod.build_inventory(hosts, d)
        # Serialize + parse back exactly as the executor does before invoking ansible.
        return yaml.safe_load(yaml.safe_dump(inv, default_flow_style=False, allow_unicode=True))


def test_malicious_password_stays_a_single_value(mod):
    # A password crafted to inject a ProxyCommand var in the old INI format.
    evil = "hunter2 ansible_ssh_common_args='-o ProxyCommand=/bin/evil'"
    host = {"id": "h1", "ip": "10.0.0.5", "port": 22}
    cred = {"username": "root", "secret_type": "password", "secret": {"password": evil}}
    hv = _roundtrip(mod, [(host, cred)])["all"]["children"]["targets"]["hosts"]["host_h1"]
    assert hv["ansible_ssh_pass"] == evil          # kept verbatim as ONE value
    assert "ansible_ssh_common_args" not in hv     # NOT injected as a separate var
    assert hv["ansible_host"] == "10.0.0.5"


def test_newline_in_address_cannot_inject_host_entries(mod):
    host = {"id": "h2", "ip": "1.2.3.4\n[targets]\nevil ansible_host=9.9.9.9", "port": 22}
    hosts = _roundtrip(mod, [(host, None)])["all"]["children"]["targets"]["hosts"]
    assert list(hosts.keys()) == ["host_h2"]        # exactly one host, no injected entry
    assert hosts["host_h2"]["ansible_host"] == host["ip"]  # newline preserved as data


def test_username_with_spaces_is_contained(mod):
    host = {"id": "h3", "ip": "10.0.0.9"}
    cred = {"username": "root x=y", "secret_type": "password", "secret": {"password": "p"}}
    hv = _roundtrip(mod, [(host, cred)])["all"]["children"]["targets"]["hosts"]["host_h3"]
    assert hv["ansible_user"] == "root x=y"
    assert "x" not in hv  # the "x=y" fragment did not become its own var


def test_non_numeric_port_falls_back_to_22(mod):
    host = {"id": "h4", "ip": "10.0.0.4", "port": "not-a-port"}
    hv = _roundtrip(mod, [(host, None)])["all"]["children"]["targets"]["hosts"]["host_h4"]
    assert hv["ansible_port"] == 22


def test_synthetic_key_decouples_name_from_address(mod):
    host = {"id": "abc", "ip": "10.0.0.1"}
    hosts = _roundtrip(mod, [(host, None)])["all"]["children"]["targets"]["hosts"]
    assert "host_abc" in hosts and hosts["host_abc"]["ansible_host"] == "10.0.0.1"
