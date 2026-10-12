"""Read-only configuration for the Last Stand authoring workspace.

Configuration describes paths and executable names, never shell commands. Loading
does not create directories, import native bindings, connect to a host or inspect
the owned editing-kit installation. Callers perform those checks explicitly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Mapping
import unicodedata


class ConfigError(ValueError):
    """A selected configuration file or value is invalid."""


@dataclass(frozen=True)
class ProjectConfig:
    workspace: Path
    editing_kit: Path | None = None
    remote_host: str = "onyx-linux"
    remote_workspace: str = "/home/jeffrey-watts/Documents/Games/Halo3Survivors"
    remote_editing_kit: str = (
        "/home/jeffrey-watts/snap/steam/common/.local/share/Steam/steamapps/common/H3EK"
    )
    remote_python: str = "python3"
    ssh: str = "ssh"
    scp: str = "scp"
    config_path: Path | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Return the resolved settings as JSON-safe display data."""
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(self).items()
        }


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{name} must be a nonempty string")
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value):
        raise ConfigError(f"{name} must not contain control characters")
    return value


def _object(value: object, name: str, allowed: set[str]) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be an object")
    unknown = set(value) - allowed
    if unknown:
        raise ConfigError(f"{name} has unknown keys: {', '.join(sorted(unknown))}")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"duplicate configuration key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ConfigError(f"invalid JSON constant: {value}")


def _local_path(value: str, base: Path, name: str) -> Path:
    value = _string(value, name)
    try:
        path = Path(value).expanduser()
        return (path if path.is_absolute() else base / path).resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise ConfigError(f"{name} is not a usable local path: {error}") from error


def _path_argument(value: object, name: str) -> str:
    try:
        return _string(os.fspath(value), name)
    except TypeError as error:
        raise ConfigError(f"{name} must be a string or filesystem path") from error


def _remote_path(value: object, name: str) -> str:
    value = _string(value, name)
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or value.startswith("//")
        or ".." in path.parts
        or str(path) != value
        or "\\" in value
    ):
        raise ConfigError(f"{name} must be an absolute normalized POSIX path without '..'")
    return value


def _host(value: object) -> str:
    value = _string(value, "remote.host")
    if value != value.strip() or value.count("@") > 1:
        raise ConfigError("remote.host must be an SSH alias or user@host")
    if "@" in value:
        user, host = value.split("@", 1)
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", user):
            raise ConfigError("remote.host has an invalid SSH user")
    else:
        host = value
    if host.startswith("-") or not host:
        raise ConfigError("remote.host must not be empty or option-shaped")
    if ":" in host or host.startswith("[") or host.endswith("]"):
        address = host[1:-1] if host.startswith("[") and host.endswith("]") else host
        # Zone identifiers contain interface names, not arbitrary SSH syntax.
        if "%" in address:
            address, zone = address.rsplit("%", 1)
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", zone):
                raise ConfigError("remote.host has an invalid IPv6 zone")
        try:
            ipaddress.IPv6Address(address)
        except ValueError as error:
            raise ConfigError("remote.host has an invalid IPv6 address") from error
    elif not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", host):
        raise ConfigError("remote.host must be a safe SSH alias or hostname")
    return value


def _executable(value: object, name: str, base: Path | None = None) -> str:
    value = _string(value, name)
    if value != value.strip() or value.startswith("-"):
        raise ConfigError(f"{name} must name one executable, without arguments")
    if any(char in value for char in ";&|`$<>\"'(){}"):
        raise ConfigError(f"{name} must name one executable, not a shell command")
    has_separator = "/" in value or "\\" in value
    if not has_separator and any(char.isspace() for char in value):
        raise ConfigError(f"{name} must name one executable, without arguments")
    # Separators distinguish paths such as './tools/Open SSH/ssh' from names.
    # Every caller must pass the returned string as one subprocess argv item.
    if base is not None and has_separator:
        return str(_local_path(value, base, name))
    return value


def load_config(
    config_path: str | os.PathLike[str] | None = None,
    *,
    workspace: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ProjectConfig:
    """Load explicit, environment-selected, or optional workspace settings.

    Selection order is ``config_path``, ``LAST_STAND_CONFIG``, then
    ``workspace/last-stand.local.json``. Only the last file is optional. Relative
    config filenames use the caller's working directory; relative configured
    local paths use the selected file's directory. No files are written.
    """
    env = os.environ if environ is None else environ
    root = _local_path(
        _path_argument(workspace, "workspace") if workspace is not None else str(Path(__file__).parent),
        Path.cwd(),
        "workspace",
    )
    selected = config_path if config_path is not None else env.get("LAST_STAND_CONFIG")
    optional = selected is None
    path = (
        root / "last-stand.local.json"
        if optional
        else _local_path(_path_argument(selected, "config_path"), Path.cwd(), "config_path")
    )
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as error:
        if optional:
            return ProjectConfig(workspace=root)
        raise ConfigError(f"configuration file does not exist: {path}") from error
    except (OSError, UnicodeError) as error:
        raise ConfigError(f"cannot read configuration file {path}: {error}") from error
    try:
        data = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_constant)
    except (json.JSONDecodeError, RecursionError) as error:
        raise ConfigError(f"invalid JSON in {path}: {error}") from error
    data = _object(data, "configuration", {"schema_version", "editing_kit", "remote", "tools"})
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ConfigError("schema_version must be the integer 1")
    remote = _object(data.get("remote", {}), "remote", {"host", "workspace", "editing_kit", "python"})
    tools = _object(data.get("tools", {}), "tools", {"ssh", "scp"})
    values: dict = {"workspace": root, "config_path": path}
    if "editing_kit" in data:
        values["editing_kit"] = _local_path(data["editing_kit"], path.parent, "editing_kit")
    if "host" in remote:
        values["remote_host"] = _host(remote["host"])
    for key in ("workspace", "editing_kit"):
        if key in remote:
            values[f"remote_{key}"] = _remote_path(remote[key], f"remote.{key}")
    if "python" in remote:
        values["remote_python"] = _executable(remote["python"], "remote.python")
    for key in ("ssh", "scp"):
        if key in tools:
            values[key] = _executable(tools[key], f"tools.{key}", path.parent)
    return ProjectConfig(**values)
