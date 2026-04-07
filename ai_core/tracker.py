from deep_sort_realtime.deepsort_tracker import DeepSort

class ObjectTracker:
    def __init__(self):
        # We initialize DeepSort with a max_age to keep tracks alive for a bit
        # when they are occluded.
        self.tracker = DeepSort(
            max_age=30,
            n_init=3,
            nms_max_overlap=1.0,
            max_cosine_distance=0.2, # We will do our own ResNet metric learning ReID outside if needed, this is bounding box tracker
        )

    def update(self, detections, frame):
        """
        Takes detections from YOLO and updates tracks.
        detections format MUST be: [ ([left,top,w,h], confidence, detection_class) ]
        Returns tracks.
        """
        tracks = self.tracker.update_tracks(detections, frame=frame)
        active_tracks = []
        for track in tracks:
            if not track.is_confirmed() or track.time_since_update > 1:
                continue
            
            # format [ltrb, track_id, class_id]
            ltrb = track.to_ltrb() # Left Top Right Bottom
            track_id = track.track_id
            class_id = track.get_det_class()
            
            active_tracks.append({
                "id": track_id,
                "bbox": [int(x) for x in ltrb],
                "class_id": class_id
            })
            
        return active_tracks
