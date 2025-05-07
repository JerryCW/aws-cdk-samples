"""
Main Lambda handler for the ELB IP Tracker.

This Lambda function monitors Elastic Load Balancer (ELB) network interfaces
and their associated IP addresses, storing the information in DynamoDB.
"""
import json
import logging
from datetime import datetime

# Import utility modules
from utils.elb_utils import extract_elb_info
from utils.network_utils import get_network_interface_details, scan_existing_elb_interfaces
from utils.dynamodb_utils import (
    store_in_dynamodb, 
    create_composite_id, 
    check_initial_scan_status, 
    mark_initial_scan_complete
)
from utils.cfn_utils import send_cfn_response
from utils.decorators import retry, check_public_ip_exists
from utils.event_utils import extract_eni_info
from utils.event_handlers import handle_delete_event, handle_create_or_modify_event
from utils.config import (
    EVENT_TYPE_CREATE, 
    EVENT_TYPE_DELETE,
    EVENT_TYPE_MODIFY,
    ELB_NAME_UNKNOWN,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_DELAY
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Apply the retry decorator to get_network_interface_details for create events
@retry(max_attempts=DEFAULT_RETRY_ATTEMPTS, delay=DEFAULT_RETRY_DELAY, check_func=check_public_ip_exists)
def get_network_interface_details_with_retry(eni_id):
    """
    Get network interface details with retry logic for public IP.
    This is used for 'Create' events where public IP might not be immediately available.
    
    Args:
        eni_id (str): Network interface ID
        
    Returns:
        dict: Network interface details or None if not found
    """
    return get_network_interface_details(eni_id)

def handle_initial_scan(lambda_timestamp):
    """
    Handle the initial scan of existing ELB network interfaces.
    
    Args:
        lambda_timestamp (str): The timestamp when the Lambda was invoked
        
    Returns:
        dict: Response with status code and results
    """
    logger.info("Performing initial scan of existing ELB interfaces.")
    scan_result = scan_existing_elb_interfaces(get_network_interface_details_with_retry, lambda_timestamp)
    mark_initial_scan_complete()
    return scan_result

def handle_custom_resource_event(event, context, lambda_timestamp):
    """
    Handle CloudFormation custom resource events.
    
    Args:
        event (dict): The event that triggered the Lambda function
        context (object): The Lambda context object
        lambda_timestamp (str): The timestamp when the Lambda was invoked
        
    Returns:
        dict: Response with status code and results
    """
    logger.info("Received custom resource event for initial scan")
    
    # Only perform the scan on Create or Update events
    if event.get('RequestType') in ['Create', 'Update'] or event.get('trigger') == 'initial-scan':
        # Check if we need to perform the initial scan
        if check_initial_scan_status():
            logger.info("Initial scan triggered by custom resource.")
            scan_result = handle_initial_scan(lambda_timestamp)
            
            # For CloudFormation custom resources, we need to respond with a specific format
            if event.get('ResponseURL'):
                send_cfn_response(event, context, 'SUCCESS', {
                    'Message': 'Initial scan completed successfully'
                })
            
            return scan_result
        else:
            logger.info("Initial scan already completed. No action needed.")
            
            # For CloudFormation custom resources, we need to respond with a specific format
            if event.get('ResponseURL'):
                send_cfn_response(event, context, 'SUCCESS', {
                    'Message': 'Initial scan already completed'
                })
            
            return {
                'statusCode': 200,
                'body': json.dumps('Initial scan already completed. No action taken.')
            }
    
    # For Delete events, just acknowledge
    if event.get('RequestType') == 'Delete' and event.get('ResponseURL'):
        send_cfn_response(event, context, 'SUCCESS', {
            'Message': 'Delete acknowledged'
        })
        return {
            'statusCode': 200,
            'body': json.dumps('Delete event acknowledged')
        }
    
    # Default response
    return {
        'statusCode': 200,
        'body': json.dumps('Custom resource event processed')
    }

def handle_cloudtrail_event(event, lambda_timestamp):
    """
    Handle CloudTrail events for network interface changes.
    
    Args:
        event (dict): The CloudWatch event containing CloudTrail information
        lambda_timestamp (str): The timestamp when the Lambda was invoked
        
    Returns:
        dict: Response with status code and results
    """
    logger.info(f"Processing CloudTrail event")
    
    # Get timestamp from event detail or use current time
    # CloudTrail events are wrapped in the 'detail' field of CloudWatch Events
    detail = event.get('detail', {})
    event_timestamp = detail.get('eventTime', lambda_timestamp)
    
    try:
        # Extract network interface information using the simplified approach
        # This function now properly handles the CloudTrail event structure
        eni_info = extract_eni_info(event)
        
        if not eni_info or not eni_info.get('eni_id'):
            logger.error("Could not extract network interface ID from the event")
            return {
                'statusCode': 400,
                'body': json.dumps('Failed to extract network interface ID')
            }
        
        action_type = eni_info['action_type']
        eni_id = eni_info['eni_id']
        description = eni_info['description']
        
        logger.info(f"Network Interface ID: {eni_id}, Action: {action_type}")
        
        # Handle different event types with specialized handlers
        if action_type == EVENT_TYPE_DELETE:
            # Special handling for delete events to deal with already deleted ENIs
            return handle_delete_event(eni_id, event_timestamp, lambda_timestamp)
        else:
            # For create or modify events, use the appropriate handler
            get_details_func = get_network_interface_details_with_retry if action_type == EVENT_TYPE_CREATE else get_network_interface_details
            return handle_create_or_modify_event(
                eni_id, 
                action_type, 
                description, 
                event_timestamp, 
                lambda_timestamp, 
                get_details_func
            )
        
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing event: {str(e)}')
        }

def lambda_handler(event, context):
    """
    Main Lambda handler function that processes network interface events,
    extracts ELB information, and stores the data in DynamoDB.
    
    Args:
        event (dict): The event that triggered the Lambda function
        context (object): The Lambda context object
        
    Returns:
        dict: Response with status code and results
    """
    # Record Lambda execution time
    lambda_timestamp = datetime.utcnow().isoformat()
    
    # Log the event type to help with debugging
    logger.info(f"Event received: {json.dumps(event, default=str)}")
    
    # Check if this is a custom resource event for initial scan
    if event.get('ResourceType') == 'Custom::InitialScanTrigger' or event.get('trigger') == 'initial-scan':
        return handle_custom_resource_event(event, context, lambda_timestamp)
    
    # Check if we need to perform the initial scan (regular check)
    if check_initial_scan_status():
        return handle_initial_scan(lambda_timestamp)
    
    # If this is a CloudTrail event, process it
    if event.get('detail-type') == 'AWS API Call via CloudTrail':
        return handle_cloudtrail_event(event, lambda_timestamp)
    
    # If we get here, it's an unknown event type
    logger.info(f"Received unknown event type. No action taken.")
    return {
        'statusCode': 200,
        'body': json.dumps('Event received but no action taken')
    }
