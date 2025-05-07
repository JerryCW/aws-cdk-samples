"""
Utility functions for handling different event types.
"""
import json
import logging
from utils.config import EVENT_TYPE_CREATE, EVENT_TYPE_DELETE, EVENT_TYPE_MODIFY

# Configure logging
logger = logging.getLogger()

def extract_eni_info_create(detail):
    """
    Extract network interface information from a Create event.
    
    Args:
        detail (dict): The CloudTrail event detail
        
    Returns:
        dict: Dictionary containing action_type, eni_id, and description
    """
    response_elements = detail.get('responseElements', {})
    network_interface = response_elements.get('networkInterface', {})
    return {
        'action_type': EVENT_TYPE_CREATE,
        'eni_id': network_interface.get('networkInterfaceId'),
        'description': network_interface.get('description', '')
    }

def extract_eni_info_delete(detail):
    """
    Extract network interface information from a Delete event.
    
    Args:
        detail (dict): The CloudTrail event detail
        
    Returns:
        dict: Dictionary containing action_type, eni_id, and description
    """
    request_parameters = detail.get('requestParameters', {})
    return {
        'action_type': EVENT_TYPE_DELETE,
        'eni_id': request_parameters.get('networkInterfaceId'),
        'description': ''
    }

def extract_eni_info_modify(detail):
    """
    Extract network interface information from a Modify event.
    
    Args:
        detail (dict): The CloudTrail event detail
        
    Returns:
        dict: Dictionary containing action_type, eni_id, and description
    """
    response_elements = detail.get('responseElements', {})
    network_interface = response_elements.get('networkInterface', {})
    return {
        'action_type': EVENT_TYPE_MODIFY,
        'eni_id': network_interface.get('networkInterfaceId'),
        'description': network_interface.get('description', '')
    }

def extract_eni_info(event):
    """
    Extract network interface information from a CloudTrail event.
    
    Args:
        event (dict): The CloudWatch event containing CloudTrail information
        
    Returns:
        dict: Dictionary containing action_type, eni_id, and description or None if event type is not supported
    """
    # Extract the detail field which contains the actual CloudTrail event
    detail = event.get('detail', {})
    
    # Get the event name from the detail
    event_name = detail.get('eventName', '')
    
    logger.info(f"Processing CloudTrail event: {event_name}")
    
    # Map event names to handler functions
    event_handlers = {
        'Create': extract_eni_info_create,
        'Delete': extract_eni_info_delete,
        'Modify': extract_eni_info_modify
    }
    
    # Find the appropriate handler based on the event name
    handler_key = next((k for k in event_handlers.keys() if k in event_name), None)
    
    if handler_key:
        logger.info(f"Processing {handler_key} event: {event_name}")
        return event_handlers[handler_key](detail)
    
    logger.warning(f"Unsupported event type: {event_name}")
    return None
