"""
Utility functions for working with EC2 network interfaces.
"""
import boto3
import json
import logging
from datetime import datetime
from utils.elb_utils import extract_elb_info, get_elb_arn
from utils.config import EVENT_TYPE_INITIAL_SCAN

# Configure logging
logger = logging.getLogger()

# Initialize boto3 clients
ec2_client = boto3.client('ec2')

def get_network_interface_details(eni_id):
    """
    Get details about a network interface, including its public IP and associated ELB.
    
    Args:
        eni_id (str): Network interface ID
        
    Returns:
        dict: Network interface details or None if not found
    """
    try:
        response = ec2_client.describe_network_interfaces(
            NetworkInterfaceIds=[eni_id]
        )
        
        if not response.get('NetworkInterfaces'):
            logger.warning(f"No network interface found with ID {eni_id}")
            return None
        
        eni = response['NetworkInterfaces'][0]
        
        # Extract relevant information
        description = eni.get('Description', '')
        private_ip = eni.get('PrivateIpAddress')
        
        # Extract ELB name and type from description
        elb_name, elb_type = extract_elb_info(description)
        
        # Get ELB ARN
        elb_arn = None
        if elb_name != 'unknown-elb':
            elb_arn = get_elb_arn(elb_name, elb_type)
            logger.info(f"Found ELB ARN: {elb_arn}")
        
        # Extract public IP if available
        public_ip = None
        if eni.get('Association'):
            public_ip = eni['Association'].get('PublicIp')
            if public_ip:
                logger.info(f"Found public IP: {public_ip}")
            else:
                logger.info(f"Association exists but no public IP found yet for ENI {eni_id}")
        else:
            logger.info(f"No association with public IP for ENI {eni_id} yet")
        
        # Get availability zone and subnet information
        az = eni.get('AvailabilityZone')
        subnet_id = eni.get('SubnetId')
        vpc_id = eni.get('VpcId')
        
        # Get security groups
        security_groups = [sg.get('GroupId') for sg in eni.get('Groups', [])]
        
        return {
            'eni_id': eni_id,
            'public_ip': public_ip,
            'private_ip': private_ip,
            'elb_name': elb_name,
            'elb_arn': elb_arn,
            'description': description,
            'availability_zone': az,
            'subnet_id': subnet_id,
            'vpc_id': vpc_id,
            'security_groups': security_groups
        }
    except boto3.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        logger.error(f"Error getting network interface details: {error_code} - {str(e)}")
        
        if error_code == 'InvalidNetworkInterfaceID.NotFound':
            logger.info(f"Network interface {eni_id} no longer exists (likely deleted)")
            return {
                'eni_id': eni_id,
                'status': 'deleted',
                'error': str(e)
            }
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting network interface details: {str(e)}")
        return None

def scan_existing_elb_interfaces(get_details_func, lambda_timestamp=None):
    """
    Scan all existing network interfaces to find ELB interfaces.
    
    Args:
        get_details_func (callable): Function to get network interface details
        lambda_timestamp (str): Optional timestamp when Lambda was invoked
        
    Returns:
        dict: Response with status code and results
    """
    # If no lambda timestamp provided, use current time
    if lambda_timestamp is None:
        lambda_timestamp = datetime.utcnow().isoformat()
        
    logger.info("Starting initial scan of existing ELB network interfaces")
    
    # List to store all ELB network interfaces
    elb_interfaces = []
    
    # Use pagination to get all network interfaces
    paginator = ec2_client.get_paginator('describe_network_interfaces')
    
    # We'll use a filter to only get interfaces with descriptions that start with "ELB"
    try:
        for page in paginator.paginate(Filters=[{'Name': 'description', 'Values': ['ELB*']}]):
            for eni in page.get('NetworkInterfaces', []):
                eni_id = eni.get('NetworkInterfaceId')
                description = eni.get('Description', '')
                
                logger.info(f"Found ELB network interface: {eni_id} with description: {description}")
                elb_interfaces.append(eni_id)
                
                # Process each interface using the provided function
                eni_details = get_details_func(eni_id)
                
                if eni_details:
                    # Get current timestamp for the event
                    event_timestamp = datetime.utcnow().isoformat()
                    
                    # Create a composite ID using eni_id, action_type, and timestamp
                    from utils.dynamodb_utils import create_composite_id, store_in_dynamodb
                    
                    composite_id = create_composite_id(eni_id, EVENT_TYPE_INITIAL_SCAN, event_timestamp)
                    
                    # Prepare data for DynamoDB
                    item = {
                        'id': composite_id,  # Use composite ID instead of random UUID
                        'event_timestamp': event_timestamp,
                        'lambda_timestamp': lambda_timestamp,
                        'action_type': EVENT_TYPE_INITIAL_SCAN,
                        'eni_id': eni_id,
                        'elb_name': eni_details.get('elb_name', 'unknown-elb')
                    }
                    
                    # Add ENI details
                    for key, value in eni_details.items():
                        if key != 'eni_id':  # Avoid duplicate
                            item[key] = value
                    
                    # Store in DynamoDB
                    store_in_dynamodb(item)
        
        logger.info(f"Initial scan complete. Found {len(elb_interfaces)} ELB network interfaces.")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f"Initial scan complete. Found {len(elb_interfaces)} ELB network interfaces.",
                'interfaces': elb_interfaces,
                'lambda_timestamp': lambda_timestamp
            }, default=str)
        }
    except Exception as e:
        logger.error(f"Error during initial scan: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error during initial scan: {str(e)}')
        }
