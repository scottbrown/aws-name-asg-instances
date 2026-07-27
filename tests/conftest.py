"""Shared fixtures for the Lambda handler tests.

The handler lives inline in the CloudFormation template rather than in its
own .py file, so that the template stays deployable in a single command
with no packaging step.  These fixtures read it back out of the template
and load it with `boto3` mocked, which keeps the template as the single
source of truth while still allowing real tests.
"""

import json
import pathlib
import sys
import types
from unittest.mock import MagicMock

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_handler import CloudFormationLoader, extract_handler  # noqa: E402

TEMPLATE = REPO_ROOT / "cfn-template.yml"
PAYLOAD = REPO_ROOT / "example-payloads" / "cloudwatch-event.json"

# The instance ID used throughout, matching the checked-in example payload.
INSTANCE_ID = "i-0123456789abcdef0"

DEFAULT_TAGS = [
    {"Key": "project", "Value": "donny"},
    {"Key": "environment", "Value": "staging"},
]


@pytest.fixture(scope="session")
def handler_source():
    """The Lambda source, read out of the CloudFormation template."""
    return extract_handler(TEMPLATE)


@pytest.fixture(scope="session")
def template():
    """The parsed CloudFormation template.

    Intrinsics are flattened by the loader, so a `!Ref Foo` reads back as
    the string "Foo" -- enough to assert what a property points at.
    """
    return yaml.load(TEMPLATE.read_text(), Loader=CloudFormationLoader)


@pytest.fixture
def instance_id():
    """The instance ID carried by the example payload."""
    return INSTANCE_ID


@pytest.fixture
def event():
    """A real AutoScaling launch event, as EventBridge delivers it."""
    return json.loads(PAYLOAD.read_text())


@pytest.fixture
def load_handler(handler_source, monkeypatch):
    """Return a factory that loads the handler with a mocked EC2 client.

    The factory returns a (module, ec2) pair.  `ec2` is the mock the
    handler will call, pre-loaded with responses describing a single
    existing instance carrying `tags`, so individual tests only need to
    override the part they care about.  `env` sets the environment
    variables the stack normally supplies from its parameters.
    """

    def _load(tags=None, env=None):
        # The handler reads its configuration from the environment at import
        # time, so this has to be set before the source is executed.
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)

        ec2 = MagicMock()
        ec2.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceId": INSTANCE_ID}]
        }
        ec2.describe_tags.return_value = {
            "Tags": DEFAULT_TAGS if tags is None else tags
        }
        ec2.create_tags.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        # The handler calls boto3.client('ec2') at import time, so boto3 has
        # to be mocked before the source is executed.
        fake_boto3 = types.ModuleType("boto3")
        fake_boto3.client = lambda service: ec2
        monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

        module = types.ModuleType("index")
        exec(compile(handler_source, "cfn-template.yml:ZipFile", "exec"), module.__dict__)
        return module, ec2

    return _load
