"""
Decorator functions for adding functionality to other functions.
"""
import logging
import time
from utils.config import DEFAULT_RETRY_ATTEMPTS, DEFAULT_RETRY_DELAY

# Configure logging
logger = logging.getLogger()

def retry(max_attempts=DEFAULT_RETRY_ATTEMPTS, delay=DEFAULT_RETRY_DELAY, check_func=None):
    """
    A decorator that retries a function if it fails or if check_func returns False.
    
    Args:
        max_attempts (int): Maximum number of retry attempts
        delay (int): Delay in seconds between retries
        check_func (callable): Optional function to check if result is acceptable
                              Should take the function result as input and return True if acceptable
    
    Returns:
        decorator: A decorator that adds retry logic to a function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            last_result = None
            
            while attempts <= max_attempts:
                try:
                    result = func(*args, **kwargs)
                    last_result = result
                    
                    # If no check function or check function returns True, return the result
                    if check_func is None or check_func(result):
                        return result
                    
                    # If we get here, the result didn't pass the check
                    logger.info(f"Result didn't pass check on attempt {attempts+1}/{max_attempts+1}. Retrying...")
                    
                except Exception as e:
                    logger.error(f"Error on attempt {attempts+1}/{max_attempts+1}: {str(e)}")
                    last_result = None
                
                # Increment attempts and sleep if we have more attempts left
                attempts += 1
                if attempts <= max_attempts:
                    logger.info(f"Retrying in {delay} seconds... (Attempt {attempts+1}/{max_attempts+1})")
                    time.sleep(delay)
            
            # If we get here, we've exhausted all attempts
            logger.warning(f"Function {func.__name__} failed after {max_attempts+1} attempts")
            return last_result
        
        return wrapper
    
    return decorator

def check_public_ip_exists(result):
    """
    Check if the network interface details contain a public IP.
    
    Args:
        result (dict): Network interface details
        
    Returns:
        bool: True if public IP exists, False otherwise
    """
    if result is None:
        return False
    
    # Check if the result has a public IP
    if result.get('public_ip'):
        logger.info(f"Public IP found: {result['public_ip']}")
        return True
    
    # If this is a deleted interface, don't retry
    if result.get('status') == 'deleted':
        return True
    
    logger.info("No public IP found yet")
    return False
