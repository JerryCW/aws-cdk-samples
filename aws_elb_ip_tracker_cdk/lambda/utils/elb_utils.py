"""
Utility functions for working with Elastic Load Balancers (ELBs).
"""
import boto3
import logging
from utils.config import (
    ELB_TYPE_APP, 
    ELB_TYPE_NET, 
    ELB_TYPE_CLASSIC, 
    ELB_TYPE_UNKNOWN, 
    ELB_NAME_UNKNOWN
)

# Configure logging
logger = logging.getLogger()

# Initialize boto3 clients
elb_client = boto3.client('elb')
elbv2_client = boto3.client('elbv2')

def extract_elb_info(description):
    """
    Extract ELB name and type from ENI description.
    CLB format: 'ELB <n>'
    ALB format: 'ELB app/<n>/<id>'
    NLB format: 'ELB net/<n>/<id>'
    
    Args:
        description (str): The network interface description
        
    Returns:
        tuple: (elb_name, elb_type) where elb_type is 'app', 'net', or 'classic'
    """
    elb_name = ELB_NAME_UNKNOWN
    elb_type = ELB_TYPE_UNKNOWN
    
    if description:
        if description.startswith('ELB '):
            # Remove the 'ELB ' prefix
            elb_part = description[4:]
            
            # Handle ALB format
            if 'app/' in elb_part:
                parts = elb_part.split('app/')[1].split('/')
                if len(parts) >= 2:
                    elb_name = parts[0]
                    elb_type = ELB_TYPE_APP
            
            # Handle NLB format
            elif 'net/' in elb_part:
                parts = elb_part.split('net/')[1].split('/')
                if len(parts) >= 2:
                    elb_name = parts[0]
                    elb_type = ELB_TYPE_NET
            
            # Handle CLB format
            elif ' ' in elb_part:
                elb_name = elb_part.split(' ')[0]
                elb_type = ELB_TYPE_CLASSIC
            
            # Simple case - just the name after "ELB"
            else:
                elb_name = elb_part
                elb_type = ELB_TYPE_CLASSIC
    
    return elb_name, elb_type

def get_elb_arn(elb_name, elb_type=ELB_TYPE_UNKNOWN):
    """
    Get the ARN of an ELB based on its name and type.
    
    Args:
        elb_name (str): The name of the ELB
        elb_type (str): The type of ELB ('app', 'net', or 'classic')
        
    Returns:
        str: The ARN of the ELB or None if not found
    """
    try:
        if elb_name == ELB_NAME_UNKNOWN:
            return None
            
        # Try to find the load balancer in ALB/NLB (v2)
        try:
            response = elbv2_client.describe_load_balancers(Names=[elb_name])
            if response.get('LoadBalancers'):
                return response['LoadBalancers'][0].get('LoadBalancerArn')
        except Exception as e:
            logger.info(f"ELB {elb_name} not found in elbv2: {str(e)}")
        
        # Try to find the load balancer in CLB (v1)
        try:
            response = elb_client.describe_load_balancers(LoadBalancerNames=[elb_name])
            if response.get('LoadBalancerDescriptions'):
                # Classic ELBs don't have ARNs in the same way, so we construct one
                region = boto3.session.Session().region_name
                account_id = boto3.client('sts').get_caller_identity().get('Account')
                return f"arn:aws:elasticloadbalancing:{region}:{account_id}:loadbalancer/{elb_name}"
        except Exception as e:
            logger.info(f"ELB {elb_name} not found in classic elb: {str(e)}")
            
        logger.warning(f"Could not find ARN for ELB {elb_name}")
        return None
    except Exception as e:
        logger.error(f"Error getting ELB ARN: {str(e)}")
        return None
