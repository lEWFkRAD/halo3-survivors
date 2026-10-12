"""Configuration failures must be explicit before any native work starts."""

from dataclasses import FrozenInstanceError
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import workspace_config
from workspace_config import ConfigError, ProjectConfig, load_config


class WorkspaceConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "Source Checkout"
        self.workspace.mkdir()
        self.config_dir = self.root / "Local Configuration"
        self.config_dir.mkdir()
        self.config = self.config_dir / "paths.json"

    def write(self, data, path=None):
        target = self.config if path is None else path
        target.write_text(json.dumps(data), encoding="utf-8")
        return target

    def load(self, data):
        return load_config(self.write(data), workspace=self.workspace, environ={})

    def test_no_optional_file_preserves_current_defaults(self):
        config = load_config(workspace=self.workspace, environ={})
        self.assertEqual(config.workspace, self.workspace)
        self.assertIsNone(config.editing_kit)
        self.assertIsNone(config.config_path)
        self.assertEqual(config.remote_host, "onyx-linux")
        self.assertEqual(config.remote_workspace, "/home/jeffrey-watts/Documents/Games/Halo3Survivors")
        self.assertEqual(config.remote_editing_kit, "/home/jeffrey-watts/snap/steam/common/.local/share/Steam/steamapps/common/H3EK")
        self.assertEqual((config.remote_python, config.ssh, config.scp), ("python3", "ssh", "scp"))

    def test_module_directory_is_default_workspace(self):
        with patch.object(Path, "read_text", side_effect=FileNotFoundError):
            config = load_config(environ={})
        self.assertEqual(config.workspace, Path(workspace_config.__file__).resolve().parent)

    def test_optional_workspace_config_is_loaded(self):
        path = self.write(
            {"schema_version": 1, "remote": {"host": "test-host"}},
            self.workspace / "last-stand.local.json",
        )
        config = load_config(workspace=self.workspace, environ={})
        self.assertEqual(config.remote_host, "test-host")
        self.assertEqual(config.config_path, path)

    def test_explicit_config_wins_over_environment_and_optional_file(self):
        explicit = self.write({"schema_version": 1, "remote": {"host": "explicit"}})
        env_file = self.write({"schema_version": 1, "remote": {"host": "environment"}}, self.root / "env.json")
        self.write({"schema_version": 1, "remote": {"host": "optional"}}, self.workspace / "last-stand.local.json")
        config = load_config(explicit, workspace=self.workspace, environ={"LAST_STAND_CONFIG": str(env_file)})
        self.assertEqual(config.remote_host, "explicit")
        self.assertEqual(config.config_path, explicit)

    def test_environment_config_wins_over_optional_file(self):
        selected = self.write({"schema_version": 1, "remote": {"host": "environment"}})
        self.write({"schema_version": 1, "remote": {"host": "optional"}}, self.workspace / "last-stand.local.json")
        config = load_config(workspace=self.workspace, environ={"LAST_STAND_CONFIG": str(selected)})
        self.assertEqual(config.remote_host, "environment")

    def test_default_environment_is_read_when_mapping_not_supplied(self):
        selected = self.write({"schema_version": 1, "remote": {"host": "from-os-env"}})
        with patch.dict("os.environ", {"LAST_STAND_CONFIG": str(selected)}):
            self.assertEqual(load_config(workspace=self.workspace).remote_host, "from-os-env")

    def test_missing_explicit_or_environment_file_is_error(self):
        missing = self.root / "missing.json"
        with self.assertRaisesRegex(ConfigError, "does not exist"):
            load_config(missing, workspace=self.workspace, environ={})
        with self.assertRaisesRegex(ConfigError, "does not exist"):
            load_config(workspace=self.workspace, environ={"LAST_STAND_CONFIG": str(missing)})

    def test_empty_environment_selection_is_error_not_optional_fallback(self):
        with self.assertRaises(ConfigError):
            load_config(workspace=self.workspace, environ={"LAST_STAND_CONFIG": ""})

    def test_loader_path_arguments_report_configuration_errors(self):
        for invalid in (True, 17, {}, b"bytes.json"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ConfigError):
                    load_config(invalid, workspace=self.workspace, environ={})
                with self.assertRaises(ConfigError):
                    load_config(workspace=invalid, environ={})

    def test_relative_selected_file_uses_working_directory(self):
        self.write({"schema_version": 1, "editing_kit": "SDK"})
        with patch.object(Path, "cwd", return_value=self.root):
            config = load_config("Local Configuration/paths.json", workspace=self.workspace, environ={})
        self.assertEqual(config.config_path, self.config)
        self.assertEqual(config.editing_kit, self.config_dir / "SDK")

    def test_file_must_be_readable_utf8_json(self):
        for contents in (b'{"schema_version": 1,}', b"\xff\xfe", b"[]", b"null"):
            with self.subTest(contents=contents):
                self.config.write_bytes(contents)
                with self.assertRaises(ConfigError):
                    load_config(self.config, workspace=self.workspace, environ={})
        with self.assertRaises(ConfigError):
            load_config(self.config_dir, workspace=self.workspace, environ={})

    def test_utf8_bom_is_accepted_for_powershell_created_file(self):
        self.config.write_text('{"schema_version": 1}', encoding="utf-8-sig")
        self.assertEqual(load_config(self.config, workspace=self.workspace, environ={}).config_path, self.config)

    def test_version_is_required_and_strict_integer_one(self):
        for version in (None, True, False, 1.0, "1", 2, [], {}):
            with self.subTest(version=version), self.assertRaises(ConfigError):
                self.load({"schema_version": version})
        with self.assertRaises(ConfigError):
            self.load({})

    def test_unknown_keys_are_rejected_at_each_schema_level(self):
        for data in (
            {"schema_version": 1, "workspace": "/unexpected"},
            {"schema_version": 1, "remote": {"hostname": "typo"}},
            {"schema_version": 1, "tools": {"python": "typo"}},
        ):
            with self.subTest(data=data), self.assertRaisesRegex(ConfigError, "unknown keys"):
                self.load(data)

    def test_duplicate_keys_are_rejected_at_each_schema_level(self):
        for raw in (
            '{"schema_version": 1, "schema_version": 1}',
            '{"schema_version": 1, "remote": {"host": "one", "host": "two"}}',
            '{"schema_version": 1, "tools": {"ssh": "ssh", "ssh": "other"}}',
        ):
            with self.subTest(raw=raw):
                self.config.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(ConfigError, "duplicate"):
                    load_config(self.config, workspace=self.workspace, environ={})

    def test_non_json_numbers_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            self.config.write_text('{"schema_version": 1, "editing_kit": ' + value + '}', encoding="utf-8")
            with self.subTest(value=value), self.assertRaises(ConfigError):
                load_config(self.config, workspace=self.workspace, environ={})

    def test_sections_must_be_objects(self):
        for section in ("remote", "tools"):
            for value in (None, [], "", 1, False):
                with self.subTest(section=section, value=value), self.assertRaises(ConfigError):
                    self.load({"schema_version": 1, section: value})

    def test_configured_values_require_nonempty_strings_without_controls(self):
        for section, name in ((None, "editing_kit"), ("remote", "host"), ("remote", "workspace"), ("remote", "editing_kit"), ("remote", "python"), ("tools", "ssh"), ("tools", "scp")):
            for value in (None, True, 8, [], {}, "", "  ", "ok\0bad", "ok\nbad", "ok\rbad", "ok\tbad", "ok\x7fbad", "ok\x85bad", "ok\u2028bad", "ok\u202ebad", "ok\ud800bad"):
                data = {"schema_version": 1}
                if section is None:
                    data[name] = value
                else:
                    data[section] = {name: value}
                with self.subTest(section=section, name=name, value=value), self.assertRaises(ConfigError):
                    self.load(data)

    def test_relative_owned_and_tool_paths_resolve_against_config_directory(self):
        config = self.load({"schema_version": 1, "editing_kit": "../Owned Halo/H3EK", "tools": {"ssh": "./Tools With Spaces/ssh.exe", "scp": "./Tools With Spaces/scp.exe"}})
        self.assertEqual(config.editing_kit, self.root / "Owned Halo" / "H3EK")
        self.assertEqual(config.ssh, str(self.config_dir / "Tools With Spaces" / "ssh.exe"))
        self.assertEqual(config.scp, str(self.config_dir / "Tools With Spaces" / "scp.exe"))
        self.assertFalse(config.editing_kit.exists())

    def test_absolute_local_paths_and_bare_tool_commands(self):
        kit = self.root / "Owned Halo" / "H3EK"
        ssh = self.root / "Open SSH" / "ssh.exe"
        config = self.load({"schema_version": 1, "editing_kit": str(kit), "tools": {"ssh": str(ssh), "scp": "custom-scp"}})
        self.assertEqual(config.editing_kit, kit)
        self.assertEqual(config.ssh, str(ssh))
        self.assertEqual(config.scp, "custom-scp")

    def test_remote_paths_are_posix_and_allow_spaces(self):
        config = self.load({"schema_version": 1, "remote": {"workspace": "/home/test/Game Workspace", "editing_kit": "/opt/Owned Games/H3EK", "python": "/opt/Python Tools/python3"}})
        self.assertEqual(config.remote_workspace, "/home/test/Game Workspace")
        self.assertEqual(config.remote_editing_kit, "/opt/Owned Games/H3EK")
        self.assertEqual(config.remote_python, "/opt/Python Tools/python3")

    def test_remote_paths_must_be_absolute_and_normalized(self):
        for name in ("workspace", "editing_kit"):
            for value in ("relative/path", "~/work", "/work/../other", "/work/./other", "/work//other", "/work/", "//work", "C:\\Games\\Halo", "/work\\other"):
                with self.subTest(name=name, value=value), self.assertRaises(ConfigError):
                    self.load({"schema_version": 1, "remote": {name: value}})

    def test_safe_ssh_aliases_users_ipv4_and_ipv6_are_accepted(self):
        for host in ("onyx-linux", "game.example.test", "127.0.0.1", "jeff@onyx-linux", "user_1@game.example.test", "::1", "user@[2001:db8::1]", "user@fe80::1%eth0"):
            with self.subTest(host=host):
                self.assertEqual(self.load({"schema_version": 1, "remote": {"host": host}}).remote_host, host)

    def test_host_rejects_options_shell_syntax_whitespace_and_bad_ipv6(self):
        for host in ("-oProxyCommand=bad", "user@-option", "-user@host", "host name", "host;command", "$(whoami)", "host|bad", "host&bad", "host>file", "'host'", '"host"', "host/command", "host\\command", "user@@host", "@host", "user@", "[broken]", "[::1]:22", "host:22", "fe80::1%bad;zone", " host", "host ", "host\u2003name"):
            with self.subTest(host=host), self.assertRaises(ConfigError):
                self.load({"schema_version": 1, "remote": {"host": host}})

    def test_tools_are_executable_values_not_shell_commands(self):
        for section, name in (("tools", "ssh"), ("tools", "scp"), ("remote", "python")):
            for value in ("-option", "python3 -c bad", "ssh; bad", "ssh && bad", "$(bad)", "`bad`", "'ssh'", '"ssh"', "/bin/ssh | bad", " ssh", "ssh "):
                with self.subTest(section=section, name=name, value=value), self.assertRaises(ConfigError):
                    self.load({"schema_version": 1, section: {name: value}})

    def test_result_is_frozen_and_json_display_has_strings(self):
        config = self.load({"schema_version": 1, "editing_kit": "Owned Halo"})
        with self.assertRaises(FrozenInstanceError):
            config.remote_host = "mutated"
        result = json.loads(json.dumps(config.to_dict()))
        self.assertEqual(result["workspace"], str(self.workspace))
        self.assertEqual(result["editing_kit"], str(self.config_dir / "Owned Halo"))
        self.assertEqual(result["config_path"], str(self.config))
        self.assertIsNone(ProjectConfig(self.workspace).to_dict()["editing_kit"])

    def test_loading_never_writes_or_requires_paths_to_exist(self):
        self.write({"schema_version": 1, "editing_kit": "Missing SDK", "tools": {"ssh": "./missing/ssh"}})
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(Path, "mkdir", side_effect=AssertionError("mkdir called")), patch.object(Path, "write_text", side_effect=AssertionError("write called")), patch.object(Path, "write_bytes", side_effect=AssertionError("write called")):
            config = load_config(self.config, workspace=self.workspace, environ={})
        self.assertFalse(config.editing_kit.exists())
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_import_does_not_read_configuration_or_write_files(self):
        spec = importlib.util.spec_from_file_location("workspace_config_import_check", workspace_config.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {spec.name: module}), patch.object(Path, "read_text", side_effect=AssertionError("read config at import")), patch.object(Path, "mkdir", side_effect=AssertionError("mkdir at import")), patch.object(Path, "write_text", side_effect=AssertionError("write at import")), patch.object(Path, "write_bytes", side_effect=AssertionError("write at import")):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.load_config))


if __name__ == "__main__":
    unittest.main()
