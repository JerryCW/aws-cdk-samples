"""
Configuration settings for the ELB IP Tracker Lambda function.
"""
import os

# DynamoDB settings
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'ELBNetworkInterfaces')
INITIAL_SCAN_STATUS_ID = 'INITIAL_SCAN_STATUS'

# Retry settings
DEFAULT_RETRY_ATTEMPTS = 6
DEFAULT_RETRY_DELAY = 30

# Initial scan settings
INITIAL_SCAN_FLAG = os.environ.get('INITIAL_SCAN', 'true').lower() == 'true'

# CloudTrail event types
EVENT_TYPE_CREATE = 'add'
EVENT_TYPE_DELETE = 'remove'
EVENT_TYPE_MODIFY = 'modify'
EVENT_TYPE_INITIAL_SCAN = 'initial_scan'

# ELB types
ELB_TYPE_APP = 'app'
ELB_TYPE_NET = 'net'
ELB_TYPE_CLASSIC = 'classic'
ELB_TYPE_UNKNOWN = 'unknown'
ELB_NAME_UNKNOWN = 'unknown-elb'
