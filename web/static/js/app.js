document.addEventListener("DOMContentLoaded", () => {
    
    const navChat = document.getElementById('nav-chat');
    const navUpload = document.getElementById('nav-upload');
    const navVehicles = document.getElementById('nav-vehicles');
    const navAlerts = document.getElementById('nav-alerts');
    
    const viewChat = document.getElementById('view-chat');
    const viewUpload = document.getElementById('view-upload');
    const viewVehicles = document.getElementById('view-vehicles');
    const viewAlerts = document.getElementById('view-alerts');
    
    const topTitle = document.getElementById('top-title');

    function switchView(activeNav, activeView, title) {
        // Reset Nav
        [navChat, navUpload, navVehicles, navAlerts].forEach(el => el.parentElement.classList.remove('active'));
        activeNav.parentElement.classList.add('active');
        
        // Reset Views
        [viewChat, viewUpload, viewVehicles, viewAlerts].forEach(el => {
            el.classList.add('d-none');
            el.classList.remove('d-flex');
        });
        
        if (activeView === viewChat) activeView.classList.add('d-flex');
        activeView.classList.remove('d-none');
        topTitle.innerText = title;
    }

    navUpload.addEventListener('click', (e) => { e.preventDefault(); switchView(navUpload, viewUpload, "Upload CCTV"); });
    navChat.addEventListener('click', (e) => { e.preventDefault(); switchView(navChat, viewChat, "AI Search Assistant"); });
    navVehicles.addEventListener('click', (e) => { e.preventDefault(); switchView(navVehicles, viewVehicles, "Vehicle Tracking"); fetchVehicles(); });
    navAlerts.addEventListener('click', (e) => { e.preventDefault(); switchView(navAlerts, viewAlerts, "Suspicious Alerts"); fetchAlerts(); });

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
            const imgPath = res.first_image ? `/${res.first_image}` : (res.last_image ? `/${res.last_image}` : '/static/img/placeholder.png');
            
            const v_id = (res.vehicle_id || res.id || 'N/A').split('-')[0].substring(0,8);
            const v_type = (res.type || res.vehicle_type || 'unknown').toUpperCase();
            const color = res.color ? ` | ${res.color}` : '';
            const plate = (res.plate || res.plate_number) ? ` | ${res.plate || res.plate_number}` : '';
            
            let speed = 'N/A';
            if (res.speed_history && res.speed_history.length > 0) speed = Math.max(...res.speed_history);
            else if (res.velocity && res.velocity.vx) speed = Math.round(Math.sqrt(res.velocity.vx**2 + res.velocity.vy**2));
            
            html += `
            <div class="result-card">
                <img src="${imgPath}" alt="${v_type}">
                <div class="result-details">
                    <p><i class="fa-solid fa-tag text-primary"></i> ${v_id}</p>
                    <p><i class="fa-solid fa-car"></i> ${v_type}${color}${plate}</p>
                    <p><i class="fa-solid fa-gauge"></i> Max Speed: ${speed}px/s</p>
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

    // History Sidebar (Updating total objects)
    async function refreshHistory() {
        try {
            const res = await fetch('/vehicles');
            const data = await res.json();
            const panel = document.getElementById('history-panel');
            const totalObj = document.getElementById('total-objects');
            
            if (data.vehicles && data.vehicles.length > 0) {
                totalObj.innerText = `${data.vehicles.length} Objects`;
                panel.innerHTML = '';
                
                const latest = [...data.vehicles].reverse().slice(0, 15);
                latest.forEach(item => {
                    const d = document.createElement('div');
                    d.className = 'history-item';
                    const c = item.color ? `(${item.color})` : '';
                    d.innerHTML = `<strong>${item.type || 'unknown'}</strong> ${c}<br><span class="text-muted" style="font-size:10px;">ID: ${item.vehicle_id.substring(0,8)}</span>`;
                    panel.appendChild(d);
                });
            }
        } catch (e) {
            console.error("History fetch error", e);
        }
    }

    // --- NEW DATA RENDERING FUNCTIONS ---

    async function fetchVehicles() {
        try {
            const res = await fetch('/vehicles');
            const data = await res.json();
            const grid = document.getElementById('vehicle-grid');
            grid.innerHTML = '';
            
            if (!data.vehicles || data.vehicles.length === 0) {
                grid.innerHTML = '<p class="text-muted w-100 mt-4 text-center">No vehicles tracked yet.</p>';
                return;
            }
            
            data.vehicles.reverse().forEach(v => {
                const img = v.last_image ? `/${v.last_image}` : '/static/img/placeholder.png';
                const speed = (v.speed_history && v.speed_history.length > 0) ? Math.max(...v.speed_history) : 0;
                
                grid.innerHTML += `
                <div class="card shadow-sm" style="width: 260px;">
                    <img src="${img}" class="card-img-top bg-dark" style="height:150px;object-fit:contain;" alt="vehicle">
                    <div class="card-body">
                        <span class="badge bg-primary float-end">${v.type.toUpperCase()}</span>
                        <h6 class="card-title text-truncate">ID: ${v.vehicle_id.substring(0,8)}</h6>
                        <p class="card-text small mb-1"><i class="fa-solid fa-clock"></i> ${v.first_seen} - ${v.last_seen}</p>
                        <p class="card-text small mb-1"><i class="fa-solid fa-palette text-muted"></i> ${v.color || 'Unknown'} | <i class="fa-solid fa-gauge text-muted"></i> Max ${speed}px/s</p>
                        <p class="card-text small fw-bold text-success"><i class="fa-solid fa-car-side"></i> Plate: ${v.plate || 'N/A'}</p>
                    </div>
                </div>`;
            });
        } catch(e) {
            console.error("Failed fetching vehicles", e);
        }
    }

    async function fetchAlerts() {
        try {
            const res = await fetch('/events');
            const data = await res.json();
            const grid = document.getElementById('alerts-grid');
            grid.innerHTML = '';
            
            if (!data.events || data.events.length === 0) {
                grid.innerHTML = '<p class="text-muted w-100 mt-4 text-center">No suspicious events recorded.</p>';
                return;
            }
            
            data.events.reverse().forEach(ev => {
                const img = ev.snapshot ? `/${ev.snapshot}` : '/static/img/placeholder.png';
                const badgeColor = ev.risk_level === 'high' ? 'bg-danger' : 'bg-warning text-dark';
                
                grid.innerHTML += `
                <div class="card shadow-sm border-danger" style="width: 280px;">
                    <img src="${img}" class="card-img-top bg-dark" style="height:160px;object-fit:contain;" alt="Suspicious Event">
                    <div class="card-body">
                        <span class="badge ${badgeColor} float-end">${ev.risk_level.toUpperCase()}</span>
                        <h6 class="card-title text-danger text-truncate"><i class="fa-solid fa-triangle-exclamation"></i> ${ev.event_type.replace('_',' ')}</h6>
                        <p class="card-text small mb-1 fw-bold text-muted">${ev.start_time}</p>
                        <ul class="small ps-3 text-muted mb-0">
                            ${ev.reasons.map(r => `<li>${r}</li>`).join('')}
                        </ul>
                    </div>
                </div>`;
            });
        } catch(e) {
            console.error("Failed fetching alerts", e);
        }
    }

    // Load initial view
    switchView(navVehicles, viewVehicles, "Vehicle Tracking");
    fetchVehicles();
});
