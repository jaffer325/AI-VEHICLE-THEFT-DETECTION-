from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import json
import threading
from werkzeug.utils import secure_filename
from ai_core.pipeline import VideoPipeline
from ai_core.query_engine import QueryEngine

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.config['UPLOAD_FOLDER'] = 'data/temp'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500 MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data/images', exist_ok=True)

pipeline = VideoPipeline(media_dir='data')
engine = QueryEngine(db_path='data/vehicle_data.json')

# Background thread handle
processing_thread = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/images/<path:filename>')
def serve_media(filename):
    return send_from_directory('data/images', filename)

@app.route('/upload_video', methods=['POST'])
def upload_video():
    global processing_thread
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Start AI processing in a background thread if not already running
        if pipeline.is_running:
            return jsonify({"error": "Pipeline is already processing a video."}), 400
            
        processing_thread = threading.Thread(target=pipeline.process_video, args=(filepath,))
        processing_thread.start()
        
        return jsonify({"message": f"Successfully uploaded {filename}. Processing started.", "filename": filename}), 200

@app.route('/process_status', methods=['GET'])
def process_status():
    status = pipeline.get_status()
    return jsonify(status), 200

# ----- NEW DATA ENDPOINTS -----

@app.route('/vehicles', methods=['GET'])
def get_vehicles():
    try:
        with open('data/vehicle_data.json', 'r') as f:
            data = json.load(f)
            return jsonify(data), 200
    except Exception as e:
        return jsonify({"vehicles": []}), 200

@app.route('/events', methods=['GET'])
def get_events():
    try:
        with open('data/suspicious_events.json', 'r') as f:
            data = json.load(f)
            return jsonify(data), 200
    except Exception as e:
        return jsonify({"events": []}), 200

@app.route('/risk_summary', methods=['GET'])
def get_risk_summary():
    summary = {"high": 0, "medium": 0, "low": 0}
    try:
        with open('data/suspicious_events.json', 'r') as f:
            data = json.load(f)
            for event in data.get("events", []):
                level = event.get("risk_level", "low")
                if level in summary:
                    summary[level] += 1
        return jsonify(summary), 200
    except Exception as e:
        return jsonify(summary), 200

# ----- CHAT / QUERY ENGINE -----

@app.route('/query', methods=['POST'])
def query():
    data = request.json
    if not data or 'text' not in data:
        return jsonify({"error": "No text provided"}), 400
        
    text = data['text']
    results = engine.query(text)
    
    return jsonify({"results": results}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
