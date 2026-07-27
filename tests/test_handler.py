"""Tests for the Lambda handler embedded in cfn-template.yml.

The handler deliberately swallows its own LambdaException and logs it
rather than raising, so that a single unnameable instance does not turn
into an EventBridge retry storm.  That means the assertion for a rejected
case is "no tag was written", not "an exception was raised".
"""

def tag_written(ec2):
    """The Name tag value the handler wrote, or None if it wrote nothing."""
    if not ec2.create_tags.called:
        return None
    tags = ec2.create_tags.call_args.kwargs["Tags"]
    return next(tag["Value"] for tag in tags if tag["Key"] == "Name")


class TestNaming:
    def test_names_instance_from_its_tags(self, load_handler, event, instance_id):
        module, ec2 = load_handler()

        module.lambda_handler(event, None)

        assert tag_written(ec2) == "donny-staging-0123456789abcdef0"
        assert ec2.create_tags.call_args.kwargs["Resources"] == [instance_id]

    def test_instance_id_loses_its_i_prefix(self, load_handler):
        module, _ = load_handler()

        assert module.build_name("proj", "env", "i-abc123") == "proj-env-abc123"

    def test_name_is_truncated_to_the_255_char_tag_limit(self, load_handler):
        module, _ = load_handler()

        name = module.build_name("p" * 300, "e" * 300, "i-abc123")

        assert len(name) == 255


class TestRefusesToTag:
    def test_when_a_name_is_already_set(self, load_handler, event):
        module, ec2 = load_handler(
            tags=[
                {"Key": "project", "Value": "donny"},
                {"Key": "environment", "Value": "staging"},
                {"Key": "Name", "Value": "already-named"},
            ]
        )

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None

    def test_when_the_project_tag_is_missing(self, load_handler, event):
        module, ec2 = load_handler(tags=[{"Key": "environment", "Value": "staging"}])

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None

    def test_when_the_environment_tag_is_missing(self, load_handler, event):
        module, ec2 = load_handler(tags=[{"Key": "project", "Value": "donny"}])

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None

    def test_when_a_required_tag_is_present_but_empty(self, load_handler, event):
        module, ec2 = load_handler(
            tags=[
                {"Key": "project", "Value": "donny"},
                {"Key": "environment", "Value": ""},
            ]
        )

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None

    def test_when_an_empty_name_tag_is_present(self, load_handler, event):
        """An empty Name is not a real name, so the instance should be named."""
        module, ec2 = load_handler(
            tags=[
                {"Key": "project", "Value": "donny"},
                {"Key": "environment", "Value": "staging"},
                {"Key": "Name", "Value": ""},
            ]
        )

        module.lambda_handler(event, None)

        assert tag_written(ec2) == "donny-staging-0123456789abcdef0"

    def test_when_the_instance_does_not_exist(self, load_handler, event):
        module, ec2 = load_handler()
        ec2.describe_instance_status.return_value = {"InstanceStatuses": []}

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None

    def test_when_more_than_one_instance_comes_back(self, load_handler, event, instance_id):
        """Ambiguity should abort rather than risk naming the wrong instance."""
        module, ec2 = load_handler()
        ec2.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceId": instance_id}, {"InstanceId": "i-other"}]
        }

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None

    def test_when_the_describe_payload_shape_changes(self, load_handler, event):
        module, ec2 = load_handler()
        ec2.describe_instance_status.return_value = {}

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None

    def test_when_the_tags_payload_shape_changes(self, load_handler, event):
        module, ec2 = load_handler()
        ec2.describe_tags.return_value = {}

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None


class TestConfiguration:
    """The tag keys and name format come from the stack's parameters, which
    reach the handler as environment variables."""

    def test_it_reads_tags_under_configured_keys(self, load_handler, event):
        module, ec2 = load_handler(
            tags=[
                {"Key": "service", "Value": "billing"},
                {"Key": "stage", "Value": "prod"},
            ],
            env={"PROJECT_TAG_KEY": "service", "ENVIRONMENT_TAG_KEY": "stage"},
        )

        module.lambda_handler(event, None)

        assert tag_written(ec2) == "billing-prod-0123456789abcdef0"

    def test_the_default_keys_no_longer_apply_once_overridden(
        self, load_handler, event
    ):
        module, ec2 = load_handler(
            tags=[
                {"Key": "project", "Value": "donny"},
                {"Key": "environment", "Value": "staging"},
            ],
            env={"PROJECT_TAG_KEY": "service", "ENVIRONMENT_TAG_KEY": "stage"},
        )

        module.lambda_handler(event, None)

        assert tag_written(ec2) is None

    def test_it_honours_a_custom_name_format(self, load_handler, event):
        module, ec2 = load_handler(
            env={"NAME_FORMAT": "{environment}.{project}.{instance_id}"}
        )

        module.lambda_handler(event, None)

        assert tag_written(ec2) == "staging.donny.0123456789abcdef0"

    def test_a_format_may_drop_placeholders(self, load_handler, event):
        module, ec2 = load_handler(env={"NAME_FORMAT": "{project}-{instance_id}"})

        module.lambda_handler(event, None)

        assert tag_written(ec2) == "donny-0123456789abcdef0"

    def test_a_custom_format_is_still_truncated(self, load_handler, event):
        module, _ = load_handler(env={"NAME_FORMAT": "{project}" * 100})

        assert len(module.build_name("p" * 10, "e", "i-abc")) == 255

    def test_an_unknown_placeholder_refuses_rather_than_crashing(
        self, load_handler, event
    ):
        module, ec2 = load_handler(env={"NAME_FORMAT": "{project}-{team}"})

        module.lambda_handler(event, None)  # must not raise

        assert tag_written(ec2) is None

    def test_a_positional_placeholder_refuses_rather_than_crashing(
        self, load_handler, event
    ):
        module, ec2 = load_handler(env={"NAME_FORMAT": "{project}-{}"})

        module.lambda_handler(event, None)  # must not raise

        assert tag_written(ec2) is None


class TestTemplateWiring:
    """Guards against the template and the handler drifting apart.  The
    handler carries its own fallback defaults so it stays runnable in
    isolation, which means a parameter default could change without the
    tests noticing unless something checks the two agree."""

    def test_parameter_defaults_match_the_handler_fallbacks(
        self, load_handler, template
    ):
        module, _ = load_handler()
        parameters = template["Parameters"]

        assert parameters["ProjectTagKey"]["Default"] == module.PROJECT_TAG_KEY
        assert parameters["EnvironmentTagKey"]["Default"] == module.ENVIRONMENT_TAG_KEY
        assert parameters["NameFormat"]["Default"] == module.NAME_FORMAT

    def test_each_parameter_reaches_the_function(self, template):
        variables = template["Resources"]["LambdaFunction"]["Properties"][
            "Environment"
        ]["Variables"]

        assert variables == {
            "PROJECT_TAG_KEY": "ProjectTagKey",
            "ENVIRONMENT_TAG_KEY": "EnvironmentTagKey",
            "NAME_FORMAT": "NameFormat",
        }


class TestNamingPolicy:
    """The whole point of the project is that nothing else gets broad
    ec2:CreateTags. That argument only holds if the function's own grant is
    narrow, so the policy shape is worth pinning."""

    @staticmethod
    def statements(template):
        return template["Resources"]["AllowEC2NamingPolicy"]["Properties"][
            "PolicyDocument"
        ]["Statement"]

    @staticmethod
    def actions(statement):
        action = statement["Action"]
        return [action] if isinstance(action, str) else action

    def write_statement(self, template):
        matching = [
            s for s in self.statements(template) if "ec2:CreateTags" in self.actions(s)
        ]
        assert len(matching) == 1, "expected exactly one statement granting CreateTags"
        return matching[0]

    def test_tag_writing_is_confined_to_the_name_key(self, template):
        condition = self.write_statement(template)["Condition"]

        assert condition["ForAllValues:StringEquals"]["aws:TagKeys"] == ["Name"]

    def test_tag_writing_is_confined_to_instances(self, template):
        resource = self.write_statement(template)["Resource"]

        assert resource != "*"
        assert resource.endswith(":instance/*")

    def test_tag_writing_is_confined_to_this_account(self, template):
        assert "${AWS::AccountId}" in self.write_statement(template)["Resource"]

    def test_the_broad_statement_grants_only_reads(self, template):
        for statement in self.statements(template):
            if statement.get("Resource") == "*":
                assert all(
                    action.startswith("ec2:Describe")
                    for action in self.actions(statement)
                ), "a wildcard-resource statement grants something other than reads"


class TestFailureIsContained:
    def test_a_rejected_instance_does_not_raise(self, load_handler, event):
        """EventBridge retries on an unhandled exception, so the handler must
        absorb the cases it deliberately refuses."""
        module, ec2 = load_handler(tags=[])

        module.lambda_handler(event, None)  # must not raise

        assert tag_written(ec2) is None

    def test_it_reads_the_instance_id_from_the_event(self, load_handler, event, instance_id):
        module, ec2 = load_handler()

        module.lambda_handler(event, None)

        ec2.describe_instance_status.assert_called_once_with(
            InstanceIds=[instance_id], IncludeAllInstances=True
        )
