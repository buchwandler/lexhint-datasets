---
schema_version: 1
object_type: implementation_check
file_version: v2
check_id: check-0010
task_id: task-0001
implementation_run: run-0002
timestamp: '2026-08-20T18:59:13Z'
command: ruby -e 'require "yaml"; YAML.load_file(".github/workflows/build-release.yml");
  puts "workflow YAML parsed"'
argv:
- ruby
- -e
- require "yaml"; YAML.load_file(".github/workflows/build-release.yml"); puts "workflow
  YAML parsed"
exit_code: 127
status: failed
category: other
summary: Ran ruby -e 'require "yaml"; YAML.load_file(".github/workflows/build-release.yml");
  puts "workflow YAML parsed"' (exit 127)
stdout_ref: null
stderr_ref: null
combined_ref: null
---

