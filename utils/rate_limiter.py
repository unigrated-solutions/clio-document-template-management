import time
import threading
from functools import wraps

class RateLimiter:
    """
    A class to manage rate limits for different API endpoints.
    Tracks rate limit details and enforces the limits for each endpoint.
    """
    def __init__(self, default_limit=60):
        """
        Initialize the rate limiter with a default rate limit.
        
        Args:
            default_limit (int): Default number of requests allowed per minute.
        """
        self.default_limit = default_limit
        self.limits = {}  # Store rate limit details for each endpoint
        self.lock = threading.Lock()
        self.call_times = {}  # Tracks call timestamps for each endpoint

    def update_rate_limits(self, endpoint, response_headers):
        """
        Update the rate limit details for an endpoint based on response headers.
        
        Args:
            endpoint (str): The API endpoint.
            response_headers (dict): Response headers containing rate limit details.
        """
        with self.lock:
            if endpoint not in self.limits:
                self.limits[endpoint] = {
                    "limit": self.default_limit,
                    "remaining": self.default_limit,
                    "reset": time.time() + 60,  # Default reset time: 60 seconds from now
                    "retry_after": None
                }

            # Update from headers if available
            if "X-RateLimit-Limit" in response_headers:
                self.limits[endpoint]["limit"] = int(response_headers["X-RateLimit-Limit"])
            if "X-RateLimit-Remaining" in response_headers:
                self.limits[endpoint]["remaining"] = int(response_headers["X-RateLimit-Remaining"])
            if "X-RateLimit-Reset" in response_headers:
                self.limits[endpoint]["reset"] = int(response_headers["X-RateLimit-Reset"])
            if "Retry-After" in response_headers:
                self.limits[endpoint]["retry_after"] = int(response_headers["Retry-After"])
            
            print(self.limits[endpoint])
            
            
    def __call__(self, endpoint):
        """
        Decorator to enforce the rate limit on a function for a specific endpoint.
        
        Args:
            endpoint (str): The API endpoint.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.lock:
                    if endpoint not in self.limits:
                        self.limits[endpoint] = {
                            "limit": self.default_limit,
                            "remaining": self.default_limit,
                            "reset": time.time() + 60,
                            "retry_after": None
                        }

                    limit_details = self.limits[endpoint]
                    current_time = time.time()

                    # Remove timestamps older than 60 seconds
                    self.call_times[endpoint] = [
                        t for t in self.call_times.get(endpoint, []) if current_time - t < 60
                    ]

                    if len(self.call_times[endpoint]) >= limit_details["limit"]:
                        # Calculate wait time based on reset time or first call
                        if current_time < limit_details["reset"]:
                            wait_time = limit_details["reset"] - current_time
                        else:
                            wait_time = 60 - (current_time - self.call_times[endpoint][0])
                        print(f"Rate limit exceeded for {endpoint}. Waiting for {wait_time:.2f} seconds.")
                        time.sleep(wait_time)

                    # Record the current call's timestamp
                    self.call_times[endpoint].append(time.time())
                    limit_details["remaining"] = max(0, limit_details["remaining"] - 1)

                # Call the actual function
                return func(*args, **kwargs)

            return wrapper
        return decorator