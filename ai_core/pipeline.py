import cv2
import os
from .tracking_engine import TrackingEngine
from .suspicious_engine import SuspiciousEngine
from .image_engine import ImageEngine

class VideoPipeline:
    def __init__(self, media_dir="data", db_path="data/vehicle_data.json"):
        self.tracking = TrackingEngine()
        self.suspicious = SuspiciousEngine()
        self.image_engine = ImageEngine()
        
        self.progress = 0
        self.status = "Initializing"
        self.is_running = False

    def process_video(self, video_path):
        self.is_running = True
        self.status = f"Processing {os.path.basename(video_path)}"
        self.progress = 0
        
        # Clear completely for new video run
        import shutil
        img_dir = self.image_engine.img_dir
        if os.path.exists(img_dir):
             shutil.rmtree(img_dir, ignore_errors=True)
        os.makedirs(img_dir, exist_ok=True)
        
        if os.path.exists(self.tracking.data_path):
            try: os.remove(self.tracking.data_path)
            except: pass
            
        if os.path.exists('data/suspicious_events.json'):
            try: os.remove('data/suspicious_events.json')
            except: pass
            
        if os.path.exists('data/image_metadata.json'):
            try: os.remove('data/image_metadata.json')
            except: pass
            
        self.tracking.tracking_db = {"vehicles": []}
        self.tracking.memory = {}
        self.suspicious.events_db = {"events": []}
        self.suspicious.last_triggers = {}
        self.tracking.save_tracking()
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0 or total_frames == 0:
            self.status = "Error: Invalid video file."
            self.is_running = False
            return
            
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_idx += 1
            current_time = frame_idx / fps
            
            # Process Frame 1/3
            if frame_idx % 3 != 0:
                continue
            
            # 1. TRACKING ENGINE
            updates = self.tracking.track_frame(frame, frame_idx, current_time)
            
            for u in updates:
                u_id = u["u_id"]
                crop = u["crop"]
                
                # 2. IMAGE ENGINE
                img_path = None
                if crop is not None and crop.size > 0:
                    quality = self.image_engine.calculate_sharpness(crop)
                    v_data = self.tracking.memory[u_id]
                    if quality > v_data.get("best_quality", 0):
                        new_path = self.image_engine.save_image(crop, u_id, current_time)
                        if new_path:
                            v_data["first_image"] = new_path
                            v_data["last_image"] = new_path
                            v_data["best_quality"] = quality
                            img_path = new_path
                            if u["type"] == "vehicle":
                                v_data["color"] = self.tracking.extractor.get_dominant_color(crop)
                                v_data["plate"] = self.tracking.extractor.get_number_plate(crop)
                    else:
                        img_path = v_data.get("first_image")
                
                # 3. SUSPICIOUS ENGINE
                event = self.suspicious.analyze_behavior(
                    u_id=u_id, 
                    obj_type=u["type"], 
                    position=u["position"], 
                    velocity=u["velocity"], 
                    current_time=current_time,
                    snapshot_path=img_path,
                    memory=self.tracking.memory
                )
                
            self.progress = int((frame_idx / total_frames) * 100)
            
            if frame_idx % 60 == 0:
                self.tracking.save_tracking()

        cap.release()
        self.tracking.save_tracking()
        self.progress = 100
        self.status = "Complete"
        self.is_running = False

    def get_status(self):
        return {
            "is_running": self.is_running,
            "progress": self.progress,
            "status": self.status
        }
