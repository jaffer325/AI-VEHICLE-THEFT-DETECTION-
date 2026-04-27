import json
import os
from .detector import ObjectDetector
from .extractor import FeatureExtractor
from .reid import ReIdentificator

class TrackingEngine:
    def __init__(self, data_path='data/vehicle_data.json'):
        self.data_path = data_path
        self.detector = ObjectDetector()
        self.extractor = FeatureExtractor()
        self.reid = ReIdentificator()
        
        self.tracking_db = {"vehicles": []}
        self.memory = {} # Fast access dictionary for current session
        
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f:
                    content = json.load(f)
                    if "vehicles" in content:
                        self.tracking_db = content
                        for v in content["vehicles"]:
                            self.memory[v["vehicle_id"]] = v
            except:
                pass

    def track_frame(self, frame, frame_idx, current_time):
        """Processes a single frame for detection and Re-ID tracking"""
        active_tracks = self.detector.track(frame)
        updates = []
        
        for t in active_tracks:
            t_id = t["id"]
            bbox = t["bbox"]
            class_name = self.detector.get_class_name(t["class_id"])
            obj_type = "person" if class_name == "person" else "vehicle"
            
            x1, y1, x2, y2 = map(int, bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
            
            if (x2 - x1 < 10) or (y2 - y1 < 10):
                continue
                
            crop = frame[y1:y2, x1:x2]
            embedding = None
            if crop.size > 0 and frame_idx % 30 == 0:
                embedding = self.extractor.get_embedding(crop)
                
            u_id = self.reid.get_or_create_id(t_id, class_name, embedding, bbox)
            
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            
            # Format according to spec
            if u_id not in self.memory:
                self.memory[u_id] = {
                    "vehicle_id": u_id,
                    "type": class_name,
                    "first_seen": f"00:00:{int(current_time):02d}",
                    "last_seen": f"00:00:{int(current_time):02d}",
                    "first_image": "",
                    "last_image": "",
                    "best_quality": 0,
                    "trajectory": [],
                    "speed_history": [],
                    "status": "active"
                }
                
                # Full extraction on first sight
                if obj_type == "vehicle":
                    self.memory[u_id]["color"] = ""
                    self.memory[u_id]["plate"] = ""
                    if crop.size > 0:
                        self.memory[u_id]["color"] = self.extractor.get_dominant_color(crop)
                        self.memory[u_id]["plate"] = self.extractor.get_number_plate(crop)
            
            v_data = self.memory[u_id]
            v_data["last_seen"] = f"00:00:{int(current_time):02d}"
            v_data["trajectory"].append([cx, cy])
            # limit trajectory to prevent file bloat
            if len(v_data["trajectory"]) > 100:
                v_data["trajectory"] = v_data["trajectory"][-100:]
                
            updates.append({
                "u_id": u_id,
                "type": obj_type,
                "crop": crop,
                "position": {"x": cx, "y": cy},
                "velocity": self._calc_velocity(u_id, cx, cy, current_time)
            })
            
        return updates

    def _calc_velocity(self, u_id, cx, cy, t):
        v_data = self.memory[u_id]
        if "last_pos" in v_data:
            px, py, pt = v_data["last_pos"]
            dt = t - pt
            if dt > 0:
                vx, vy = (cx - px) / dt, (cy - py) / dt
                speed = (vx**2 + vy**2)**0.5
                v_data["speed_history"].append(int(speed))
                v_data["last_pos"] = (cx, cy, t)
                return {"vx": vx, "vy": vy, "speed": speed}
        v_data["last_pos"] = (cx, cy, t)
        return {"vx": 0, "vy": 0, "speed": 0}



    def save_tracking(self):
        # Flatten memory into list
        self.tracking_db["vehicles"] = list(self.memory.values())
        with open(self.data_path, 'w') as f:
            json.dump(self.tracking_db, f, indent=4)
