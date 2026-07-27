#!/usr/bin/env python3
"""Check that the Lambda handler embedded in the template is valid Python.

The handler is defined inline in the CloudFormation template, under
Resources.LambdaFunction.Properties.Code.ZipFile, so that the template
stays deployable in a single command with no packaging step.  The cost of
that choice is that nothing type-checks or syntax-checks the code the way
it would a normal .py file -- and cfn-lint does not look inside the
ZipFile block, so a syntax error there passes its checks and only fails at
deploy time.

This script closes that gap.  It is also the extraction mechanism a real
test suite should build on: parse the template, pull the source out, and
exercise it with boto3 mocked.

Usage: python3 scripts/check_handler.py [template.yml]
"""

import pathlib
import sys

import yaml


class CloudFormationLoader(yaml.SafeLoader):
    """A YAML loader that tolerates CloudFormation's short-form tags.

    We only care about the handler source, so intrinsics such as !Sub and
    !GetAtt are resolved to something inert rather than interpreted.
    """


def _construct_cfn_tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return node.value
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


CloudFormationLoader.add_multi_constructor("!", _construct_cfn_tag)

HANDLER_PATH = ("Resources", "LambdaFunction", "Properties", "Code", "ZipFile")


def extract_handler(template_path):
    """Return the inline Lambda source from a CloudFormation template."""
    document = yaml.load(template_path.read_text(), Loader=CloudFormationLoader)

    node = document
    for key in HANDLER_PATH:
        if not isinstance(node, dict) or key not in node:
            raise SystemExit(
                "Could not find the handler at {} in {}".format(
                    ".".join(HANDLER_PATH), template_path
                )
            )
        node = node[key]

    if not isinstance(node, str):
        raise SystemExit("Handler source is not a string in {}".format(template_path))

    return node


def main(argv):
    template_path = pathlib.Path(argv[1] if len(argv) > 1 else "cfn-template.yml")
    if not template_path.is_file():
        raise SystemExit("No such template: {}".format(template_path))

    source = extract_handler(template_path)

    try:
        compile(source, "{}:ZipFile".format(template_path), "exec")
    except SyntaxError as error:
        print(
            "FAIL: inline handler is not valid Python\n"
            "  {}\n"
            "  line {} of the ZipFile block: {}".format(
                error.msg, error.lineno, (error.text or "").rstrip()
            ),
            file=sys.stderr,
        )
        return 1

    print(
        "OK: inline handler in {} is valid Python "
        "({} lines)".format(template_path, len(source.splitlines()))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
