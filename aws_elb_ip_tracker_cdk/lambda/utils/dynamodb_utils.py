"""
Utility functions for working with DynamoDB.
"""
import boto3
import json
import logging
import os
from boto3.dynamodb.conditions import Key
from utils.config import DYNAMODB_TABLE_NAME, INITIAL_SCAN_STATUS_ID, INITIAL_SCAN_FLAG

# Configure logging
logger = logging.getLogger()

# Initialize boto3 resources
dynamodb = boto3.resource('dynamodb')

def store_in_dynamodb(item):
    """
    Store the item in DynamoDB
    
    Args:
        item (dict): The item to store in DynamoDB
        
    Returns:
        dict: The response from DynamoDB
    """
    try:
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # Convert any sets to lists for JSON serialization
        for key, value in item.items():
            if isinstance(value, set):
                item[key] = list(value)
        
        # Store in DynamoDB
        response = table.put_item(Item=item)
        logger.info(f"Successfully stored item in DynamoDB: {response}")
        return response
    except Exception as e:
        logger.error(f"Error storing item in DynamoDB: {str(e)}")
        logger.error(f"Item that failed: {json.dumps(item, default=str)}")
        raise

def create_composite_id(eni_id, action_type, timestamp):
    """
    Create a composite ID using eni_id, action_type, and timestamp.
    This helps prevent duplicate records and makes the data more organized.
    
    Args:
        eni_id (str): Network interface ID
        action_type (str): Action type (add, remove, modify, initial_scan)
        timestamp (str): ISO format timestamp
        
    Returns:
        str: Composite ID in the format "eni_id#action_type#timestamp"
    """
    # Clean up the timestamp to ensure it's valid for a DynamoDB key
    # Remove any special characters that might cause issues
    clean_timestamp = timestamp.replace(':', '-').replace('.', '-')
    
    # Create and return the composite ID
    return f"{eni_id}#{action_type}#{clean_timestamp}"

def check_initial_scan_status():
    """
    Check if the initial scan has been completed.
    
    Returns:
        bool: True if initial scan is needed, False if already completed
    """
    try:
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # Try to get the initial scan status record
        response = table.get_item(
            Key={
                'id': INITIAL_SCAN_STATUS_ID
            }
        )
        
        # If the item exists and completed is True, return False (no scan needed)
        if 'Item' in response and response['Item'].get('completed', False):
            logger.info("Initial scan already completed according to DynamoDB record")
            return False
        
        # If we get here, either the item doesn't exist or completed is False
        logger.info("Initial scan is needed according to DynamoDB check")
        return True
    except Exception as e:
        logger.error(f"Error checking initial scan status: {str(e)}")
        # If there's an error (e.g., table doesn't exist yet), use the environment variable
        logger.info("Using environment variable fallback for initial scan status")
        return INITIAL_SCAN_FLAG

def mark_initial_scan_complete():
    """
    Mark the initial scan as complete in DynamoDB.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # Store a record indicating the initial scan is complete
        response = table.put_item(
            Item={
                'id': INITIAL_SCAN_STATUS_ID,
                'completed': True,
                'timestamp': str(boto3.client('sts').get_caller_identity().get('Account'))
            }
        )
        
        logger.info("Initial scan marked as complete in DynamoDB")
        return True
    except Exception as e:
        logger.error(f"Error marking initial scan as complete: {str(e)}")
        return False

def get_eni_historical_data(eni_id):
    """
    Retrieve historical data for a network interface from DynamoDB.
    This is useful when the ENI has been deleted and we can't get current information.
    
    Args:
        eni_id (str): Network interface ID
        
    Returns:
        dict: The most recent record for this ENI, or None if not found
    """
    try:
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # Query the GSI to find records for this ENI
        response = table.query(
            IndexName="eni-id-index",
            KeyConditionExpression=Key('eni_id').eq(eni_id),
            ScanIndexForward=False,  # Descending order (newest first)
            Limit=1  # We only need the most recent record
        )
        
        if response.get('Items') and len(response['Items']) > 0:
            logger.info(f"Found historical data for ENI {eni_id}")
            return response['Items'][0]
        
        logger.warning(f"No historical data found for ENI {eni_id}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving historical data for ENI {eni_id}: {str(e)}")
        return None

def check_recent_delete_event(eni_id, minutes=1):
    """
    Check if there has been a recent delete event for this ENI.
    This helps prevent processing duplicate delete events.
    
    Args:
        eni_id (str): Network interface ID
        minutes (int): Time window in minutes to check for recent events
        
    Returns:
        bool: True if a recent delete event exists, False otherwise
    """
    from datetime import datetime, timedelta
    import time
    
    try:
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        
        # Calculate timestamp from X minutes ago
        time_ago = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        
        # Query for recent delete events for this ENI
        response = table.query(
            IndexName="eni-id-index",
            KeyConditionExpression=Key('eni_id').eq(eni_id),
            FilterExpression="action_type = :action_type AND event_timestamp > :time_ago",
            ExpressionAttributeValues={
                ':action_type': 'remove',
                ':time_ago': time_ago
            }
        )
        
        if response.get('Items') and len(response['Items']) > 0:
            logger.info(f"Found recent delete event for ENI {eni_id} within the last {minutes} minutes")
            return True
        
        logger.info(f"No recent delete event found for ENI {eni_id}")
        return False
    except Exception as e:
        logger.error(f"Error checking for recent delete events for ENI {eni_id}: {str(e)}")
        return False
