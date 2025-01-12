        // Add event listeners for keydown and keyup to track Shift key state
        document.addEventListener("keydown", (event) => {
            if (event.key === "Shift") {
                document.body.classList.add("no-select"); // Disable text selection
            }
        });

        document.addEventListener("keyup", (event) => {
            if (event.key === "Shift") {
                document.body.classList.remove("no-select"); // Re-enable text selection
            }
        });
        
        // Token Setting Logic
        document.addEventListener("DOMContentLoaded", async () => {
            const uploadButton = document.getElementById("upload-button");
            const tokenFileInput = document.getElementById("token-file");
            const uploadMessage = document.getElementById("upload-message");
        
            // Check if token is already set when the page loads
            try {
                const response = await fetch("/is_token_set");
                const result = await response.json();
                console.log("Token check response:", result); // Debugging
        
                if (result.token_set === true) {
                    uploadButton.textContent = "Access Token Set";
                    uploadButton.style.backgroundColor = "green";
                    uploadButton.style.color = "white";
                }
            } catch (error) {
                console.error("Failed to check token status:", error);
            }
        
            // Open file dialog when button is clicked
            uploadButton.addEventListener("click", () => {
                tokenFileInput.click();
            });
        
            // Handle file upload and feedback
            tokenFileInput.addEventListener("change", async (event) => {
                const file = event.target.files[0];
        
                if (!file) {
                    return;
                }
        
                const formData = new FormData();
                formData.append("token_file", file);
        
                try {
                    const response = await fetch("/upload-token", {
                        method: "POST",
                        body: formData,
                    });
        
                    const result = await response.json();
        
                    if (response.ok) {
                        uploadButton.textContent = "Access Token Set";
                        uploadButton.style.backgroundColor = "green";
                        uploadButton.style.color = "white";
                        uploadMessage.textContent = ""; // Clear any messages
                    } else {
                        uploadMessage.textContent = result.error;
                        uploadMessage.style.color = "red";
                    }
                } catch (error) {
                    uploadMessage.textContent = "An error occurred during upload.";
                    uploadMessage.style.color = "red";
                }
            });
        });

        document.addEventListener("DOMContentLoaded", () => {
            const tabs = document.querySelectorAll(".tab");
            const contents = document.querySelectorAll(".content");
            const fetchButtons = document.querySelectorAll(".fetch-files");
            
            const fileList = document.getElementById("file-list"); // Delete list
            const downloadFileList = document.getElementById("download-file-list"); // Download list
            const searchInput = document.getElementById("search-input");
            const searchDownloadInput = document.getElementById("search-download-input");
            
            const destinationPathInput = document.getElementById("destination-path");
            
            const deleteButton = document.getElementById("delete-files");
            const downloadButton = document.getElementById("download-files");
            const statusBar = document.getElementById("status-bar");
            const statusText = document.getElementById("status-text");
        
            const uploadList = document.getElementById("upload-list");
            const fileInput = document.getElementById("file-input");
            const uploadButton = document.getElementById("upload-files");
            const matterIdInput = document.getElementById("matter-id");
            const fileTypeDropdown = document.getElementById("file-type");
            const categoryInput = document.getElementById("category-input");

            let sharedFiles = []; // Shared fetched files
            let selectedDeleteFiles = new Set();
            let selectedDownloadFiles = new Set();
            let lastSelectedIndexDelete = null; // Last selected index for delete list
            let lastSelectedIndexDownload = null; // Last selected index for download list

            let filesToUpload = []; // List of files with absolute paths
        

            // Synchronize search inputs
            function syncSearchInputs(value) {
                searchInput.value = value;
                searchDownloadInput.value = value;
            }
            
            // Tab Switching Logic
            tabs.forEach(tab => {
                tab.addEventListener("click", () => {
                    tabs.forEach(t => t.classList.remove("active"));
                    contents.forEach(content => content.classList.remove("active"));
        
                    tab.classList.add("active");
                    const tabName = tab.dataset.tab;
                    document.getElementById(`${tabName}-content`).classList.add("active");
        
                    // Preserve search text between tabs
                    const currentSearchValue = searchInput.value;
                    syncSearchInputs(currentSearchValue);
                    filterAllLists(currentSearchValue.toLowerCase());
                });
            });
        
            // Fetch Files and Update Both Lists
            fetchButtons.forEach(button => {
                button.addEventListener("click", async () => {
                    const response = await fetch("/get_templates");
                    if (response.ok) {
                        sharedFiles = await response.json();
                        console.log("Files fetched:", sharedFiles);
        
                        // Update both the delete and download lists
                        renderFileList(sharedFiles, fileList, selectedDeleteFiles, toggleDeleteSelection);
                        renderFileList(sharedFiles, downloadFileList, selectedDownloadFiles, toggleDownloadSelection);
                    } else {
                        alert("Error fetching files.");
                    }
                });
            });
        
            // Render File List
            function renderFileList(files, fileListElement, selectedFiles, toggleSelectionCallback) {
                fileListElement.innerHTML = ""; // Clear existing rows
        
                files.forEach((file, index) => {
                    const li = document.createElement("li");
                    li.dataset.id = file.id;
                    li.dataset.filename = file.filename;
                    li.dataset.index = index; // Add index for shift selection
                    li.classList.add("file-item");
        
                    // Display file information
                    li.innerHTML = `
                        <div class="file-info">
                            ${file.filename} ${
                                file.document_category ? `(Category: ${file.document_category.name})` : "(No Category)"
                            }
                        </div>
                    `;
        
                    // Highlight selected files
                    if (selectedFiles.has(file.id)) {
                        li.classList.add("selected");
                    }
        
                    // Add click event for selection toggle
                    li.addEventListener("click", (e) => {
                        toggleSelectionCallback(e, file.id, li, fileListElement, selectedFiles);
                        e.stopPropagation(); // Prevent deselecting all on list item click
                    });
        
                    fileListElement.appendChild(li);
                });
        
                // Show message if no valid files are found
                if (!files.length) {
                    const li = document.createElement("li");
                    li.textContent = "No valid files found.";
                    li.style.color = "#888";
                    fileListElement.appendChild(li);
                }
            }
        
            // Toggle Selection for Deletion
            function toggleDeleteSelection(event, fileId, listItem, fileListElement, selectedFiles) {
                handleSelection(event, fileId, listItem, fileListElement, selectedFiles, lastSelectedIndexDelete, (newIndex) => {
                    lastSelectedIndexDelete = newIndex;
                });
                updateDeleteButtonState();
            }
        
            // Toggle Selection for Downloading
            function toggleDownloadSelection(event, fileId, listItem, fileListElement, selectedFiles) {
                handleSelection(event, fileId, listItem, fileListElement, selectedFiles, lastSelectedIndexDownload, (newIndex) => {
                    lastSelectedIndexDownload = newIndex;
                });
                updateDownloadButtonState();
            }
        
            // Handle Selection Logic
            function handleSelection(event, fileId, listItem, fileListElement, selectedFiles, lastSelectedIndex, updateLastIndex) {
                const items = Array.from(fileListElement.querySelectorAll(".file-item"));
                const currentIndex = parseInt(listItem.dataset.index);
        
                if (event.shiftKey && lastSelectedIndex !== null) {
                    // Shift-based range selection
                    const startIndex = Math.min(currentIndex, lastSelectedIndex);
                    const endIndex = Math.max(currentIndex, lastSelectedIndex);
        
                    for (let i = startIndex; i <= endIndex; i++) {
                        const item = items[i];
                        const id = item.dataset.id;
        
                        if (!selectedFiles.has(id)) {
                            selectedFiles.add(id);
                            item.classList.add("selected");
                        }
                    }
                } else if (event.ctrlKey || event.metaKey) {
                    // Ctrl-based multi-selection (metaKey for Mac)
                    if (selectedFiles.has(fileId)) {
                        selectedFiles.delete(fileId);
                        listItem.classList.remove("selected");
                    } else {
                        selectedFiles.add(fileId);
                        listItem.classList.add("selected");
                    }
                } else {
                    // Single selection
                    selectedFiles.clear();
                    items.forEach(item => item.classList.remove("selected"));
        
                    selectedFiles.add(fileId);
                    listItem.classList.add("selected");
                }
        
                updateLastIndex(currentIndex); // Update the last selected index
            }

            // Deselect All on Page Click (Outside Interactive Elements)
            document.addEventListener("click", (e) => {
                if (![...tabs, ...fetchButtons, deleteButton, downloadButton, searchInput, searchDownloadInput, fileList, downloadFileList, destinationPathInput].some(el => el.contains(e.target))) {
                    clearSelections();
                }
            });

            // Clear All Selections
            function clearSelections() {
                selectedDeleteFiles.clear();
                selectedDownloadFiles.clear();

                const allItems = document.querySelectorAll(".file-item");
                allItems.forEach(item => item.classList.remove("selected"));

                updateDeleteButtonState();
                updateDownloadButtonState();
            }

            // Unified Live Search
            [searchInput, searchDownloadInput].forEach(input => {
                input.addEventListener("input", (e) => {
                    clearSelections();
                    const query = e.target.value.toLowerCase();
                    syncSearchInputs(e.target.value); // Synchronize search inputs
                    filterAllLists(query);
                });
            });
        
            // Filter Both Lists Simultaneously
            function filterAllLists(query) {
                [fileList, downloadFileList].forEach(fileListElement => {
                    const items = fileListElement.querySelectorAll(".file-item");
                    items.forEach(item => {
                        const text = item.querySelector(".file-info").textContent.toLowerCase();
                        item.style.display = text.includes(query) ? "flex" : "none";
                    });
                });
            }
        
            // Update Button States
            function updateDeleteButtonState() {
                deleteButton.disabled = selectedDeleteFiles.size === 0;
            }
        
            function updateDownloadButtonState() {
                downloadButton.disabled = selectedDownloadFiles.size === 0;
            }
        
            // Delete Files and Remove from Both Lists
            deleteButton.addEventListener("click", async () => {
                const fileIds = Array.from(selectedDeleteFiles);
                if (!fileIds.length) {
                    alert("No files selected for deletion.");
                    return;
                }
        
                try {
                    const response = await fetch("/delete_templates", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ file_ids: fileIds }),
                    });
        
                    if (response.ok) {
                        const result = await response.json();
                        alert(result.message);
        
                        // Remove deleted files from both lists
                        fileIds.forEach(id => {
                            const deleteItem = document.querySelector(`#file-list li[data-id='${id}']`);
                            if (deleteItem) deleteItem.remove();
        
                            const downloadItem = document.querySelector(`#download-file-list li[data-id='${id}']`);
                            if (downloadItem) downloadItem.remove();
        
                            // Remove from both selection sets
                            selectedDeleteFiles.delete(id);
                            selectedDownloadFiles.delete(id);
                        });
        
                        updateDeleteButtonState();
                        updateDownloadButtonState();
                    } else {
                        alert("Error deleting files.");
                    }
                } catch (error) {
                    console.error("Error deleting files:", error);
                    alert("An error occurred while deleting files.");
                }
            });
        
            // Download Files
            downloadButton.addEventListener("click", async () => {
                const filesToDownload = Array.from(selectedDownloadFiles).map(fileId => {
                    const listItem = document.querySelector(`#download-file-list li[data-id="${fileId}"]`);
                    return {
                        id: fileId,
                        filename: listItem ? listItem.dataset.filename : `file_${fileId}.txt`,
                    };
                });
        
                if (!filesToDownload.length) {
                    alert("No files selected for download.");
                    return;
                }
        
                try {
                    statusBar.style.display = "block";
                    statusText.textContent = "Starting download...";
        
                    const response = await fetch("/download_templates", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            files: filesToDownload,
                            destination_path: destinationPathInput.value.trim() || null,
                        }),
                    });
        
                    if (response.ok) {
                        statusText.textContent = "Download completed!";
                    } else {
                        const error = await response.json();
                        statusText.textContent = `Error: ${error.message}`;
                    }
                } catch (error) {
                    console.error("Error downloading files:", error);
                    statusText.textContent = "An unexpected error occurred.";
                }
            });

            // Add files to the list when selected
            fileInput.addEventListener("change", (event) => {
                Array.from(event.target.files).forEach((file) => {
                    // Check if file already exists in the list
                    if (!filesToUpload.some((f) => f.name === file.name)) {
                        filesToUpload.push(file);
            
                        // Add to UI
                        const li = document.createElement("li");
                        li.textContent = file.name;
                        li.dataset.path = file.webkitRelativePath || file.name; // Use absolute path or file name
                        li.classList.add("file-item");
            
                        // Add a remove button for the item
                        const removeButton = document.createElement("button");
                        removeButton.textContent = "Remove";
                        removeButton.style.marginLeft = "10px";
                        removeButton.style.backgroundColor = "#f44336";
                        removeButton.style.color = "white";
                        removeButton.style.border = "none";
                        removeButton.style.borderRadius = "5px";
                        removeButton.style.cursor = "pointer";
            
                        // Remove file logic
                        removeButton.addEventListener("click", () => {
                            filesToUpload = filesToUpload.filter((f) => f.name !== file.name); // Remove from array
                            li.remove(); // Remove from UI
                            toggleUploadButton(); // Re-evaluate upload button state
                        });
            
                        li.appendChild(removeButton);
                        uploadList.appendChild(li);
                    }
                });
            
                toggleUploadButton();
            });
            
            // Enable/Disable Upload Button
            matterIdInput.addEventListener("input", toggleUploadButton);
            fileTypeDropdown.addEventListener("change", toggleUploadButton);
            
            function toggleUploadButton() {
                const matterId = matterIdInput.value.trim();
                const fileType = fileTypeDropdown.value;
                uploadButton.disabled = !filesToUpload.length;
            }
            
            // Upload Files
            uploadButton.addEventListener("click", async () => {
                console.log("Uploading files:", filesToUpload.map(f => f.name));
                console.log("Matter ID:", matterIdInput.value.trim(), "Type:", fileTypeDropdown.value);
            
                const matterId = matterIdInput.value.trim();
                const fileType = fileTypeDropdown.value;
                const category = categoryInput.value.trim(); // Optional category field
            
                if (filesToUpload.length === 0) {
                    alert("Please provide a Matter ID, File Type, and select files to upload.");
                    return;
                }
            
                const formData = new FormData();
                formData.append("matter_id", matterId);
                formData.append("type", fileType);
                if (category) formData.append("category", category); // Optional
                filesToUpload.forEach(file => formData.append("files", file)); // Attach files
            
                try {
                    const response = await fetch("/upload_templates", {
                        method: "POST",
                        body: formData,
                    });
            
                    if (response.ok) {
                        const result = await response.json();
                        alert(result.message);
                        console.log("Uploaded files:", result.uploaded_files); // Debugging uploaded files
                        filesToUpload = [];
                        fileInput.value = ""; // Clear file input
                    } else {
                        const error = await response.json();
                        console.error("Error uploading files:", error);
                        alert("Error uploading files: " + (error.error || "Unknown error"));
                    }
                } catch (error) {
                    console.error("Unexpected error during upload:", error);
                    alert("An unexpected error occurred during upload.");
                }
            });

            
        });
        
/////////////////////////
        // Connect to the SSE endpoint
        const statusBar = document.getElementById("status-bar");
        const statusText = document.getElementById("status-text");
        const eventSource = new EventSource("/stream-status");

        // Display updates from the server
        eventSource.onmessage = function(event) {
            console.log("Received update:", event.data);

            // Show the status bar if hidden
            if (statusBar.style.display === "none") {
                statusBar.style.display = "block";
            }

            // Update the status text
            statusText.textContent = event.data;

            // Hide the status bar when the task is completed
            if (event.data.toLowerCase().includes("completed")) {
                setTimeout(() => {
                    statusBar.style.display = "none";
                }, 3000); // Hide after 3 seconds
            }
        };

        // Handle errors
        eventSource.onerror = function() {
            console.error("Error with SSE connection.");
            statusText.textContent = "Connection lost. Retrying...";
        };
