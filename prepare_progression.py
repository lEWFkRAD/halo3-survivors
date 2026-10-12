from pathlib import Path
import json,tarfile
import progression_tags,generate_progression,author_progression_ui
ROOT=Path(__file__).resolve().parent
progression_tags.main()
generate_progression.main()
progression_tags.author_damage()
author_progression_ui.main()
with tarfile.open(ROOT/'v3-native.tar','w') as tf:
 for path in sorted((ROOT/'native-tags/objects/survivors/v3').glob('*')):tf.add(path,arcname=str(path.relative_to(ROOT/'native-tags')).replace('\\','/'))
 path=ROOT/'native-tags/ui/survivors/progression.multilingual_unicode_string_list';tf.add(path,arcname=str(path.relative_to(ROOT/'native-tags')).replace('\\','/'))
print('Prepared native tags and scripts. Engine compilation still required.')
