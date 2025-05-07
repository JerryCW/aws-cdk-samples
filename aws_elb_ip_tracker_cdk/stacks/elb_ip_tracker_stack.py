from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
    CfnOutput,
    CustomResource,
    custom_resources as cr
)
from constructs import Construct
import time

class ElbIpTrackerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table to store ELB network interface information
        table = dynamodb.Table(
            self, "ELBNetworkInterfaces",
            table_name="elb-network-interfaces",  # Specific table name
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,  # Retain the table on stack deletion
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            )
        )
        
        # Add a Global Secondary Index on eni_id for efficient queries
        table.add_global_secondary_index(
            index_name="eni-id-index",
            partition_key=dynamodb.Attribute(
                name="eni_id",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Create Lambda function to process network interface events
        lambda_function = lambda_.Function(
            self, "ELBIpTrackerFunction",
            function_name="fn-elb-ip-tracker",  # Specific function name
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("lambda"),
            timeout=Duration.seconds(300),
            memory_size=256,
            environment={
                "DYNAMODB_TABLE_NAME": table.table_name,
                "INITIAL_SCAN": "true"  # Used as a fallback if DynamoDB check fails
            }
        )

        # Grant Lambda permissions to access DynamoDB
        table.grant_read_write_data(lambda_function)

        # Grant Lambda permissions to describe EC2 network interfaces and ELBs
        lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeNetworkInterfaces",
                    "elasticloadbalancing:DescribeLoadBalancers",
                    "elasticloadbalancing:DescribeLoadBalancersV2"
                ],
                resources=["*"]
            )
        )

        # Create CloudWatch Events rule to trigger Lambda on network interface changes via CloudTrail
        rule = events.Rule(
            self, "NetworkInterfaceEventsRule",
            event_pattern=events.EventPattern(
                source=["aws.ec2"],
                detail_type=["AWS API Call via CloudTrail"],
                detail={
                    "eventSource": ["ec2.amazonaws.com"],
                    "eventName": [
                        "CreateNetworkInterface",
                        "DeleteNetworkInterface",
                        "ModifyNetworkInterfaceAttribute"
                    ],
                    "userAgent": ["elasticloadbalancing.amazonaws.com"]
                }
            )
        )

        # Add Lambda as target for the rule
        rule.add_target(targets.LambdaFunction(lambda_function))
        
        # Create a custom resource that will invoke the Lambda function once during deployment
        # This is better than a scheduled event because it only runs once during deployment
        initial_scan_provider = cr.Provider(
            self, "InitialScanProvider",
            on_event_handler=lambda_function,
            # Define a custom function name for the provider's Lambda function
            provider_function_name="fn-elb-ip-tracker-initializer"
        )
        
        # Create the custom resource that will trigger the initial scan
        CustomResource(
            self, "InitialScanTrigger",
            service_token=initial_scan_provider.service_token,
            properties={
                "trigger": "initial-scan",  # This will be passed to the Lambda as part of the event
                "timestamp": str(int(time.time()))  # Current timestamp to ensure uniqueness on each deployment
            }
        )
        
        # Output the resources created
        CfnOutput(
            self, "LambdaFunctionName",
            description="Name of the Lambda function",
            value=lambda_function.function_name
        )
        
        CfnOutput(
            self, "DynamoDBTableName",
            description="Name of the DynamoDB table",
            value=table.table_name
        )
