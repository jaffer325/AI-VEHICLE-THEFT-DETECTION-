import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import uuid
import math

class ReIdentificator:
    def __init__(self, similarity_threshold=0.85):
        """
        Similarity threshold for ResNet embeddings. 
        Higher means stricter match.
        """
        self.similarity_threshold = similarity_threshold
        # Stores final Re-ID metrics: { "reid_uuid": { ... metadata } }
        self.database = {}
        # Maps temporal track_id to our permanent uuid
        self.track_to_uuid = {}

    def get_or_create_id(self, track_id, class_name, embedding, bbox=None):
        """
        Matches the current track's embedding to existing instances in the database.
        Returns a unique UUID.
        """
        if track_id in self.track_to_uuid:
            return self.track_to_uuid[track_id]

        if not embedding or np.all(np.array(embedding) == 0):
            new_id = f"{uuid.uuid4().hex[:8]}"
            self.track_to_uuid[track_id] = new_id
            return new_id

        best_match_id = None
        highest_sim = -1

        emb_array = np.array(embedding).reshape(1, -1)

        for uid, data in self.database.items():
            is_both_person = (class_name == 'person') and (data.get('vehicle_type') == 'person')
            is_both_vehicle = (class_name != 'person') and (data.get('vehicle_type') != 'person')
            
            if not (is_both_person or is_both_vehicle):
                continue
                
            db_emb = np.array(data['embedding']).reshape(1, -1)
            if db_emb.shape[1] != emb_array.shape[1] or np.all(db_emb == 0):
                continue
                
            sim = cosine_similarity(emb_array, db_emb)[0][0]
            if sim > highest_sim:
                highest_sim = sim
                best_match_id = uid

        if highest_sim >= self.similarity_threshold and best_match_id is not None:
            self.track_to_uuid[track_id] = best_match_id
            return best_match_id
        
        # Create a clean new UUID
        new_id = f"{uuid.uuid4().hex[:8]}"
        self.track_to_uuid[track_id] = new_id
        return new_id

    def update_database(self, u_id, attribute_dict):
        """
        Update the structured attributes for a specific UUID.
        """
        if u_id not in self.database: # New Object
            self.database[u_id] = attribute_dict
            self.database[u_id]['embedding_count'] = 1 if attribute_dict.get('embedding') else 0
        else: # Update Existing Object
            current = self.database[u_id]
            current['last_seen'] = attribute_dict.get('last_seen', current.get('last_seen'))
            
            # Robust Embedding Averaging! 
            # This prevents identity drifting by accumulating a generalized appearance model
            if attribute_dict.get('embedding') and sum(attribute_dict['embedding']) != 0:
                old_emb = np.array(current['embedding'])
                new_emb = np.array(attribute_dict['embedding'])
                count = current.get('embedding_count', 1)
                
                # Rolling Mean Implementation
                avg_emb = ((old_emb * count) + new_emb) / (count + 1)
                
                current['embedding'] = avg_emb.tolist()
                current['embedding_count'] = count + 1
            
            # Discarded dense tracking memory logic for performance
            
            if not current.get('first_image') and attribute_dict.get('first_image'):
                 current['first_image'] = attribute_dict['first_image']
                 
            if attribute_dict.get('position'):
                current['position'] = attribute_dict['position']
            if attribute_dict.get('velocity'):
                current['velocity'] = attribute_dict['velocity']
                
            if attribute_dict.get('plate_number') and not current.get('plate_number'):
                 current['plate_number'] = attribute_dict['plate_number']
                 
            self.database[u_id] = current
