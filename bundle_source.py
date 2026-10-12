"""Bundle authored Last Stand source only; never collect files by directory glob."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile


SOURCE_FILES = tuple("""
.gitignore
.gitattributes
AGENTS.md
PLAN.md
TASKS.md
DEVELOPMENT.md
ROADMAP.md
author_effects.py
author_hangar.py
author_progression_ui.py
birds_eye.py
bundle_source.py
fetch_progression_inputs.py
generate.py
generate_progression.py
launch-installed.py
launch_v04.py
install_launcher_v04.py
launcher-install-v04.json
record_v03_clip.py
record_v04_clip.py
launch_onyx.py
onyx_progression.py
outdoors.py
polish_native.py
preflight.py
prepare_progression.py
progression_catalog.py
progression_hsc.py
progression_remote.py
progression_tags.py
promote_v03.py
qa_gallery.py
qa_progression.py
qa_v03_final.py
qa_v04.py
qa_v04_gallery.py
remote_build.py
tests/hsc_vm.py
tests/test_autofire.py
tests/test_camera.py
tests/test_progression_native.py
tests/test_promote_v03.py
tests/test_launch_v04.py
tests/test_spawn_geometry.py
tests/test_spawn_runtime.py
tests/test_survival.py
source/last_stand.hsc
source/progression.hsc
camera-grid.json
outdoor-layout.json
progression-layout.json
progression-contract.json
scenario-contract.json
promotion-v03.json
cache-build-receipt-v03.json
native-validation-v03.json
build-result-v03.json
promotion-v04.json
cache-build-receipt-v04.json
native-validation-v04.json
build-result-v04.json
victory-fix.diff
victory-cleanup-v04.diff
README.md
README-v0.3.md
README-v0.4.md
MODLOG.md
""".split())


def source_inputs(root: Path) -> dict[str, bytes]:
    """Read an explicit source snapshot; reject missing or linked inputs."""
    root = root.resolve(strict=True)
    result = {}
    for name in SOURCE_FILES:
        relative = Path(name)
        path = root / relative
        if any(root.joinpath(*relative.parts[:n]).is_symlink()
               for n in range(1, len(relative.parts) + 1)):
            raise ValueError(f"Linked source input is not allowed: {name}")
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Missing or outside source input: {name}")
        result[name] = path.read_bytes()
    return result


def build_bundle(root: Path, output: Path, *, force: bool = False) -> dict:
    root = root.resolve(strict=True)
    output = output.absolute()
    if output.suffix.lower() != '.zip' or output.is_symlink():
        raise ValueError("Output must be an unlinked .zip file")
    if output.exists() and not force:
        raise FileExistsError(f"Bundle already exists; pass --force to replace it: {output}")
    if output.resolve() in {(root / name).resolve() for name in SOURCE_FILES}:
        raise ValueError("Output cannot replace a source input")
    inputs = source_inputs(root)
    manifest = {
        'schema_version': 1,
        'project': 'Last Stand: Halo 3 Survivors',
        'version': '0.4.0',
        'content': 'Authored source only; not a playable map or a release-validation receipt.',
        'files': [{'path': name, 'bytes': len(data),
                   'sha256': hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(inputs.items())],
    }
    inputs['SOURCE-MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.last-stand-source-',
                                         suffix='.zip', delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for name, data in sorted(inputs.items()):
                # Stable metadata makes identical source snapshots reproducible.
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, data, compresslevel=9)
        if not force and output.exists():
            raise FileExistsError(f"Output appeared during bundling: {output}")
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    data = output.read_bytes()
    return {'output': str(output), 'source_files': len(SOURCE_FILES),
            'archive_members': len(inputs), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    output = args.output or args.root / 'dist/last-stand-v0.4-source.zip'
    try:
        print(json.dumps(build_bundle(args.root, output, force=args.force), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Source bundle not created: {error}\n")


if __name__ == '__main__':
    main()
