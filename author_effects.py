"""Author private auto-attack tags from the owner's Halo 3 inputs."""
from pathlib import Path
import blam_tags as b
ROOT=Path(__file__).resolve().parent
out=ROOT/'native-tags/objects/survivors'
out.mkdir(parents=True,exist_ok=True)
for rank in range(4):
    tag=b.TagFile.read(ROOT/'private-inputs/auto_damage.damage_effect')
    root=tag.root();damage=float(12+8*rank)
    root.field('damage lower bound').set(damage)
    root.field('damage upper bound').set(b.RealBounds(damage,damage))
    tag.recompute_checksum();tag.write(out/f'auto_damage_{rank}.damage_effect')
tag=b.TagFile.read(ROOT/'private-inputs/impact.effect')
locations=tag.root().field('locations').as_block()
for index in range(len(locations)):
    locations[index].field('marker name').set('root')
tag.recompute_checksum();tag.write(out/'auto_impact.effect')
print('Authored four damage tiers and root-attached impact effect.')
