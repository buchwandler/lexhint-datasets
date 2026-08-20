---
schema_version: 1
object_type: implementation_check
file_version: v2
check_id: check-0024
task_id: task-0001
implementation_run: run-0002
timestamp: '2026-08-20T19:02:01Z'
command: bash -c 'if grep -RInE "senses\.word|SELECT .*FROM (senses|entries|lexeme_domains)|schema.?version.*4|datasets-v1|lexhint-dictionary"
  scripts README.md DATA_SOURCES.md .github/workflows; then exit 1; else echo "no
  obsolete dataset contract references"; fi'
argv:
- bash
- -c
- if grep -RInE "senses\.word|SELECT .*FROM (senses|entries|lexeme_domains)|schema.?version.*4|datasets-v1|lexhint-dictionary"
  scripts README.md DATA_SOURCES.md .github/workflows; then exit 1; else echo "no
  obsolete dataset contract references"; fi
exit_code: 0
status: passed
category: other
summary: Ran bash -c 'if grep -RInE "senses\.word|SELECT .*FROM (senses|entries|lexeme_domains)|schema.?version.*4|datasets-v1|lexhint-dictionary"
  scripts README.md DATA_SOURCES.md .github/workflows; then exit 1; else echo "no
  obsolete dataset contract references"; fi' (exit 0)
stdout_ref: null
stderr_ref: null
combined_ref: null
---

