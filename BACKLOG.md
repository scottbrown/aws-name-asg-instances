# Backlog

GitHub Issues are currently disabled on this repository, so planned work is
tracked here.  If Issues are enabled later, these should be moved over and
this file deleted.

---

## 1. Rename the project to `christen`

`aws-name-asg-instances` is a mouthful.  Rename to `christen` -- it names
newborn instances, it is short, and it works as a stack name.

Touches: the repository name, the README title, and `PROJECT_NAME` in
`Taskfile.yml` (which feeds the default stack name).

Renaming `cfn-template.yml` to `christen.yml` is optional but consistent.
If it is done, the filename is referenced in four places: the `TEMPLATE`
variable in `Taskfile.yml`, two steps in `.github/workflows/ci.yml`, the
default in `scripts/check_handler.py`, and the deploy examples in the
README.

Note that renaming `PROJECT_NAME` changes the default stack name, so
existing deployments would need either the old value passed explicitly or
a deliberate stack replacement.
