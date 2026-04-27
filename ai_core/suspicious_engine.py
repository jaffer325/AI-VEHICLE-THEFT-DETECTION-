import json
import os
import math
import uuid

class SuspiciousEngine:
    def __init__(self, data_path='data/suspicious_events.json'):
        self.data_path = data_path
        self.history = {}
        self.last_triggers = {}
        self.events_db = {"events": []}
        
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f:
                    content = json.load(f)
                    if "events" in content:
                        self.events_db = content
            except:
                pass

        self.loitering_time = 15.0
        self.speeding_threshold_person = 150.0
        self.speeding_threshold_vehicle = 500.0

    def analyze_behavior(self, u_id, obj_type, position, velocity, current_time, snapshot_path=None, memory=None):
        if u_id not in self.history:
            self.history[u_id] = []
            
        self.history[u_id].append({"pos": position, "time": current_time, "vel": velocity})
        self.history[u_id] = [h for h in self.history[u_id] if current_time - h["time"] < 30.0]
        history = self.history[u_id]
        
        vx = velocity.get("vx", 0)
        vy = velocity.get("vy", 0)
        speed = math.sqrt(vx*vx + vy*vy)
        
        # Determine risk
        event_found = False
        event_type = ""
        reasons = []
        risk_score = 0
        risk_level = "low"
        
        # Rule 1: Speeding / Running
        thresh = self.speeding_threshold_person if obj_type == "person" else self.speeding_threshold_vehicle
        if speed > thresh:
            if not self._is_cooldown(u_id, "Running"):
                event_found = True
                event_type = "fast_movement"
                reasons.append("moving at suspicious speed")
                reasons.append("running away quickly")
                risk_score = 65 if obj_type == "vehicle" else 85
                risk_level = "medium" if obj_type == "vehicle" else "high"
                self._set_cooldown(u_id, "Running", current_time)

        # Rule 2: Loitering
        if not event_found and len(history) > 5 and (current_time - history[0]["time"]) >= self.loitering_time:
            first_pos = history[0]["pos"]
            is_loitering = True
            for h in history:
                dx = h["pos"]["x"] - first_pos["x"]
                dy = h["pos"]["y"] - first_pos["y"]
                if math.sqrt(dx*dx + dy*dy) > 50.0:
                    is_loitering = False
                    break
                    
            if is_loitering and not self._is_cooldown(u_id, "Loitering"):
                event_found = True
                event_type = "loitering"
                reasons.append(f"stationary for {int(self.loitering_time)}s")
                risk_score = 75
                risk_level = "medium"
                self._set_cooldown(u_id, "Loitering", current_time)

        # Rule 3: Vehicle Tampering / Break-In
        if not event_found and obj_type == "person" and memory:
            px, py = position["x"], position["y"]
            for v_id, v_data in memory.items():
                if v_data.get("type", "") == "vehicle" and v_data.get("status") == "active":
                    # Check distance to vehicle
                    v_traj = v_data.get("trajectory", [])
                    if len(v_traj) > 0:
                        vx, vy = v_traj[-1]
                        dist = math.sqrt((px - vx)**2 + (py - vy)**2)
                        
                        # Check if vehicle is basically stationary (e.g. parked)
                        v_speeds = v_data.get("speed_history", [])
                        v_speed = v_speeds[-1] if len(v_speeds) > 0 else 0
                        
                        # Rule 3 REFINED: Person is very close to parked car AND standing still (not just walking by)
                        if dist < 60.0 and v_speed < 10:
                            # Check if person is also relatively stationary (low velocity)
                            vx_p = velocity.get("vx", 0)
                            vy_p = velocity.get("vy", 0)
                            p_speed = math.sqrt(vx_p**2 + vy_p**2)
                            
                            if p_speed < 80: # Standing/Lurking near car
                                if not self._is_cooldown(u_id, "Tampering"):
                                    event_found = True
                                    event_type = "vehicle_tampering"
                                    reasons.append("person lingering suspiciously close to parked vehicle")
                                    reasons.append("potential break-in/interference detected")
                                    risk_score = 95
                                    risk_level = "high"
                                    self._set_cooldown(u_id, "Tampering", current_time)
                                    break

        # Rule 4: Hazardous Tailgating (High speed, very close proximity)
        if not event_found and obj_type == "vehicle" and memory:
            vx1, vy1 = velocity.get("vx", 0), velocity.get("vy", 0)
            s1 = math.sqrt(vx1**2 + vy1**2)
            
            if s1 > 350: # Only check if vehicle 1 is moving fast
                for v_id, v_data in memory.items():
                    if v_id != u_id and v_data.get("type") == "vehicle":
                        v_traj = v_data.get("trajectory", [])
                        if len(v_traj) > 0:
                            vx2, vy2 = v_traj[-1]
                            dist = math.sqrt((position["x"] - vx2)**2 + (position["y"] - vy2)**2)
                            
                            v_speeds = v_data.get("speed_history", [])
                            s2 = v_speeds[-1] if len(v_speeds) > 0 else 0
                            
                            if dist < 120 and s2 > 300: # Both moving fast and very close
                                if not self._is_cooldown(u_id, "Tailgating"):
                                    event_found = True
                                    event_type = "hazardous_driving"
                                    reasons.append("extreme tailgating at high speed")
                                    reasons.append("unsafe following distance")
                                    risk_score = 80
                                    risk_level = "high"
                                    self._set_cooldown(u_id, "Tailgating", current_time)
                                    break

        # Rule 5: Critical Potential Collision (Fast vehicle near person)
        if not event_found and memory:
            if obj_type == "vehicle":
                v_vx, v_vy = velocity.get("vx", 0), velocity.get("vy", 0)
                v_speed = math.sqrt(v_vx**2 + v_vy**2)
                
                if v_speed > 300:
                    for p_id, p_data in memory.items():
                        if p_data.get("type") == "person":
                            p_traj = p_data.get("trajectory", [])
                            if len(p_traj) > 0:
                                px, py = p_traj[-1]
                                dist = math.sqrt((position["x"] - px)**2 + (position["y"] - py)**2)
                                if dist < 100:
                                    if not self._is_cooldown(u_id, "PotentialCollision"):
                                        event_found = True
                                        event_type = "imminent_danger"
                                        reasons.append("high-speed vehicle in close proximity to pedestrian")
                                        reasons.append("critical collision risk")
                                        risk_score = 98
                                        risk_level = "critical"
                                        self._set_cooldown(u_id, "PotentialCollision", current_time)
                                        break

        if event_found:
            event = {
                "event_id": str(uuid.uuid4().hex[:8]),
                "person_id": u_id if obj_type == "person" else None,
                "vehicle_id": u_id if obj_type == "vehicle" else None,
                "event_type": event_type,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "start_time": f"00:00:{int(current_time):02d}", # Formatted roughly
                "end_time": f"00:00:{int(current_time):02d}",
                "snapshot": snapshot_path,
                "reasons": reasons
            }
            self.events_db["events"].append(event)
            self.save_events()
            return event
            
        return None

    def _is_cooldown(self, u_id, event_type):
        key = f"{u_id}_{event_type}"
        return key in self.last_triggers
        
    def _set_cooldown(self, u_id, event_type, current_time):
        key = f"{u_id}_{event_type}"
        self.last_triggers[key] = current_time

    def save_events(self):
        with open(self.data_path, 'w') as f:
            json.dump(self.events_db, f, indent=4)
