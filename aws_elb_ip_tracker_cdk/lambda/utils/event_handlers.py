"""
Event handler functions for different types of events.
"""
import json
import logging
from datetime import datetime
from utils.network_utils import get_network_interface_details
from utils.elb_utils import extract_elb_info
from utils.dynamodb_utils import (
    store_in_dynamodb, 
    create_composite_id, 
    get_eni_historical_data,
    check_recent_delete_event
)
from utils.config import EVENT_TYPE_DELETE, EVENT_TYPE_CREATE

# Configure logging
logger = logging.getLogger()

def handle_delete_event(eni_id, event_timestamp, lambda_timestamp):
    """
    Handle a network interface delete event.
    For delete events, we need special handling because the ENI might already be deleted,
    making it impossible to get its current details.
    
    Args:
        eni_id (str): Network interface ID
        event_timestamp (str): Timestamp of the event
        lambda_timestamp (str): Timestamp when Lambda was invoked
        
    Returns:
        dict: Response with status code and results
    """
    # Check if we've already processed a delete event for this ENI recently
    if check_recent_delete_event(eni_id):
        logger.info(f"Skipping duplicate delete event for ENI {eni_id}")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f"Skipped duplicate delete event for ENI {eni_id}",
                'eni_id': eni_id
            })
        }
    
    # Try to get current details (might fail if ENI is already deleted)
    eni_details = get_network_interface_details(eni_id)
    
    # If we couldn't get details or the ENI is marked as deleted
    if eni_details is None or eni_details.get('status') == 'deleted':
        logger.info(f"ENI {eni_id} already deleted, retrieving historical data")
        
        # Try to get historical data
        historical_data = get_eni_historical_data(eni_id)
        
        if historical_data:
            # Create a new details dictionary with historical data
            eni_details = {
                'eni_id': eni_id,
                'status': 'deleted',
                'public_ip': historical_data.get('public_ip'),
                'private_ip': historical_data.get('private_ip'),
                'elb_name': historical_data.get('elb_name'),
                'elb_arn': historical_data.get('elb_arn'),
                'description': historical_data.get('description'),
                'availability_zone': historical_data.get('availability_zone'),
                'subnet_id': historical_data.get('subnet_id'),
                'vpc_id': historical_data.get('vpc_id'),
                'security_groups': historical_data.get('security_groups'),
                'data_source': 'historical'
            }
            logger.info(f"Successfully retrieved historical data for ENI {eni_id}")
        else:
            # If no historical data, create minimal details
            eni_details = {
                'eni_id': eni_id,
                'status': 'deleted',
                'data_source': 'minimal',
                'error': 'ENI already deleted and no historical data found'
            }
            logger.warning(f"No historical data found for ENI {eni_id}")
    
    # Create composite ID for DynamoDB
    composite_id = create_composite_id(eni_id, EVENT_TYPE_DELETE, event_timestamp)
    
    # Prepare item for DynamoDB
    item = {
        'id': composite_id,
        'event_timestamp': event_timestamp,
        'lambda_timestamp': lambda_timestamp,
        'action_type': EVENT_TYPE_DELETE,
        'eni_id': eni_id
    }
    
    # Add ENI details if available
    if eni_details:
        for key, value in eni_details.items():
            if key != 'eni_id':  # Avoid duplicate
                item[key] = value
    
    # Store in DynamoDB
    store_in_dynamodb(item)
    
    # Return response
    result = {
        'event_timestamp': event_timestamp,
        'lambda_timestamp': lambda_timestamp,
        'action_type': EVENT_TYPE_DELETE,
        'eni_id': eni_id,
        'elb_name': eni_details.get('elb_name', 'unknown-elb'),
        'elb_arn': eni_details.get('elb_arn'),
        'dynamodb_id': composite_id,
        'data_source': eni_details.get('data_source', 'direct')
    }
    
    return {
        'statusCode': 200,
        'body': json.dumps(result, default=str)
    }

def handle_create_or_modify_event(eni_id, action_type, description, event_timestamp, lambda_timestamp, get_details_func):
    """
    Handle a network interface create or modify event.
    
    Args:
        eni_id (str): Network interface ID
        action_type (str): Action type (add or modify)
        description (str): Network interface description
        event_timestamp (str): Timestamp of the event
        lambda_timestamp (str): Timestamp when Lambda was invoked
        get_details_func (callable): Function to get network interface details
        
    Returns:
        dict: Response with status code and results
    """
    # Extract ELB name and type from description
    elb_name, elb_type = extract_elb_info(description)
    logger.info(f"ELB Name: {elb_name}, Type: {elb_type}")
    
    # Get network interface details
    # For create events, use the retry version to wait for public IP
    eni_details = get_details_func(eni_id)
    
    # Create composite ID for DynamoDB
    composite_id = create_composite_id(eni_id, action_type, event_timestamp)
    
    # Prepare item for DynamoDB
    item = {
        'id': composite_id,
        'event_timestamp': event_timestamp,
        'lambda_timestamp': lambda_timestamp,
        'action_type': action_type,
        'eni_id': eni_id,
        'elb_name': elb_name
    }
    
    # Add ENI details if available
    if eni_details:
        if isinstance(eni_details, dict):
            for key, value in eni_details.items():
                if key != 'eni_id':  # Avoid duplicate
                    item[key] = value
        else:
            item['eni_details'] = str(eni_details)
    
    # Store in DynamoDB
    store_in_dynamodb(item)
    
    # Return response
    result = {
        'event_timestamp': event_timestamp,
        'lambda_timestamp': lambda_timestamp,
        'action_type': action_type,
        'eni_id': eni_id,
        'elb_name': elb_name,
        'elb_arn': eni_details.get('elb_arn') if eni_details else None,
        'dynamodb_id': composite_id,
        'eni_details': eni_details
    }
    
    return {
        'statusCode': 200,
        'body': json.dumps(result, default=str)
    }
