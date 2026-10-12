"""Read-only Armory pages derived from the progression catalog and a run snapshot.

Call ``build_armory_pages(ranks, stage=stage, points=points,
selected_id=node_id)`` with ranks keyed by stable catalog IDs, not HSC globals.
Omitted ranks use the catalog's initial values. A native author can also use
the default snapshot to obtain page order, labels and prerequisite edges.

``state`` describes ownership styling: a purchased node stays purchased even
when its next rank is unavailable. Use ``can_purchase`` and ``reason`` for the
buy affordance, and ``selected`` for focus. This module never spends points,
changes ranks or replaces the generated native purchase guards.
"""
from dataclasses import dataclass
import textwrap
from typing import Any, Literal, Mapping

from progression_catalog import CATALOG

NodeState = Literal['maxed', 'purchased', 'available', 'locked']
UnavailableReason = Literal['maxed', 'stage', 'prerequisite', 'exclusive', 'points']


@dataclass(frozen=True)
class EffectView:
    stat: str
    per_rank: int | float


@dataclass(frozen=True)
class PrerequisiteView:
    id: str
    page_id: str
    rank: int
    actual_rank: int

    @property
    def met(self) -> bool:
        return self.actual_rank >= self.rank


@dataclass(frozen=True)
class PrerequisiteEdge:
    source: str
    target: str
    source_page: str
    target_page: str
    required_rank: int
    met: bool


@dataclass(frozen=True)
class NodeView:
    id: str
    catalog_index: int
    native_global: str
    name: str
    description: str
    effects: tuple[EffectView, ...]
    prerequisites: tuple[PrerequisiteView, ...]
    rank: int
    max_rank: int
    next_cost: int | None
    stage: int
    stage_unlocked: bool
    exclusive_group: str | None
    exclusive_chosen: tuple[str, ...]
    affordable: bool
    selected: bool
    purchased: bool
    maxed: bool
    can_purchase: bool
    state: NodeState
    reason: UnavailableReason | None
    reasons: tuple[UnavailableReason, ...]


@dataclass(frozen=True)
class ArmoryPage:
    id: str
    name: str
    nodes: tuple[NodeView, ...]
    # Incoming prerequisites, including edges from another page if declared.
    edges: tuple[PrerequisiteEdge, ...]


def build_armory_pages(
    ranks: Mapping[str, int] | None = None,
    *,
    stage: int = 1,
    points: int = 0,
    selected_id: str | None = None,
    catalog: Mapping[str, Any] = CATALOG,
) -> tuple[ArmoryPage, ...]:
    """Build pages in first-occurrence catalog order without mutating inputs.

    Availability reasons follow the native guard priority: maximum rank,
    stage, prerequisites, exclusive sibling, then points. ``reasons`` retains
    every applicable blocker in that order; ``reason`` is the first one.
    Affordability means only that the next rank's price fits the wallet. A
    stage-locked or prerequisite-locked node can therefore be affordable.
    A maximum-rank node has no next price and is never affordable.

    ``exclusive_chosen`` lists purchased members of this node's declared
    group, including itself. Only a different member blocks purchase. No
    exclusivity or prerequisite is inferred from an ID or screen position.
    """
    nodes = catalog['nodes']
    by_id = {node['id']: node for node in nodes}
    supplied = ranks or {}
    unknown = set(supplied) - set(by_id)
    if unknown:
        raise ValueError(f'Unknown rank IDs: {sorted(unknown)}')
    if selected_id is not None and selected_id not in by_id:
        raise ValueError(f'Unknown selected ID: {selected_id}')
    if stage < 1 or points < 0:
        raise ValueError('Stage must be positive and points nonnegative')
    current = {node['id']: supplied.get(node['id'], node.get('initial_rank', 0))
               for node in nodes}
    if any(rank < 0 for rank in current.values()):
        raise ValueError('Ranks must be nonnegative')
    page_ids = {node['id']: node['weapon'] or 'support' for node in nodes}
    page_nodes: dict[str, list[NodeView]] = {}
    page_edges: dict[str, list[PrerequisiteEdge]] = {}
    for index, node in enumerate(nodes):
        node_id = node['id']
        page_id = page_ids[node_id]
        rank = current[node_id]
        maxed = rank >= node['max_rank']
        next_cost = None if maxed else node['costs'][rank]
        affordable = next_cost is not None and points >= next_cost
        prerequisites = tuple(
            PrerequisiteView(p['id'], page_ids[p['id']], p['rank'], current[p['id']])
            for p in node['prerequisites'])
        group = node['exclusive_group']
        chosen = tuple(other['id'] for other in nodes
                       if group and other['exclusive_group'] == group
                       and current[other['id']] > 0)
        reasons: list[UnavailableReason] = []
        if maxed:
            reasons.append('maxed')
        if stage < node['stage']:
            reasons.append('stage')
        if any(not prerequisite.met for prerequisite in prerequisites):
            reasons.append('prerequisite')
        if any(other_id != node_id for other_id in chosen):
            reasons.append('exclusive')
        if next_cost is not None and not affordable:
            reasons.append('points')
        purchased = rank > 0
        can_purchase = not reasons
        state: NodeState = ('maxed' if maxed else 'purchased' if purchased
                            else 'available' if can_purchase else 'locked')
        page_nodes.setdefault(page_id, []).append(NodeView(
            id=node_id, catalog_index=index, native_global=node['native_global'],
            name=node['name'], description=node['description'],
            effects=tuple(EffectView(e['stat'], e['per_rank']) for e in node['effects']),
            prerequisites=prerequisites, rank=rank, max_rank=node['max_rank'],
            next_cost=next_cost, stage=node['stage'], stage_unlocked=stage >= node['stage'],
            exclusive_group=group, exclusive_chosen=chosen, affordable=affordable,
            selected=selected_id == node_id, purchased=purchased, maxed=maxed,
            can_purchase=can_purchase, state=state,
            reason=reasons[0] if reasons else None, reasons=tuple(reasons)))
        edges = page_edges.setdefault(page_id, [])
        edges.extend(PrerequisiteEdge(p.id, node_id, p.page_id, page_id, p.rank, p.met)
                     for p in prerequisites)
    return tuple(ArmoryPage(page_id,
                            'Support' if page_id == 'support' else catalog['weapons'][page_id]['name'],
                            tuple(views), tuple(page_edges[page_id]))
                 for page_id, views in page_nodes.items())


def native_page_titles(catalog: Mapping[str, Any] = CATALOG) -> dict[str, str]:
    """Return bounded ASCII reference maps for native cinematic title slots.

    These maps show static catalog topology and stage gates. They intentionally
    contain no snapshot rank, selection or affordability: the selected native
    CHUD detail remains the source of current purchase information. A number
    after a prerequisite label is its required rank, not the player's rank.
    Labels and incoming edges come from the catalog, including external-page
    requirements. The current seven pages fit 60 columns and 12 lines each;
    future catalog changes that exceed this budget fail visibly.
    """
    pages = build_armory_pages(catalog=catalog)
    all_nodes = {node.id: (page, node) for page in pages for node in page.nodes}

    def label(node_id: str, current_page: str) -> str:
        page, node = all_nodes[node_id]
        name = node.name.removeprefix(page.name + ': ')
        if name == 'Unlock ' + page.name:
            name = 'Unlock'
        return name if page.id == current_page else page.name + ': ' + name

    def requirement_key(node: NodeView) -> tuple[tuple[str, int], ...]:
        return tuple((p.id, p.rank) for p in node.prerequisites)

    titles: dict[str, str] = {}
    for index, page in enumerate(pages):
        def requirements(node: NodeView) -> str:
            return ' + '.join(label(p.id, page.id) + str(p.rank) for p in node.prerequisites)

        def gated(node: NodeView) -> str:
            return f'{label(node.id, page.id)} [S{node.stage}]'

        groups: dict[str, list[NodeView]] = {}
        for node in page.nodes:
            if node.exclusive_group:
                groups.setdefault(node.exclusive_group, []).append(node)
        branches = {node.id: node for members in groups.values() for node in members}
        descendants: dict[str, list[NodeView]] = {node_id: [] for node_id in branches}
        assigned = set(branches)
        for node in page.nodes:
            branch_parents = [p.id for p in node.prerequisites if p.id in branches]
            if not node.exclusive_group and len(branch_parents) == 1:
                descendants[branch_parents[0]].append(node)
                assigned.add(node.id)

        lines = [page.name.upper() + ' | TREE | S = stage',
                 'Numbers = required ranks, not current ranks']
        rendered: set[str] = set()
        # Nodes without specializations (including support chains) are rendered
        # from their exact incoming edges. Equal requirements share one row.
        for node in page.nodes:
            if node.id in assigned or node.id in rendered:
                continue
            peers = [node]
            if node.prerequisites:
                peers = [other for other in page.nodes
                         if other.id not in assigned and other.id not in rendered
                         and requirement_key(other) == requirement_key(node)]
            row = ' + '.join(gated(other) for other in peers)
            lines.append((requirements(node) + ' -> ' if node.prerequisites else '') + row)
            rendered.update(other.id for other in peers)

        for members in groups.values():
            shared = all(requirement_key(node) == requirement_key(members[0]) for node in members)
            prefix = requirements(members[0]) + ' -> ' if shared and members[0].prerequisites else ''
            lines.append(prefix + 'choose ONE:')
            for branch_index, branch in enumerate(members):
                if not shared and branch.prerequisites:
                    lines.append('  ' + requirements(branch) + ' ->')
                lines.append('  +-> ' + gated(branch))
                stem = '  |   ' if branch_index < len(members) - 1 else '      '
                for descendant in descendants[branch.id]:
                    lines.append(stem + requirements(descendant))
                    lines.append(stem + '-> ' + gated(descendant))
        wrapped = [part for line in lines for part in textwrap.wrap(
            line, width=60, subsequent_indent='      ', break_long_words=False,
            break_on_hyphens=False)]
        title = '\n'.join(wrapped)
        if not title.isascii() or len(wrapped) > 12 or any(len(line) > 60 for line in wrapped):
            raise ValueError(f'Native Armory page exceeds ASCII/60-column/12-line budget: {page.id}')
        titles[f'sv_tree_{index}'] = title
    return titles
