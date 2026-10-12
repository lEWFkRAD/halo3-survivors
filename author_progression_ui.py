"""Apply generated native Armory strings to a separate progression candidate."""
from pathlib import Path
import json
import blam_tags as b
ROOT=Path(__file__).resolve().parent

def title_style(name):
    # Binding constructor is (top, left, bottom, right), not XYWH:
    # blam-tags-py/src/generated.rs:1026. The status scheduler emits at
    # most once every 3 seconds; use one wide strip with a 2.3-second life.
    if name.startswith('sv_node_'):
        bounds=(208,32,370,1120)
    else:
        bounds=(28,32,116,1120)
    return {'text bounds (on screen)':b.Rectangle2d(*bounds),
            'justification':'left','vertical justification':'top',
            'font':'large body text font','fade in time [seconds]':0.05,
            'up time [seconds]':3600.0 if name=='sv_win' else 2.1,
            'fade out time [seconds]':0.15}

def main():
    contract=json.loads((ROOT/'progression-contract.json').read_text())
    titles=contract['titles'];assert len(titles)<=128
    tag=b.TagFile.read(ROOT/'native-tags/levels/survivors/last_stand/progression.scenario')
    r=tag.root();block=r.field('cutscene titles').as_block()
    assert len(block)>0
    while len(block)>1:block.delete(len(block)-1)
    for i,(name,text) in enumerate(titles.items()):
        if i:
            j=block.duplicate(0);block.move_element(j,len(block)-1)
        row=block[i]
        for k,v in {'name':name,**title_style(name)}.items():row.field(k).set(v)
    assert [block[i].field('name').value for i in range(len(block))]==list(titles)
    r.field('chapter title text').set((0x756e6963,r'ui\survivors\progression'))
    strings=b.TagFile.read(ROOT/'native-tags/ui/survivors/last_stand.multilingual_unicode_string_list')
    sr=strings.root();refs=sr.field('string references').as_block();refs.clear();data=bytearray()
    for name,text in titles.items():
        j=refs.add();refs[j].field('string id').set(name)
        for field in refs[j].field_names():
            if field.endswith(' offset'):refs[j].field(field).set(len(data))
        data.extend(text.encode('utf-8')+b'\0')
    sr.field('string data utf8').set(bytes(data))
    for obj,path in [(strings,ROOT/'native-tags/ui/survivors/progression.multilingual_unicode_string_list'),
                     (tag,ROOT/'native-tags/levels/survivors/last_stand/progression-ui.scenario')]:
        obj.recompute_checksum();obj.write(path)
        assert b.TagFile.read(path).write_to_bytes()==path.read_bytes()
    print(f'Authored {len(titles)} titles into progression-ui.scenario; base candidate unchanged.')
if __name__=='__main__':main()
