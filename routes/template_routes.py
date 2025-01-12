from flask import Blueprint, request, render_template, jsonify, Response
import requests
import json
import time
import queue
import threading

from urllib.parse import urlparse, parse_qs
from utils.template_utils import confirm_auth, set_access_token, get_template, delete_template, download_template, get_event_queue, zip_files, upload_template

template_manager = Blueprint('template_manager', __name__)

@template_manager.route("/", methods=["GET"])
def index():
    print("endpoint reached")
    return render_template("template_manager.html")

@template_manager.route("/is_token_set", methods=["GET"])
def confirm_token_set():
    token_set = confirm_auth()
    print(token_set)
    return jsonify(token_set=token_set)  # Return a valid JSON response

@template_manager.route("/upload-token", methods=["POST"])
def upload_token():
    if 'token_file' not in request.files:
        return {"error": "No file uploaded"}, 400

    token_file = request.files['token_file']
    try:
        data = json.load(token_file)
        token = data.get("access_token")
        if not token:
            return {"error": "Invalid JSON: 'access_token' not found"}, 400
        
        set_access_token(token)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON file"}, 400

    return {"message": "Access token successfully stored!"}, 200

@template_manager.route("/get_templates", methods=["GET"])
def get_templates():
    """
    Retrieves a list of filenames from the Clio API and saves them to a JSON file.
    """

    if not confirm_auth():
        return jsonify({"error": "Access token not set"}), 400

    filenames = []  # To store all results
    output_file = "static/templates.json"
    next_page_token = None
    
    while True:
        # Use the rate-limited function to fetch data
        response = get_template()

        if response.status_code != 200:
            print(f"Error: Received status code {response.status_code} with message: {response.text}")
            return jsonify({"error": f"Failed to fetch documents. Status code: {response.status_code}"}), response.status_code

        response_json = response.json()
        filenames.extend(response_json.get('data', []))  # Append the data from the current page

        # Get the next_page_url from the response
        next_page_url = response_json.get('meta', {}).get('paging', {}).get('next')

        if not next_page_url:
            break  # Exit loop if no more pages

        # Parse the next_page_token from the URL
        parsed_url = urlparse(next_page_url)
        query_params = parse_qs(parsed_url.query)
        next_page_token = query_params.get('page_token', [None])[0]

        if not next_page_token:
            break  # Exit loop if page_token is missing

    # Save the combined data to a JSON file
    with open(output_file, 'w') as f:
        json.dump(filenames, f, indent=4)
    print(f"Data saved to {output_file}")

    return jsonify(filenames)
    
@template_manager.route("/delete_templates", methods=["POST"])
def delete_templates():
    """
    Handles the deletion of multiple documents based on their IDs.
    """

    if not confirm_auth():
        return jsonify({"error": "Access token not set"}), 400

    # Parse the JSON payload
    data = request.json
    selected_ids = data.get("file_ids")

    if not selected_ids:
        return jsonify({"error": "No IDs provided"}), 400

    print(f"Processing IDs: {selected_ids}")

    success_ids = []
    failed_ids = []

    for id in selected_ids:
        retry_count = 0
        while retry_count < 5:  # Retry up to 5 times for rate-limited responses
            response = delete_template(id)

            if response.status_code == 200:
                success_ids.append(id)
                break
            elif response.status_code == 429:  # Rate limited
                retry_after = int(response.headers.get("Retry-After", 1))
                print(f"Rate limited for ID {id}. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
                retry_count += 1
            else:  # Other errors
                failed_ids.append({
                    "id": id,
                    "status_code": response.status_code,
                    "error": response.text
                })
                break  # Exit retry loop for non-retryable errors

    # Prepare the response summary
    result = {
        "message": "File processing complete",
        "success_ids": success_ids,
        "failed_ids": failed_ids,
    }

    if failed_ids:
        return jsonify(result), 207  # 207: Multi-Status (some operations succeeded, some failed)
    else:
        return jsonify(result), 200

@template_manager.route("/download_templates", methods=["POST"])
def download_templates():
    data = request.get_json()
    files = data.get("files")  # Array of objects: {id, filename}
    destination_path = data.get("destination_path")
    print(files)
    # Remove duplicate file IDs
    # TODO Duplicates caused by shift logic
    
    unique_files = []
    seen_ids = set()

    for file in files:
        file_id = str(file.get("id"))  # Normalize IDs to strings
        if file_id and file_id not in seen_ids:
            seen_ids.add(file_id)
            unique_files.append(file)
        else:
            print(f"Duplicate found: {file_id}")
    
    if not unique_files:
        return jsonify({"error": {"type": "ValidationError", "message": "No files selected for download."}}), 400


    # Start a background thread for downloading
    def download_files():
        downloaded_files = []
        output_path = None
        event_queue = get_event_queue()
        for index, file in enumerate(unique_files):
            file_id = file.get("id")
            filename = file.get("filename")
            retry_count = 0

            while retry_count < 5:  # Retry up to 5 times
                try:
                    print(f"Attempting to download file ID {file_id}")
                    content = download_template(file_id)
                    print(f"Downloaded: {filename}")

                    if destination_path:
                        output_path = destination_path
                    else:
                        output_path = "/home/user/Downloads"

                    downloaded_files.append((filename, content))
                    break  # Exit retry loop on success

                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    time.sleep(30)  # Wait before retrying
                    if retry_count == 5:
                        event_queue.put(f"Failed to download file ID {file_id}. Skipping.")

        # Zip the files if more than one is downloaded
        # if len(downloaded_files) > 1:
        output_path = zip_files(downloaded_files, output_path)
        event_queue.put(f"Documents saved to {output_path} ")

    # Run the download process in a separate thread
    threading.Thread(target=download_files).start()

    return jsonify({"message": "Download initiated. Progress updates will follow."})

@template_manager.route("/upload_templates", methods=["POST"])
def upload_templates():
    """
    API endpoint to handle file uploads and template processing.
    """
    try:
        # Extract form data
        matter_id = request.form.get("matter_id")
        file_type = request.form.get("type")
        category = request.form.get("category")  # Optional
        update_template = request.form.get("update", None) 
        uploaded_files = request.files.getlist("files")  # Expecting "files" key

        # Validate required fields
        if not file_type or not uploaded_files:
            return jsonify({"error": "Missing required fields"}), 400

        if update_template:
            # TODO Map template filename to id
            pass
        
        results = []
        for file in uploaded_files:
            try:
                # Process the file directly
                response = upload_template(file, update=update_template)
                results.append(response)
            except Exception as e:
                results.append({
                    "file": file.filename,
                    "status": "error",
                    "error": str(e)
                })

        return jsonify({
            "message": "Files uploaded and processed",
            "matter_id": matter_id,
            "file_type": file_type,
            "category": category,
            "results": results
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@template_manager.route("/stream-status")
def stream_status():
    """
    Stream status updates to the client using SSE.
    Rebroadcasts the last status when no new updates are available.
    """
    last_status = "Status: Waiting for input"  # Initial status
    event_queue = get_event_queue()
    def event_stream():
        nonlocal last_status, event_queue
        while True:
            try:
                # Wait for an event to be added to the queue
                status_update = event_queue.get(timeout=10)  # Timeout to avoid blocking indefinitely
                last_status = status_update  # Update the last status
                yield f"data: {status_update}\n\n"
            except queue.Empty:
                # Rebroadcast the last status
                yield f"data: {last_status}\n\n"

    return Response(event_stream(), content_type="text/event-stream")
