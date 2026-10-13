# Contributing to Last Stand

Bug reports, playtest notes, documentation fixes and focused code changes are
welcome. Last Stand is a native Halo 3 survival mod: overhead camera, automatic
attacks, outdoor stages and upgrades carried between stages. Preserve that
direction. Read the [plan](PLAN.md), [task list](TASKS.md) and
[development guide](DEVELOPMENT.md) before substantial implementation work.

Everyone participating follows our [community rules](CODE_OF_CONDUCT.md).
Human and AI-assisted contributions follow the same review and evidence rules.

## Pick the right submission

- **Bug or playtest finding:** search existing issues, then use the bug-report
  template. Include the build/commit, SDK versus retail environment, steps to
  reproduce, expected result and actual result. A clear text report is enough.
- **Idea or feature:** use the feature template and explain the player problem,
  smallest useful change and how it fits the plan. Discuss large features,
  dependencies, architecture or balance changes before investing in a full PR.
- **Small fix:** a focused typo, documentation or isolated bug-fix PR can be
  submitted directly; a separate issue is optional. Explain what it fixes.
- **Existing task:** check the issue and open PRs before starting. Comment with
  your branch, scope, acceptance criteria and whether native testing is needed.
  Respect active claims and leave a handoff when you stop. Use the work-proposal
  template for substantial work that does not already have an issue.

An idea or task claim does not guarantee acceptance or reserve a release date.
Maintainers may request a smaller scope, changes or additional evidence.

## Prepare a pull request

1. Fork the repository if you do not have write access, and create a focused
   branch from current `main`. Keep unrelated cleanup in a separate PR.
2. Link the relevant issue and use its task ID in the branch and PR title when
   one exists, for example `[LS-04] Improve overhead camera recovery`.
3. Edit the authoring source/catalog, then regenerate affected outputs when
   the required local inputs are available. Do not hand-patch generated HSC as
   the lasting implementation. If regeneration is blocked, open a draft and
   state the missing inputs. Preserve exact file bytes/line endings where
   release hashes depend on them.
4. Describe the problem, resulting behavior, checks actually run, limitations
   and save/build compatibility. Use `not run` or `not applicable` explicitly.
   A screenshot, mock test or historical receipt alone is not native proof.
5. Keep review discussion in the PR. The contributor is responsible for
   understanding and checking the submission, including AI-generated code.
   Mention material AI assistance and any unverified portions; never submit
   fabricated test results or work you cannot explain.

Maintainers review and merge contributions. Submitting or merging source does
not authorize changing the installed game, publishing a release or closing a
larger task whose acceptance criteria are still unmet. These are contribution
rules for everyone working on the project.

## Checks should match the change

Documentation-only work needs checked links, readable examples and archive
inclusion where relevant; it does not require owning the game or running Halo.
For code changes, run the relevant checks and normally the source suite:

```sh
python -B preflight.py --stage source
python -B -m unittest discover -s tests -v
```

The source suite works without game assets; native geometry checks may skip
without their external binding/inputs. See [DEVELOPMENT.md](DEVELOPMENT.md).
Tests should verify behavior or a meaningful regression, not just mirror code.
Gameplay changes need exact-candidate native evidence before release. Keep
native-pending source work clearly identified; source tests do not validate
retail MCC, game performance, balance or save compatibility.

Add new authored deliverables to the explicit allowlist in `bundle_source.py`.
The supported fresh-kit build sequence is documented in [BOOTSTRAP.md](BOOTSTRAP.md)
and has bounded SDK evidence in [native-validation-ls01.json](native-validation-ls01.json).
New candidates still need their own native validation. Do not claim a clean
native rebuild unless you performed it and retained the commands/results.

## What must stay out of submissions

Commit authored source, small original text fixtures and necessary documentation.
Do not commit or attach owned Halo tags/assets, SDK tools, compiled maps/caches,
native extensions, save cores, player saves, credentials, private keys or local
configuration. Do not request someone else's game files in an issue.

For third-party snippets, dependencies or original art proposals, identify the
source, author and applicable permission/license; include required attribution.
Discuss binary/art additions first. Do not introduce a project license or change
licensing in an unrelated PR; no project-wide license has been selected yet.

Use sanitized text logs and minimal reproductions. Screenshots or short clips
can be linked in an issue/PR when useful and appropriate to share, but keep
media out of Git and remove personal information, tokens and unrelated desktop
content. Never upload a full save or private asset bundle as bug evidence.

## Native testing and shared machines

The [agent/operator guide](AGENTS.md) applies to anyone touching the shared
Onyx environment, including humans. Reserve the
[native integration slot](https://github.com/lEWFkRAD/halo3-survivors/issues/1)
before staging, compiling, driving input or changing launchers/packages.
Coordinate with the session owner and preserve their checkpoint first. Do not
use or replace the player's save profile for QA, and do not infer an idle host
from an old timestamp. External contributors can propose a bounded experiment
for the operator; repository access does not provide access to shared machines.

Use an isolated QA profile for native experiments. Record the exact candidate,
environment, result and cleanup. Keep SDK, retail and ordinary-run evidence
separate, and leave the next operator a clear handoff.
