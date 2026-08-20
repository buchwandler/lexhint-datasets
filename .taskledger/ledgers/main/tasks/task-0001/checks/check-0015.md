---
schema_version: 1
object_type: implementation_check
file_version: v2
check_id: check-0015
task_id: task-0001
implementation_run: run-0002
timestamp: '2026-08-20T19:00:30Z'
command: /home/nahrstaedt/src/wandler/.venv/bin/python -c 'from pathlib import Path;
  text=Path("README.md").read_text()+Path("DATA_SOURCES.md").read_text(); required=("datasets-v2.json",
  "lexical", "runtime", "rich", "source_sha256", "ATTRIBUTION.md"); missing=[item
  for item in required if item not in text]; assert not missing, missing; print("documentation
  contract terms present")'
argv:
- /home/nahrstaedt/src/wandler/.venv/bin/python
- -c
- from pathlib import Path; text=Path("README.md").read_text()+Path("DATA_SOURCES.md").read_text();
  required=("datasets-v2.json", "lexical", "runtime", "rich", "source_sha256", "ATTRIBUTION.md");
  missing=[item for item in required if item not in text]; assert not missing, missing;
  print("documentation contract terms present")
exit_code: 0
status: passed
category: other
summary: Ran /home/nahrstaedt/src/wandler/.venv/bin/python -c 'from pathlib import
  Path; text=Path("README.md").read_text()+Path("DATA_SOURCES.md").read_text(); required=("datasets-v2.json",
  "lexical", "runtime", "rich", "source_sha256", "ATTRIBUTION.md"); missing=[item
  for item in required if item not in text]; assert not missing, missing; print("documentation
  contract terms present")' (exit 0)
stdout_ref: null
stderr_ref: null
combined_ref: null
---

