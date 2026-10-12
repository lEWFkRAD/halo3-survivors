import argparse
from pathlib import Path
import sys

def check(root):
    required = ['tool.exe','sapien.exe','tags','data',
                'tags/levels/survivors/last_stand/last_stand.scenario']
    missing = [p for p in required if not (root/p).exists()]
    for p in missing:
        print('MISSING:',root/p)
    if missing:
        print('BLOCKED: no compiled/playable mod. Install/extract tools and author the scenario first.')
        return 2
    print('Prerequisites found. This does not verify the scenario bindings or compiled scripts.')
    print('Compile and save in Sapien, then test in tag_test before packaging.')
    return 0

if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--tools', type=Path, required=True)
    args=ap.parse_args()
    sys.exit(check(args.tools))
