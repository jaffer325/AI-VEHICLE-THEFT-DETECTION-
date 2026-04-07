document.addEventListener("DOMContentLoaded", () => {
    
    // View switching
    const navChat = document.getElementById('nav-chat');
    const navUpload = document.getElementById('nav-upload');
    const viewChat = document.getElementById('view-chat');
    const viewUpload = document.getElementById('view-upload');
    const topTitle = document.getElementById('top-title');

    navUpload.addEventListener('click', (e) => {
        e.preventDefault();
        navUpload.parentElement.classList.add('active');
        navChat.parentElement.classList.remove('active');
        viewChat.classList.add('d-none');
        viewUpload.classList.remove('d-none');
        topTitle.innerText = "Upload CCTV";
    });

    navChat.addEventListener('click', (e) => {
        e.preventDefault();
        navChat.parentElement.classList.add('active');
        navUpload.parentElement.classList.remove('active');
        viewUpload.classList.add('d-none');
        viewChat.classList.remove('d-none');
        topTitle.innerText = "AI Search Assistant";
    });

    // File Upload handling
    const videoFileInput = document.getElementById('video_file');
    const progressContainer = document.getElementById('upload-progress-container');
    const progressBar = document.getElementById('upload-progress-bar');
    const statusText = document.getElementById('upload-status-text');

    let processingInterval = null;

    videoFileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        progressContainer.classList.remove('d-none');
        progressBar.style.width = '10%';
        progressBar.innerText = "Uploading...";
        statusText.innerText = "Uploading " + file.name + "...";

        try {
            const response = await fetch('/upload_video', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (response.ok) {
                // Upload complete, start polling for process status
                startPollingStatus();
            } else {
                statusText.innerText = "Error: " + data.error;
                statusText.classList.add('text-danger');
            }
        } catch (err) {
            statusText.innerText = "Upload failed: " + err;
        }
    });

    function startPollingStatus() {
        if (processingInterval) clearInterval(processingInterval);
        
        processingInterval = setInterval(async () => {
            try {
                const res = await fetch('/process_status');
                const data = await res.json();
                
                progressBar.style.width = data.progress + '%';
                progressBar.innerText = data.progress + '%';
                statusText.innerText = "Status: " + data.status;

                if (!data.is_running && data.progress === 100) {
                    clearInterval(processingInterval);
                    statusText.innerText = "Processing Complete! You can now search in the Chat UI.";
                    progressBar.classList.remove('progress-bar-animated');
                    
                    // Switch back to chat automatically after 2s
                    setTimeout(() => navChat.click(), 2000);
                    refreshHistory();
                } else if (!data.is_running && data.progress < 100 && data.progress > 0) {
                    clearInterval(processingInterval); // Error case
                }
            } catch (e) {
                console.error("Polling error", e);
            }
        }, 1000);
    }

    // Chat handling
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatBox = document.getElementById('chat-box');

    function appendMessage(isUser, content, isHtml=false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${isUser ? 'user-message' : 'ai-message'}`;
        
        const avatarStr = isUser ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';
        
        const contentStr = isHtml ? content : `<div class="message-content">${content}</div>`;
        const avatarDiv = `<div class="avatar">${avatarStr}</div>`;
        
        msgDiv.innerHTML = avatarDiv + contentStr;
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function buildResultCards(results) {
        if (!results || results.length === 0) {
            return ``;
        }

        let html = ``;
        
        results.forEach(res => {
            const imgPath = `/media/${res.first_image || res.last_image || 'placeholder.jpg'}`;
            const velocity = res.velocity ? Math.round(Math.sqrt(res.velocity.vx**2 + res.velocity.vy**2)) : 'N/A';
            const color = res.color ? ` | ${res.color}` : '';
            const plate = res.plate_number ? ` | ${res.plate_number}` : '';
            
            html += `
            <div class="result-card">
                <img src="${imgPath}" alt="${res.type}">
                <div class="result-details">
                    <p><i class="fa-solid fa-tag text-primary"></i> ${res.id.split('-')[0]}</p>
                    <p><i class="fa-solid fa-car"></i> ${res.vehicle_type}${color}${plate}</p>
                    <p><i class="fa-solid fa-gauge"></i> ${res.velocity ? res.velocity.direction : 'unknown'} (${velocity}/s)</p>
                </div>
            </div>`;
        });
        
        return `<div class="results-row pb-2">${html}</div>`;
    }

    async function submitQuery() {
        const text = chatInput.value.trim();
        if (!text) return;

        appendMessage(true, text);
        chatInput.value = '';

        // Add typical AI typing indicator here if wanted.
        
        try {
            const res = await fetch('/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({text})
            });
            const data = await res.json();
            
            const aiResponse = data.results.response_text || "";
            const targets = data.results.results || [];
            
            let innerHtml = ``;
            if (targets.length > 0) {
                innerHtml += buildResultCards(targets);
            }
            innerHtml += `<div class="response-text py-1 border-top">${aiResponse}</div>`;
            
            const combinedHtml = `<div class="message-content w-100">${innerHtml}</div>`;
            
            appendMessage(false, combinedHtml, true);
            
        } catch (e) {
            appendMessage(false, "Network error processing your query.");
        }
    }

    sendBtn.addEventListener('click', submitQuery);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') submitQuery();
    });

    // History Sidebar
    async function refreshHistory() {
        try {
            const res = await fetch('/get_results');
            const data = await res.json();
            const panel = document.getElementById('history-panel');
            const totalObj = document.getElementById('total-objects');
            
            if (data.results && data.results.length > 0) {
                totalObj.innerText = `${data.results.length} Objects`;
                panel.innerHTML = '';
                
                data.results.slice(0, 15).forEach(item => {
                    const d = document.createElement('div');
                    d.className = 'history-item';
                    const c = item.color ? `(${item.color})` : '';
                    d.innerHTML = `<strong>${item.vehicle_type}</strong> ${c}<br><span class="text-muted" style="font-size:10px;">ID: ${item.id.split('-')[0]}</span>`;
                    panel.appendChild(d);
                });
            }
        } catch (e) {
            console.error("History fetch error", e);
        }
    }

    refreshHistory();
});
