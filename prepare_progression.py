"""Prepare native progression only after checking every direct prerequisite."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import tarfile

from preflight import inspect_workspace, print_report
from workspace_config import ConfigError, load_config

ROOT = Path(__file__).resolve().parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--check', action='store_true', help='Read-only prerequisites; do not author tags.')
    parser.add_argument('--json', action='store_true', help='Structured report (requires --check).')
    args = parser.parse_args(argv)
    if args.json and not args.check:
        parser.error('--json requires --check')
    try:
        config = load_config(args.config, workspace=ROOT)
        report = inspect_workspace(config, 'authoring')
        print_report(report, as_json=args.json)
        if not report['ready']:
            return 2
        if args.check:
            return 0
        # Load every module before authoring, including the native binding.
        tags = importlib.import_module('progression_tags')
        generator = importlib.import_module('generate_progression')
        ui = importlib.import_module('author_progression_ui')
        importlib.import_module('progression_catalog')
        tags.main()
        generator.main()
        tags.author_damage()
        ui.main()
        with tarfile.open(ROOT / 'v3-native.tar', 'w') as archive:
            for path in sorted((ROOT / 'native-tags/objects/survivors/v3').glob('*')):
                archive.add(path, arcname=path.relative_to(ROOT / 'native-tags').as_posix())
            path = ROOT / 'native-tags/ui/survivors/progression.multilingual_unicode_string_list'
            archive.add(path, arcname=path.relative_to(ROOT / 'native-tags').as_posix())
        print('Prepared native tags and scripts. Engine compilation still required.')
        return 0
    except (ConfigError, ImportError, SyntaxError, OSError) as error:
        if args.json:
            print(json.dumps({'schema_version': 1, 'stage': 'authoring',
                              'ready': False, 'error': str(error)}))
        else:
            print(f'Preparation failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
