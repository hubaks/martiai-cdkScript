#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_script.cdk_script_stack import CdkScriptStack


app = cdk.App()
env_name = app.node.try_get_context("env") or "dev"
project_name = app.node.try_get_context("project") or "marti"
CdkScriptStack(app, f"{project_name}-{env_name}-CdkScriptStack",
    env_name=env_name,
    env=cdk.Environment(
        account=os.getenv('123456789012'),
        region=os.getenv('us-east-1')
    )
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()
