# Superpowers document header template

Copy these fields to the beginning of every new Superpowers-produced design or plan:

```yaml
---
document_id: YYYY-MM-DD-<project_id>-<topic>-<design|plan>
owner_project: <project_id|repository>
document_type: <design|implementation_plan>
status: <draft|approved|superseded|completed>
created: YYYY-MM-DD
owner: <person-or-role>
canonical_path: <path required by PROJECT_STRUCTURE_CODEX.md>
implements: <approved-design-path-or-null>
supersedes: <canonical-path-or-null>
artifact_roots:
  - <canonical output path>
verification:
  - <exact test or validator command>
---
```

Do not create the document until `owner_project`, `canonical_path`, and artifact ownership
are resolved.
