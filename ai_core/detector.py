from ultralytics import YOLO
import cv2
import numpy as np

class ObjectDetector:
    def __init__(self, model_path='yolov8s.pt'):
        try:
            # Upgrade to the 'small' model (yolov8s) to significantly improve person detection accuracy
            self.model = YOLO(model_path)
            # YOLOv8 classes: 0: person, 2: car, 3: motorcycle, 5: bus, 7: truck
            self.target_classes = [0, 2, 3, 5, 7]
        except Exception as e:
            print(f"Failed to load YOLO model: {e}")
            self.model = None

    def track(self, frame):
        """
        Detect and Track vehicles/persons using YOLOv8 built-in ByteTrack.
        Returns a list of tracked objects: {"id": track_id, "bbox": [x1, y1, x2, y2], "class_id": cls, "conf": conf}
        """
        if self.model is None:
            return []
            
        # persist=True keeps tracking state across frames. tracker="bytetrack.yaml" uses ByteTrack.
        results = self.model.track(frame, classes=self.target_classes, persist=True, tracker="bytetrack.yaml", verbose=False)
        tracked_objects = []
        
        for r in results:
            boxes = r.boxes
            if boxes.id is not None:
                track_ids = boxes.id.cpu().numpy().astype(int)
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0].cpu().numpy())
                    cls_id = int(box.cls[0].cpu().numpy())
                    track_id = track_ids[i]
                    
                    tracked_objects.append({
                        "id": track_id,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "class_id": cls_id,
                        "conf": conf
                    })
                
        return tracked_objects

    def get_class_name(self, class_id):
        names = {
            0: 'person',
            2: 'car',
            3: 'motorcycle',
            5: 'bus',
            7: 'truck'
        }
        return names.get(class_id, 'unknown')
