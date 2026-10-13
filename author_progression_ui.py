"""Apply generated native Armory strings to a separate progression candidate."""
from pathlib import Path
import json
import blam_tags as b
ROOT=Path(__file__).resolve().parent

def title_style(name):
    # Binding constructor is (top, left, bottom, right), not XYWH:
    # blam-tags-py/src/generated.rs:1026. The status scheduler emits at
    # most once every 3 seconds; use one wide strip with a 2.3-second life.
    if name.startswith('sv_tree_'):
        # One short-lived reference page, refreshed at 30 logical ticks. It
        # expires within a second after Resume without a clear-title API.
        return {'text bounds (on screen)':b.Rectangle2d(125,32,590,1120),
                'text color':b.RgbColor(0xFF111820),
                'shadow color':b.RgbColor(0xFFF4F6F8),
                'justification':'left','vertical justification':'top',
                'font':'large body text font','fade in time [seconds]':0.0,
                'up time [seconds]':1.0,'fade out time [seconds]':0.0}
    if name.startswith('sv_node_'):
        bounds=(208,32,370,1120)
        # Skill descriptions use the separate CHUD objective renderer. Keep
        # their inherited colors; cinematic title styling does not prove a
        # change to CHUD appearance.
        text_color=0xFFFFFFFF
        shadow_color=0xFF000000
    else:
        bounds=(28,32,116,1120)
        # Explicit contrast for cinematic notices over the bright outdoor
        # terrain. A pale shadow also separates dark text from shaded rocks.
        text_color=0xFF111820
        shadow_color=0xFFF4F6F8
    return {'text bounds (on screen)':b.Rectangle2d(*bounds),
            'text color':b.RgbColor(text_color),
            'shadow color':b.RgbColor(shadow_color),
            'justification':'left','vertical justification':'top',
            'font':'large body text font','fade in time [seconds]':0.05,
            'up time [seconds]':3600.0 if name=='sv_win' else 2.1,
            'fade out time [seconds]':0.15}


def native_title_text(text):
    """Halo's title renderer consumes |n; ordinary LF is silently ignored."""
    return text.replace('\r\n', '\n').replace('\n', '|n')

def main(root=None):
    root=Path(root) if root is not None else ROOT
    contract=json.loads((root/'progression-contract.json').read_text())
    titles=contract['titles'];assert len(titles)<=128
    tag=b.TagFile.read(root/'native-tags/levels/survivors/last_stand/progression.scenario')
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
    strings=b.TagFile.read(root/'native-tags/ui/survivors/last_stand.multilingual_unicode_string_list')
    sr=strings.root();refs=sr.field('string references').as_block();refs.clear();data=bytearray()
    for name,text in titles.items():
        j=refs.add();refs[j].field('string id').set(name)
        for field in refs[j].field_names():
            if field.endswith(' offset'):refs[j].field(field).set(len(data))
        data.extend(native_title_text(text).encode('utf-8')+b'\0')
    sr.field('string data utf8').set(bytes(data))
    written=[]
    for obj,path in [(strings,root/'native-tags/ui/survivors/progression.multilingual_unicode_string_list'),
                     (tag,root/'native-tags/levels/survivors/last_stand/progression-ui.scenario')]:
        obj.recompute_checksum();obj.write(path)
        assert b.TagFile.read(path).write_to_bytes()==path.read_bytes()
        written.append(path)
    print(f'Authored {len(titles)} titles into progression-ui.scenario; base candidate unchanged.')
    return tuple(written)
if __name__=='__main__':main()
