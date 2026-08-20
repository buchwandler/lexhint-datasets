---
schema_version: 1
object_type: change
file_version: v2
change_id: change-0020
task_id: task-0001
implementation_run: run-0002
timestamp: '2026-08-20T19:02:13Z'
kind: scan
path: .
summary: Reconciled dataset repository and sibling Lexhint implementation changes
  before finishing.
git_commit: null
git_diff_stat: "branch: main\nstatus:\nA  .codecrate.toml\n M .github/workflows/build-release.yml\n\
  M  .gitignore\nA  .taskledger/ledgers/main/active-task.yaml\nAM .taskledger/ledgers/main/events/2026-08-20.ndjson\n\
  A  .taskledger/ledgers/main/indexes/active_locks.json\nA  .taskledger/ledgers/main/indexes/dependencies.json\n\
  A  .taskledger/ledgers/main/indexes/introductions.json\nAM .taskledger/ledgers/main/indexes/task_sidecars.json\n\
  AM .taskledger/ledgers/main/indexes/tasks.json\nA  .taskledger/ledgers/main/tasks/task-0001/artifacts/run-0002-command-0001.log\n\
  A  .taskledger/ledgers/main/tasks/task-0001/changes/change-0001.md\nA  .taskledger/ledgers/main/tasks/task-0001/changes/change-0002.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/changes/change-0003.md\nA  .taskledger/ledgers/main/tasks/task-0001/changes/change-0004.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/changes/change-0005.md\nA  .taskledger/ledgers/main/tasks/task-0001/changes/change-0006.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/changes/change-0007.md\nA  .taskledger/ledgers/main/tasks/task-0001/changes/change-0008.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/changes/change-0009.md\nA  .taskledger/ledgers/main/tasks/task-0001/checks/check-0001.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/checks/check-0002.md\nA  .taskledger/ledgers/main/tasks/task-0001/checks/check-0003.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/checks/check-0004.md\nA  .taskledger/ledgers/main/tasks/task-0001/checks/check-0005.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/checks/check-0006.md\nA  .taskledger/ledgers/main/tasks/task-0001/lock.yaml\n\
  A  .taskledger/ledgers/main/tasks/task-0001/plans/plan-v1.md\nA  .taskledger/ledgers/main/tasks/task-0001/runs/run-0001.md\n\
  AM .taskledger/ledgers/main/tasks/task-0001/runs/run-0002.md\nAM .taskledger/ledgers/main/tasks/task-0001/task.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/todos/todo-0001.md\nA  .taskledger/ledgers/main/tasks/task-0001/todos/todo-0002.md\n\
  A  .taskledger/ledgers/main/tasks/task-0001/todos/todo-0003.md\nA  .taskledger/ledgers/main/tasks/task-0001/todos/todo-0004.md\n\
  AM .taskledger/ledgers/main/tasks/task-0001/todos/todo-0005.md\nAM .taskledger/ledgers/main/tasks/task-0001/todos/todo-0006.md\n\
  AM .taskledger/ledgers/main/tasks/task-0001/todos/todo-0007.md\nAM .taskledger/ledgers/main/tasks/task-0001/todos/todo-0008.md\n\
  AM .taskledger/ledgers/main/tasks/task-0001/todos/todo-0009.md\nAM .taskledger/ledgers/main/tasks/task-0001/todos/todo-0010.md\n\
  \ M DATA_SOURCES.md\n M README.md\nA  datasets.toml\nA  scripts/config.py\nA  scripts/download_source.py\n\
  \ M scripts/package_dataset.py\nAM scripts/package_release.py\nMM scripts/validate.py\n\
  A  tests/test_config.py\nA  tests/test_download_source.py\nA  tests/test_package_release.py\n\
  A  tests/test_validate.py\n?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0010.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0011.md\n?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0012.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0013.md\n?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0014.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0015.md\n?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0016.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0017.md\n?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0018.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/changes/change-0019.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0007.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0008.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0009.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0010.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0011.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0012.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0013.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0014.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0015.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0016.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0017.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0018.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0019.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0020.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0021.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0022.md\n?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0023.md\n\
  ?? .taskledger/ledgers/main/tasks/task-0001/checks/check-0024.md\n?? 01_todo.md\n\
  ?? plan.md\ndiff_stat:\n.github/workflows/build-release.yml                | 201\
  \ ++++++++++++++++----\n .taskledger/ledgers/main/events/2026-08-20.ndjson  |  34\
  \ ++++\n .../ledgers/main/indexes/task_sidecars.json        |   6 +-\n .taskledger/ledgers/main/indexes/tasks.json\
  \        |   8 +-\n .../ledgers/main/tasks/task-0001/runs/run-0002.md  |  28 +++\n\
  \ .taskledger/ledgers/main/tasks/task-0001/task.md   |  12 +-\n .../main/tasks/task-0001/todos/todo-0005.md\
  \        |  25 ++-\n .../main/tasks/task-0001/todos/todo-0006.md        |  26 ++-\n\
  \ .../main/tasks/task-0001/todos/todo-0007.md        |  25 ++-\n .../main/tasks/task-0001/todos/todo-0008.md\
  \        |  26 ++-\n .../main/tasks/task-0001/todos/todo-0009.md        |  25 ++-\n\
  \ .../main/tasks/task-0001/todos/todo-0010.md        |  25 ++-\n DATA_SOURCES.md\
  \                                    |  89 +++++----\n README.md               \
  \                           | 211 +++++++++------------\n scripts/package_dataset.py\
  \                         | 169 ++++-------------\n scripts/package_release.py \
  \                        |  11 +-\n scripts/validate.py                        \
  \        |   2 +-\n 17 files changed, 549 insertions(+), 374 deletions(-)"
command: git branch --show-current && git status --short && git diff --stat
before_hash: null
after_hash: null
exit_code: null
---
Reconciled dataset repository and sibling Lexhint implementation changes before finishing.
