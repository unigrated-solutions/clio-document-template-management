import os
import requests
import zipfile
import time
import queue
import base64
from io import BytesIO

from utils.rate_limiter import RateLimiter

#Default limit per Clio Documentation
# https://docs.developers.clio.com/api-docs/rate-limits/
rate_limiter = RateLimiter(default_limit=50)

_access_token = None


# Global event queue to store updates
_event_queue = queue.Queue()

def get_event_queue():
    return _event_queue

def set_access_token(token):
    global _access_token
    _access_token = token
    
def confirm_auth():
    return _access_token is not None


def zip_files(files, directory_path):
    """
    Create a ZIP file from a list of files, saving it in the specified directory.

    Args:
        files (list): A list of tuples, where each tuple contains a filename and file content (bytes).
        directory_path (str): Path to the directory where the ZIP file will be saved.
    """
    # Ensure the directory exists
    os.makedirs(directory_path, exist_ok=True)

    # Determine a unique ZIP file name
    base_name = "document_export"
    extension = ".zip"
    counter = 0
    output_filename = f"{base_name}{extension}"
    output_filepath = os.path.join(directory_path, output_filename)

    while os.path.exists(output_filepath):
        counter += 1
        output_filename = f"{base_name}_{counter}{extension}"
        output_filepath = os.path.join(directory_path, output_filename)

    # Create the ZIP archive
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filename, content in files:
            zipf.writestr(filename, content)

    # Write the ZIP file to the determined path
    with open(output_filepath, "wb") as f:
        f.write(zip_buffer.getvalue())
    
    print(f"ZIP file created at {output_filepath}")
    return output_filepath  # Return the path to the created ZIP file

@rate_limiter("https://app.clio.com/api/v4/document_templates")
def get_template(page_token=None):
    """
    Makes a paginated request to the Clio API to fetch document templates.

    Args:
        api_url (str): The API endpoint URL.
        params (dict): Query parameters for the request.
        headers (dict): Request headers.

    Returns:
        requests.Response: The API response object.
    """
    print("Getting documents")
    
    api_url = "https://app.clio.com/api/v4/document_templates.json"
    headers = {
        "Authorization": f"Bearer {_access_token}",
        "Content-Type": "application/json"
    }

    params = {
        "limit": 200,  # Maximum allowed by the API
        "order": "category.name(asc)",
        "parent_type": "matter",
        "fields": "id,filename,document_category{id,name}"
    }
    if page_token:
        params["page_token"] = page_token
        
    _event_queue.put(f"Retrieving list of existing templates")
    response = requests.get(api_url, params=params, headers=headers)

    # Update rate limit details from response headers
    rate_limiter.update_rate_limits("https://app.clio.com/api/v4/document_templates", response.headers)

    if response.status_code == 429:  # Rate limit exceeded
        retry_after = int(response.headers.get("Retry-After", 1))
        _event_queue.put(f"Rate limited. Retrying after {retry_after} seconds.")
        time.sleep(retry_after)  # Wait before retrying
        response = requests.get(api_url, params=params, headers=headers)
    _event_queue.put(f"Finished retrieving templates")
    return response

@rate_limiter("https://app.clio.com/api/v4/document_templates/delete")
def delete_template(id):
    """
    Sends a DELETE request to delete a document with the given ID.

    Args:
        id (int): The ID of the document to delete.

    Returns:
        requests.Response: The response from the external API.
    """
    api_url = f"https://app.clio.com/api/v4/document_templates/{id}.json"
    headers = {
        "Authorization": f"Bearer {_access_token}",
        "Content-Type": "application/json"
    }

    response = requests.delete(api_url, headers=headers)

    # Update rate limits dynamically based on response headers
    rate_limiter.update_rate_limits("https://app.clio.com/api/v4/document_templates/delete", response.headers)

    return response

@rate_limiter("https://app.clio.com/api/v4/document_templates/download.json")
def download_template(file_id):
    """
    Fetches a file from the external API and returns the response or raises an exception.

    Args:
        file_id (int): The ID of the file to download.

    Returns:
        tuple: Filename and file content.
    """
    api_url = f"https://app.clio.com/api/v4/document_templates/{file_id}/download.json"
    headers = {
        "Authorization": f"Bearer {_access_token}",
        "Content-Type": "application/pdf",
    }

    response = requests.get(api_url, headers=headers)

    # Update the rate limiter with response headers
    rate_limiter.update_rate_limits(api_url, response.headers)

    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 1))
        raise requests.exceptions.RequestException(
            f"Rate limited. Retry after {retry_after} seconds."
        )

    if response.status_code != 200:
        raise requests.exceptions.RequestException(f"HTTP {response.status_code}: {response.text}")

    return response.content

@rate_limiter("https://app.clio.com/api/v4/document_templates/update")
def update_template(file, template_id, category=None):
    """
    Process the uploaded file by making a POST request to an external API.

    Args:
        file: A file-like object from the user's upload.

    Returns:
        dict: A dictionary with the processing result.
    """
    try:
        # Read the file content and get the filename
        file_content = file.read()
        filename = file.filename

        # Encode file content in Base64
        base64_encoded_file = base64.b64encode(file_content).decode("utf-8")

        # Construct the JSON payload
        payload = {
            "data": {
                "filename": filename,
                "file": base64_encoded_file
            }
        }

        # Make the POST request
        api_url = f"https://app.clio.com/api/v4/document_templates/{template_id}.json"
        headers = {
            "Authorization": f"Bearer {_access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(api_url, json=payload, headers=headers)
        print(response)
        # Check the response
        if response.status_code == 200:
            return {
                "file": filename,
                "status": "success",
                "response": response.json()
            }
        else:
            return {
                "file": filename,
                "status": "failed",
                "error": response.text,
                "status_code": response.status_code
            }
    except Exception as e:
        return {
            "file": file.filename,
            "status": "error",
            "error": str(e)
        }

@rate_limiter("https://app.clio.com/api/v4/document_templates/create") 
def upload_template(file, category=None, update=False):
    """
    Process the uploaded file by making a POST request to an external API.

    Args:
        file: A file-like object from the user's upload.

    Returns:
        dict: A dictionary with the processing result.
    """
    try:
        # Read the file content and get the filename
        file_content = file.read()
        filename = file.filename
        print(filename)
        # Encode file content in Base64
        base64_encoded_file = base64.b64encode(file_content).decode("utf-8")

        # Construct the JSON payload
        payload = {
            "data": {
                "filename": filename,
                "file": base64_encoded_file
            }
        }

        # Make the POST request
        api_url = "https://app.clio.com/api/v4/document_templates.json"
        headers = {
            "Authorization": f"Bearer {_access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(api_url, json=payload, headers=headers)
        print(response)
        # Check the response
        if response.status_code == 200:
            return {
                "file": filename,
                "status": "success",
                "response": response.json()
            }
        else:
            return {
                "file": filename,
                "status": "failed",
                "error": response.text,
                "status_code": response.status_code
            }
    except Exception as e:
        return {
            "file": file.filename,
            "status": "error",
            "error": str(e)
        }
