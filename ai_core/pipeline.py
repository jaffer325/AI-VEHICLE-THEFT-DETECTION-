import cv2
import os
import json
from .detector import ObjectDetector
from .extractor import FeatureExtractor
from .reid import ReIdentificator

class VideoPipeline:
    def __init__(self, media_dir="media", db_path="database.json"):
        self.detector = ObjectDetector()
        self.extractor = FeatureExtractor()
        self.reid = ReIdentificator()
        
        self.media_dir = media_dir
        self.db_path = db_path
        os.makedirs(self.media_dir, exist_ok=True)
        
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    self.reid.database = json.load(f)
            except:
                self.reid.database = {}
                
        self.progress = 0
        self.status = "Initializing"
        self.is_running = False

    def process_video(self, video_path):
        self.is_running = True
        self.status = f"Processing {os.path.basename(video_path)}"
        self.progress = 0
        
        # Clear database to act as temporary store for current video only
        self.reid.database = {}
        self.save_database()
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0 or total_frames == 0:
            self.status = "Error: Invalid video file."
            self.is_running = False
            return
            
        frame_idx = 0
        prev_positions = {}
        
        # Track when we last extracted embeddings to speed up processing
        last_extracted_frame = {} 

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_idx += 1
            current_time = frame_idx / fps
            
            # Optimize speed by skipping frames (evaluate 1/3 of frames)
            if frame_idx % 3 != 0:
                continue
            
            active_tracks = self.detector.track(frame)
            
            for t in active_tracks:
                t_id = t["id"]
                bbox = t["bbox"]
                class_id = t["class_id"]
                class_name = self.detector.get_class_name(class_id)
                obj_type = "person" if class_name == "person" else "vehicle"
                
                x1, y1, x2, y2 = map(int, bbox)
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(frame.shape[1], x2); y2 = min(frame.shape[0], y2)
                
                if (x2 - x1 < 10) or (y2 - y1 < 10):
                    continue
                
                embedding = None
                # Optimize: Only extract heavy embedding every 30 frames or when first seen
                if t_id not in last_extracted_frame or (frame_idx - last_extracted_frame[t_id]) > 30:
                    crop = frame[y1:y2, x1:x2]
                    if crop.size > 0:
                        embedding = self.extractor.get_embedding(crop)
                        last_extracted_frame[t_id] = frame_idx
                
                u_id = self.reid.get_or_create_id(t_id, class_name, embedding, bbox)
                
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                vx, vy = 0, 0
                if u_id in prev_positions:
                    px, py, pt = prev_positions[u_id]
                    dt = current_time - pt
                    if dt > 0:
                        vx = (cx - px) / dt
                        vy = (cy - py) / dt
                        
                prev_positions[u_id] = (cx, cy, current_time)
                direction = self._get_direction(vx, vy)
                
                # Removed dense tracking_history tracking array to eliminate redundant data
                data = {
                    "id": u_id,
                    "type": obj_type,
                    "vehicle_type": class_name,
                    "position": {"x": cx, "y": cy},
                    "velocity": {"vx": vx, "vy": vy, "direction": direction},
                    "embedding": embedding,
                    "last_seen": current_time
                }
                
                db_entry = self.reid.database.get(u_id, {})
                
                # Save Image ONLY on first appearance
                if not db_entry.get("first_image"):
                    crop = frame[y1:y2, x1:x2] if 'crop' not in locals() else crop
                    if crop is not None and crop.size > 0:
                        img_name = f"{u_id}_{int(current_time*10)}.jpg"
                        cv2.imwrite(os.path.join(self.media_dir, img_name), crop)
                        data["first_seen"] = current_time
                        data["first_image"] = img_name
                        
                        if obj_type == "vehicle":
                            data["color"] = self.extractor.get_dominant_color(crop)
                            data["plate_number"] = self.extractor.get_number_plate(crop)
                
                self.reid.update_database(u_id, data)
                
            self.progress = int((frame_idx / total_frames) * 100)
            
            if frame_idx % 60 == 0:
                self.save_database()

        cap.release()
        self.save_database()
        self.progress = 100
        self.status = "Complete"
        self.is_running = False

    def save_database(self):
        with open(self.db_path, 'w') as f:
            json.dump(self.reid.database, f, indent=4)

    def _get_direction(self, vx, vy):
        if abs(vx) < 10 and abs(vy) < 10:
            return "stationary"
        if abs(vx) > abs(vy):
            return "right" if vx > 0 else "left"
        else:
            return "down" if vy > 0 else "up"
            
    def get_status(self):
        return {
            "is_running": self.is_running,
            "progress": self.progress,
            "status": self.status
        }
