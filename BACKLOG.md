# Backlog

GitHub Issues are currently disabled on this repository, so planned work is
tracked here.  If Issues are enabled later, these should be moved over and
this file deleted.

---

## 1. Lambda runtime `python3.6` is no longer accepted by AWS

**Priority: blocker.**  `cfn-template.yml` sets `Runtime: "python3.6"`.  AWS
no longer permits creating functions on that runtime, so a fresh deploy of
this stack fails outright.

Bump to a current runtime (`python3.12`).  The handler code should run
unchanged, but it is worth confirming that `boto3` calls behave the same on
the newer bundled SDK.

## 2. Make the tag keys and name format configurable

The tag keys `project` and `environment`, and the resulting
`<project>-<environment>-<instance_id>` format, are hardcoded in the Lambda
source.  Adopting this project with a different tagging standard currently
means editing the template.

Expose them as CloudFormation `Parameters` (e.g. `ProjectTagKey`,
`EnvironmentTagKey`, `NameFormat`) with the present values as defaults, and
pass them into the function via environment variables.

## 3. Add unit tests for the Lambda handler

The handler has no tests.  It should not be extracted to a separate source
file, because the inline `ZipFile` definition is what keeps the template
deployable in a single command with no packaging step or S3 staging bucket.

Instead, have the tests read the handler out of the template: parse
`cfn-template.yml`, pull
`Resources.LambdaFunction.Properties.Code.ZipFile`, and `exec` it into a
namespace with `boto3` mocked.  That keeps one source of truth and still
gets real coverage.  `example-payloads/cloudwatch-event.json` is ready-made
fixture data.

Cases worth covering: missing `project`/`environment` tags, a `Name` tag
that is already set, instance-not-found, and the 255-character truncation
in `build_name`.

## 4. Refresh the region list

The `REGIONS` list in `Taskfile.yml` (carried over from the old Ansible
vars) predates a number of current regions -- `eu-north-1`, `eu-south-1`,
`ap-east-1`, `me-south-1`, `af-south-1` and others are missing.

The original reason for maintaining a curated list was that CloudWatch
Events was not available everywhere.  That constraint no longer holds:
EventBridge is in every commercial region.  Either refresh the list or
document it plainly as a user-editable filter.

## 5. Add CI

There is no CI.  A GitHub Actions workflow running `cfn-lint` on the
template -- plus the tests from item 3 once they exist -- would have caught
both the dead Python runtime and the Ansible breakage that motivated
removing Ansible.

A `.gitignore` is also missing.

## 6. Add an architecture diagram to the README

A small diagram of the flow (ASG launch event -> EventBridge rule -> Lambda
-> `ec2:CreateTags`) would let a reader understand the project in a few
seconds.

The README typo and the stale CloudWatch Events naming were fixed when
Ansible was removed; the diagram is what remains.

## 7. Tighten the Lambda's `ec2:CreateTags` permission

`AllowEC2NamingPolicy` grants `ec2:CreateTags` on `Resource: "*"`.  This is
defensible -- concentrating the permission in one audited function instead
of granting it to every instance profile is the entire point of the project
-- but it can be tightened further with a condition restricting tag
creation to the `Name` key, e.g. `aws:RequestTag` / `aws:TagKeys`.

Worth verifying against the EC2 condition keys that `CreateTags` actually
supports before committing to a policy shape.

## 8. Rename the project to `christen`

`aws-name-asg-instances` is a mouthful.  Rename to `christen` -- it names
newborn instances, it is short, and it works as a stack name.

Touches: the repository name, the README title, `PROJECT_NAME` in
`Taskfile.yml` (which feeds the default stack name), and possibly
`cfn-template.yml` -> `christen.yml`.  Note that renaming `PROJECT_NAME`
changes the default stack name, so existing deployments would need either
the old value passed explicitly or a deliberate stack replacement.
