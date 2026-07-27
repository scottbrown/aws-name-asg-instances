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
