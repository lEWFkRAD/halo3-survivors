"""Install the tested launcher after the matching native package is promoted."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil,uuid
import launch_v04 as launcher

def install():
    root=Path(__file__).resolve().parent
    paths=launcher.Paths(root,Path.home()/'snap/steam/common/.local/share/Steam/steamapps/common/H3EK')
    with launcher.launcher_lock(paths):
        if launcher.native_children(paths):raise RuntimeError('Close private tools/game before launcher installation')
        result=json.loads((root/'build-result.json').read_text())
        if result.get('version')!='0.4.0':raise RuntimeError('Promote v0.4.0 first')
        metadata=json.loads((root/'mods/LastStand/ModInfo.json').read_text())
        if metadata.get('ModVersion')!={'Major':0,'Minor':4,'Patch':0}:raise RuntimeError('Package version mismatch')
        current=launcher.fingerprint(paths)
        if current['scenario']!=result['candidate']['scenario_sha256'] or current['hsc']!=result['candidate']['source_hsc_sha256']:
            raise RuntimeError('Installed source/scenario do not match the promoted package')
        source=(root/'launch_v04.py').read_bytes()
        backup=root/'backups'/('launcher-before-v04-'+uuid.uuid4().hex[:10]);backup.mkdir(parents=True)
        for path in (root/'launch.py',paths.init):
            if path.exists():shutil.copy2(path,backup/path.name)
        launcher.atomic_bytes(root/'launch.py',source);(root/'launch.py').chmod(0o755)
        receipt={'version':'0.4.0','installed_at':datetime.now(timezone.utc).isoformat(),
                 'sha256':hashlib.sha256(source).hexdigest(),'backup':str(backup),
                 'launcher':str(root/'launch.py'),'production_profile':str(paths.production)}
        launcher.atomic_bytes(root/'launcher-install-v04.json',(json.dumps(receipt,indent=2)+'\n').encode())
        print(json.dumps(receipt,indent=2))

if __name__=='__main__':install()
