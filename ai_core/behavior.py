import math

class BehaviorAnalyzer:
    def __init__(self):
        self.history = {} # u_id -> list of history points
        self.last_triggers = {} # cooldown to prevent spamming
        
        # Thresholds
        self.loitering_time = 15.0 # seconds
        self.loitering_radius = 50.0 # pixels distance max movement
        
        # Speed thresholds (pixels per second rough estimate)
        self.speeding_threshold_person = 150.0
        self.speeding_threshold_vehicle = 500.0

    def check_behavior(self, u_id, obj_type, position, velocity, current_time):
        """
        Evaluate recent history for suspicious actions.
        Returns a dict event if triggered, else None.
        """
        if u_id not in self.history:
            self.history[u_id] = []
            
        self.history[u_id].append({"pos": position, "time": current_time, "vel": velocity})
        
        # Keep only last 30 seconds
        self.history[u_id] = [h for h in self.history[u_id] if current_time - h["time"] < 30.0]
        history = self.history[u_id]
        
        # 1. Check Speeding / Running
        vx = velocity.get("vx", 0)
        vy = velocity.get("vy", 0)
        speed = math.sqrt(vx*vx + vy*vy)
        
        thresh = self.speeding_threshold_person if obj_type == "person" else self.speeding_threshold_vehicle
        if speed > thresh:
            if not self._is_cooldown(u_id, "Speeding", current_time):
                self._set_cooldown(u_id, "Speeding", current_time)
                return {
                    "id": u_id, 
                    "obj_type": obj_type, 
                    "event_type": "Speeding/Running", 
                    "timestamp": current_time, 
                    "details": f"Speed: {int(speed)} px/s"
                }

        # 2. Check Loitering (must have history roughly equal to loitering_time)
        if len(history) > 5 and (current_time - history[0]["time"]) >= self.loitering_time:
            first_pos = history[0]["pos"]
            is_loitering = True
            
            # Check if all points since history[0] are within the radius
            # We only evaluate the span from current to history[0]? Actually just all points in history
            for h in history:
                dx = h["pos"]["x"] - first_pos["x"]
                dy = h["pos"]["y"] - first_pos["y"]
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > self.loitering_radius:
                    is_loitering = False
                    break
                    
            if is_loitering:
                if not self._is_cooldown(u_id, "Loitering", current_time):
                    self._set_cooldown(u_id, "Loitering", current_time)
                    return {
                        "id": u_id,
                        "obj_type": obj_type,
                        "event_type": "Loitering",
                        "timestamp": current_time,
                        "details": f"Stationary for {int(current_time - history[0]['time'])}s"
                    }

        return None

    def _is_cooldown(self, u_id, event_type, current_time):
        key = f"{u_id}_{event_type}"
        if key in self.last_triggers:
            if current_time - self.last_triggers[key] < 10.0: # 10s cooldown
                return True
        return False
        
    def _set_cooldown(self, u_id, event_type, current_time):
        key = f"{u_id}_{event_type}"
        self.last_triggers[key] = current_time
