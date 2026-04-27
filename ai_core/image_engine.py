import cv2
import os
import json
import numpy as np

class ImageEngine:
    def __init__(self, data_dir='data', img_dir='data/images', metadata_path='data/image_metadata.json'):
        self.img_dir = img_dir
        self.metadata_path = metadata_path
        
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(img_dir, exist_ok=True)
        
        self.metadata = {"images": []}
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r') as f:
                    content = json.load(f)
                    if "images" in content:
                        self.metadata = content
            except Exception as e:
                print(f"Error loading image metadata: {e}")

    def calculate_sharpness(self, image):
        """Calculate composite quality score. Factor in sharpness and resolution."""
        try:
            h, w = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            variance = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Sharpness score (max 100)
            sharpness = min(variance / 15.0, 100)
            
            # Resolution score (normalized against 400x400 as high quality baseline)
            resolution = min((w * h) / (400 * 400) * 100, 100)
            
            # Composite: 60% Sharpness, 40% Resolution weight
            composite_score = int((sharpness * 0.6) + (resolution * 0.4))
            
            # Penalize very small images
            if w < 30 or h < 30:
                composite_score = int(composite_score * 0.3)
                
            return max(10, composite_score)
        except:
            return 50

    def save_image(self, crop, prefix, current_time):
        """
        Saves a cropped image frame. Overwrites existing best image to save space.
        Returns relative path
        """
        if crop is None or crop.size == 0:
            return None
            
        file_name = f"{prefix}_best.jpg"
        full_path = os.path.join(self.img_dir, file_name)
        relative_path = f"images/{file_name}"
        
        # Save real image
        cv2.imwrite(full_path, crop)
        
        return relative_path

    def save_metadata(self):
        with open(self.metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=4)
