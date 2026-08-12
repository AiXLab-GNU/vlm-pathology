# Legacy code boundary

This directory preserves historical analysis paths needed to interpret frozen outputs.
Its scripts are not the default implementation surface and their presence does not imply
current validation.

No new analysis file may be created here after the file-governance baseline. Put new
entry points in `../active/`, add focused tests, and record which legacy script or result
they supersede. Existing files are renamed only through a dedicated, hash-audited
provenance migration.
