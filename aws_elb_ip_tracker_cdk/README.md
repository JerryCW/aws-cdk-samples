# AWS ELB IP Tracker CDK Project

This CDK project deploys the AWS ELB IP Tracker solution, which monitors Elastic Load Balancer (ELB) network interfaces and their associated IP addresses, storing the information in DynamoDB for monitoring and auditing purposes.

## Solution Overview

The AWS ELB IP Tracker solution helps you:

- Track all network interfaces associated with your Elastic Load Balancers
- Monitor IP address changes in real-time
- Maintain a historical record of ELB IP addresses for auditing and security purposes
- Simplify network security group management by having up-to-date ELB IP information

## Architecture

![Architecture Diagram](https://via.placeholder.com/800x400?text=ELB+IP+Tracker+Architecture)

The solution uses the following components:
- **CloudTrail** - Captures API calls related to network interface changes
- **CloudWatch Events** - Triggers Lambda function when ELB network interfaces are created, modified, or deleted
- **Lambda Function** - Processes events and extracts ELB information
- **DynamoDB** - Stores ELB network interface data for querying and analysis

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.9 or higher
- Node.js 14.x or higher (required by CDK)
- AWS CDK Toolkit installed (`npm install -g aws-cdk`)

## Project Structure

```
aws_elb_ip_tracker_cdk/
├── app.py                  # CDK application entry point
├── cdk.json                # CDK configuration
├── requirements.txt        # Python dependencies
├── stacks/
│   └── elb_ip_tracker_stack.py  # Main CDK stack definition
└── lambda/
    ├── index.py            # Lambda function main handler
    └── utils/              # Lambda utility modules
        ├── elb_utils.py    # ELB-related functions
        ├── network_utils.py # Network interface functions
        ├── dynamodb_utils.py # DynamoDB operations
        └── ...             # Other utility modules
```

## Deployment Instructions

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Bootstrap the CDK environment (if not already done):

```bash
cdk bootstrap
```

4. Deploy the stack:

```bash
cdk deploy
```

5. To view the CloudFormation outputs (DynamoDB table name, Lambda function name):

```bash
cdk deploy --outputs-file outputs.json
```

## Resources Created

The CDK stack creates the following resources:

1. **DynamoDB Table**: 
   - Table name: `elb-network-interfaces`
   - Stores information about ELB network interfaces
   - Uses point-in-time recovery for data protection
   - Includes a GSI on `eni_id` for efficient queries

2. **Lambda Function**: 
   - Function name: `fn-elb-ip-tracker`
   - Processes EC2 network interface events and extracts ELB information
   - Performs initial scan of existing ELB interfaces on first deployment
   - Runtime: Python 3.12
   - Memory: 256MB
   - Timeout: 300 seconds

3. **IAM Role**: 
   - Grants the Lambda function permissions to:
     - Access DynamoDB table
     - Describe EC2 network interfaces
     - Describe ELBs (both Classic and Application/Network Load Balancers)

4. **CloudWatch Events Rule**: 
   - Triggers the Lambda function when network interfaces are created, modified, or deleted
   - Filters for events from the ELB service

5. **Custom Resource**: 
   - Triggers an initial scan of existing ELB interfaces during deployment

## How It Works

1. When an ELB is created or modified, AWS creates or updates network interfaces
2. CloudTrail captures these API calls
3. CloudWatch Events triggers the Lambda function
4. The Lambda function:
   - Extracts network interface details
   - Identifies the associated ELB
   - Stores the information in DynamoDB
5. On initial deployment, a custom resource triggers a scan of all existing ELB interfaces

## Querying the Data

You can query the DynamoDB table to find information about your ELB network interfaces:

```bash
# Get all entries for a specific ELB
aws dynamodb query \
  --table-name elb-network-interfaces \
  --key-condition-expression "elb_name = :name" \
  --expression-attribute-values '{":name":{"S":"my-load-balancer"}}'

# Get details for a specific network interface
aws dynamodb query \
  --table-name elb-network-interfaces \
  --index-name eni-id-index \
  --key-condition-expression "eni_id = :eni" \
  --expression-attribute-values '{":eni":{"S":"eni-0123456789abcdef0"}}'
```

## Customization

You can customize the deployment by modifying the `elb_ip_tracker_stack.py` file:

- Change the DynamoDB table name
- Adjust the Lambda function's timeout or memory allocation
- Modify the IAM permissions
- Add additional CloudWatch Events rules

## Cleanup

To remove all resources created by this CDK stack:

```bash
cdk destroy
```

Note: The DynamoDB table is configured with `RemovalPolicy.RETAIN` to prevent accidental data loss. To delete the table after destroying the stack, use the AWS Management Console or AWS CLI.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
