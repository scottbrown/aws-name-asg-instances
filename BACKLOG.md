# Backlog

GitHub Issues are currently disabled on this repository, so planned work is
tracked here.  If Issues are enabled later, these should be moved over and
this file deleted.

---

## 1. Refresh the region list

The `REGIONS` list in `Taskfile.yml` (carried over from the old Ansible
vars) predates a number of current regions -- `eu-north-1`, `eu-south-1`,
`ap-east-1`, `me-south-1`, `af-south-1` and others are missing.

The original reason for maintaining a curated list was that CloudWatch
Events was not available everywhere.  That constraint no longer holds:
EventBridge is in every commercial region.  Either refresh the list or
document it plainly as a user-editable filter.

## 2. Tighten the Lambda's `ec2:CreateTags` permission

`AllowEC2NamingPolicy` grants `ec2:CreateTags` on `Resource: "*"`.  This is
defensible -- concentrating the permission in one audited function instead
of granting it to every instance profile is the entire point of the project
-- but it can be tightened further with a condition restricting tag
creation to the `Name` key, e.g. `aws:RequestTag` / `aws:TagKeys`.

Worth verifying against the EC2 condition keys that `CreateTags` actually
supports before committing to a policy shape.

## 3. Rename the project to `christen`

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
