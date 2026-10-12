# Last Stand agent work queue

The complete specifications and acceptance checklists are in [PLAN.md](PLAN.md).
This index is stable; live claims, progress, blockers and evidence belong in the
linked GitHub issues. Read [AGENTS.md](AGENTS.md) before claiming a task.

Priority order is P0 foundations, P1 playable-release work, P2 proposed
expansions, P3 later vehicles. A dependency does not prevent preliminary design
or read-only investigation. No task below is claimed by publishing this plan.

| Task | Priority | Main dependency or gate | Source ownership |
| --- | --- | --- | --- |
| [LS-01 Portable configuration and native bootstrap](https://github.com/lEWFkRAD/halo3-survivors/issues/2) | P0 | None for source work; owned tools for native proof | Setup/helpers/configuration |
| [LS-02 Retail MCC compatibility and save capability](https://github.com/lEWFkRAD/halo3-survivors/issues/3) | P0 | Owner sign-in; native slot | Retail package and capability evidence |
| [LS-03 Native QA and run recovery baseline](https://github.com/lEWFkRAD/halo3-survivors/issues/4) | P0 | Native slot for engine observations | QA helpers, recovery tests and evidence |
| [LS-04 Overhead camera and combat readability](https://github.com/lEWFkRAD/halo3-survivors/issues/5) | P1 | Native slot; LS-02 for retail confirmation | Camera/scenario presentation |
| [LS-05 Graphical Armory and complete skill tree](https://github.com/lEWFkRAD/halo3-survivors/issues/6) | P1 | Native UI spike before full implementation | UI tags/catalog presentation/menu hooks |
| [LS-06 Projectile and melee combat](https://github.com/lEWFkRAD/halo3-survivors/issues/7) | P2 | Native mechanism spike; LS-02 for retail | Combat generator/effect and projectile tags |
| [LS-07 Physical XP drops and collection](https://github.com/lEWFkRAD/halo3-survivors/issues/8) | P2 | Death/drop hook proof; LS-03 | XP observation/object tags/collection |
| [LS-08 Permanent progression between new runs](https://github.com/lEWFkRAD/halo3-survivors/issues/9) | P2 | LS-02 target capabilities; LS-03 recovery | Separate profile/launcher/catalog integration |
| [LS-09 Enemy director and stage pacing](https://github.com/lEWFkRAD/halo3-survivors/issues/10) | P1 | LS-03 observations | Stage cohorts/AI/reward data |
| [LS-10 Complete run balance and performance](https://github.com/lEWFkRAD/halo3-survivors/issues/11) | P1 | Selected milestone features integrated | Playtest evidence and coordinated tuning |
| [LS-11 Packaging installation and release](https://github.com/lEWFkRAD/halo3-survivors/issues/12) | P1 | LS-01/02/03/10 | Installer/promotion/release documentation |
| [LS-12 Vehicle feasibility prototype](https://github.com/lEWFkRAD/halo3-survivors/issues/13) | P3 | Stable camera/combat; target capability findings | One vehicle and isolated arena |
| [LS-13 Integrated vehicle encounters](https://github.com/lEWFkRAD/halo3-survivors/issues/14) | P3 | LS-12; repeat LS-10/11 | Vehicle encounters/recovery/balance |

## Claim and handoff record

Post a claim in the task issue after checking existing claims and open PRs:

```text
Agent:
Task:
Branch and base commit:
Files or area:
Acceptance criteria being handled:
Dependencies or blockers:
Native integration slot needed:
Last update:
```

Before handing off or closing work, add:

```text
Result commit and PR:
Behavior changed:
Source checks:
Native SDK checks:
Retail MCC checks:
Ordinary-run checks:
Evidence paths or links:
Save and package compatibility:
Remaining work and next owner action:
Native slot released or handed to:
```

Use `not run` or `not applicable` explicitly. Do not infer a pass from a missing
result. Close a task only when its checklist is met or the coordinating owner
has recorded an explicit scope decision; link any remaining work.

## GitHub coordination links

[Onyx native integration coordination](https://github.com/lEWFkRAD/halo3-survivors/issues/1) tracks the shared
native slot. Each task row above links to its live issue. The launcher lock
alone does not cover Sapien, tag staging or every QA helper.

All 13 implementation tasks are initially open and unassigned. Read current
issue comments and assignees before starting; this statement records publication
state rather than a live claim snapshot.
