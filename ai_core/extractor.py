import cv2
import numpy as np
import torch
import torchvision.transforms as transforms
from torchvision.models import resnet50, ResNet50_Weights
from sklearn.cluster import KMeans
import pytesseract
import math

class FeatureExtractor:
    def __init__(self):
        # Setup ResNet50 for Embeddings
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load pre-trained ResNet50 model
        weights = ResNet50_Weights.DEFAULT
        self.model = resnet50(weights=weights)
        
        # Remove the classification layer to just get embeddings
        self.model = torch.nn.Sequential(*list(self.model.children())[:-1])
        self.model = self.model.to(self.device).eval()
        
        self.preprocess = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])

    def get_embedding(self, image_crop):
        """
        Returns ResNet50 feature vector for a cropped image
        """
        if image_crop is None or image_crop.size == 0:
            return np.zeros(2048).tolist()
            
        try:
            # Convert OpenCV image (BGR) to RGB
            rgb_image = cv2.cvtColor(image_crop, cv2.COLOR_BGR2RGB)
            input_tensor = self.preprocess(rgb_image)
            input_batch = input_tensor.unsqueeze(0).to(self.device)

            with torch.no_grad():
                features = self.model(input_batch)
                
            # Flatten to 1D vector and convert to list
            embedding = features.squeeze().cpu().numpy().tolist()
            return embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            return np.zeros(2048).tolist()

    def get_dominant_color(self, image_crop, k=3):
        """
        Uses KMeans clustering to find the dominant color naming.
        """
        if image_crop is None or image_crop.size == 0:
            return "unknown"
            
        try:
            # Crop to center 50% to ignore background (road, grass, etc)
            h, w = image_crop.shape[:2]
            cx1, cy1 = w // 4, h // 4
            cx2, cy2 = w - w // 4, h - h // 4
            
            center_crop = image_crop[cy1:cy2, cx1:cx2]
            if center_crop.size == 0:
                center_crop = image_crop
                
            # Resize image to speed up clustering
            small_image = cv2.resize(center_crop, (64, 64))
            small_image = cv2.cvtColor(small_image, cv2.COLOR_BGR2RGB)
            
            # Reshape the image to be a list of pixels
            pixels = small_image.reshape((-1, 3))
            
            # Cluster the pixels
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            # Get the most common cluster center
            counts = np.bincount(kmeans.labels_)
            dominant_color = kmeans.cluster_centers_[np.argmax(counts)]
            
            return self._rgb_to_name(dominant_color)
        except Exception as e:
            print(f"Color extraction error: {e}")
            return "unknown"

    def _rgb_to_name(self, rgb):
        # A simple color closest-match map
        colors = {
            "red": (255, 0, 0),
            "dark red": (139, 0, 0),
            "green": (0, 255, 0),
            "dark green": (0, 100, 0),
            "blue": (0, 0, 255),
            "dark blue": (0, 0, 139),
            "light blue": (173, 216, 230),
            "black": (30, 30, 30), # Shifted slightly from 0,0,0
            "white": (245, 245, 245),
            "silver": (192, 192, 192),
            "gray": (128, 128, 128),
            "yellow": (255, 255, 0),
            "orange": (255, 140, 0),
            "purple": (128, 0, 128),
            "brown": (165, 42, 42),
            "pink": (255, 192, 203)
        }
        
        r, g, b = rgb
        min_dist = float('inf')
        closest_color = "unknown"
        
        for name, (cr, cg, cb) in colors.items():
            dist = math.sqrt((r - cr)**2 + (g - cg)**2 + (b - cb)**2)
            if dist < min_dist:
                min_dist = dist
                closest_color = name
                
        return closest_color

    def get_number_plate(self, image_crop):
        """
        Uses Tesseract to read text from crop
        Assuming Tesseract is installed and in PATH
        """
        if image_crop is None or image_crop.size == 0:
            return ""
            
        try:
            gray = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
            # Basic preprocessing
            gray = cv2.bilateralFilter(gray, 11, 17, 17)
            # Thresholding
            _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            
            text = pytesseract.image_to_string(binary, config='--psm 8')
            clean_text = ''.join(char for char in text if char.isalnum())
            return clean_text if len(clean_text) >= 4 else ""
        except Exception as e:
            print(f"OCR error: {e}")
            return ""
