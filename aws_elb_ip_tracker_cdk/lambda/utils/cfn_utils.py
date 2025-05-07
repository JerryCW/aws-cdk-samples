"""
Utility functions for working with CloudFormation.
"""
import json
import logging
import urllib.request
import urllib.parse

# Configure logging
logger = logging.getLogger()

def send_cfn_response(event, context, response_status, response_data):
    """
    Send a response to CloudFormation for custom resource events.
    
    Args:
        event: The event that triggered the Lambda function
        context: The Lambda context
        response_status: 'SUCCESS' or 'FAILED'
        response_data: Dictionary containing response data
    """
    response_body = {
        'Status': response_status,
        'Reason': f"See the details in CloudWatch Log Stream: {context.log_stream_name}",
        'PhysicalResourceId': context.log_stream_name,
        'StackId': event.get('StackId'),
        'RequestId': event.get('RequestId'),
        'LogicalResourceId': event.get('LogicalResourceId'),
        'Data': response_data
    }
    
    response_url = event.get('ResponseURL')
    
    if not response_url:
        logger.warning("No ResponseURL found in the event. Skipping CloudFormation response.")
        return
    
    logger.info(f"Sending response to CloudFormation: {json.dumps(response_body)}")
    
    req = urllib.request.Request(
        url=response_url,
        data=json.dumps(response_body).encode('utf-8'),
        headers={
            'Content-Type': '',
            'Content-Length': len(json.dumps(response_body))
        },
        method='PUT'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            logger.info(f"CloudFormation response status code: {response.getcode()}")
            logger.info(f"CloudFormation response: {response.read().decode('utf-8')}")
    except Exception as e:
        logger.error(f"Failed to send response to CloudFormation: {str(e)}")
