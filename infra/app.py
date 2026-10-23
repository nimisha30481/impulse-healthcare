#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.impulse_stack import ImpulseStack

app = cdk.App()
env_name = app.node.try_get_context("env") or "dev"
if env_name == "prod" and app.node.try_get_context("approvedProd") != "true":
    raise SystemExit("Production deploys need explicit approval: add -c approvedProd=true")

ImpulseStack(
    app,
    f"Impulse-{env_name}",
    env_name=env_name,
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
                        region=app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION", "ap-south-1")),
    tags={"project": "impulse", "environment": env_name, "data-classification": "health"},
)
app.synth()
