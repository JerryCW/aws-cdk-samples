#!/usr/bin/env python3
from aws_cdk import App
from stacks.elb_ip_tracker_stack import ElbIpTrackerStack

app = App()
ElbIpTrackerStack(app, "ElbIpTrackerStack")
app.synth()