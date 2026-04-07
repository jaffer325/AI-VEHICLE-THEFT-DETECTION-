import json
import re
import os
from groq import Groq

class QueryEngine:
    def __init__(self, db_path="database.json"):
        self.db_path = db_path
        self.api_key = "GROQ_API_KEY"
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
            self.model_name = 'llama-3.3-70b-versatile'

    def load_db(self):
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except:
            return {}

    def get_summary_context(self):
        """ Creates a minified string of the DB for the LLM to read without blowing up context window """
        db = self.load_db()
        items = []
        for v in db.values():
             items.append(
                 f"ID: {v['id']}, Type: {v.get('vehicle_type', v.get('type'))}, "
                 f"Color: {v.get('color', 'N/A')}, "
                 f"Plate: {v.get('plate_number', 'N/A')}, "
                 f"Motion/Direction: {v.get('velocity', {}).get('direction', 'unknown')}"
             )
        return "\n".join(items)

    def extract_attributes_fallback(self, text):
        """ Legacy logic if no API key """
        text = text.lower()
        extracted = {}
        colors = ["red", "green", "blue", "black", "white", "silver", "gray", "yellow", "unknown"]
        types = ["car", "truck", "bus", "motorcycle", "person", "vehicle"]
        directions = ["right", "left", "up", "down", "stationary"]
        for c in colors:
            if c in text: extracted["color"] = c
        for t in types:
            if t in text: extracted["type"] = t
        for d in directions:
            if d in text: extracted["direction"] = d
        return extracted

    def fallback_query(self, text):
        db = self.load_db()
        if not db:
            return {"response_text": "The database is empty.", "results": []}
            
        text_lower = text.lower()
        
        # Simple count check
        if "total" in text_lower or "how many" in text_lower:
            count = len(db)
            return {"response_text": f"There are {count} total objects detected in the system history.", "results": []}
            
        attrs = self.extract_attributes_fallback(text)
        if not attrs:
             sorted_items = sorted(db.values(), key=lambda x: x.get('last_seen', 0), reverse=True)
             return {"response_text": "Here are the most recent detections:", "results": sorted_items[:5]}
             
        results = []
        for uid, data in db.items():
            score = 0
            t = attrs.get('type')
            is_vehicle = data.get('type') == 'vehicle'
            is_person = data.get('type') == 'person'
            v_type = data.get('vehicle_type', '')
            
            if t:
                if t == 'person' and is_person: score += 5
                elif t == 'vehicle' and is_vehicle: score += 2
                elif t == v_type: score += 5
                else: score -= 5
                
            c = attrs.get('color')
            if c and c == data.get('color'): score += 3

            d = attrs.get('direction')
            if d and 'velocity' in data and data['velocity'].get('direction') == d: score += 2
            
            if score > 0:
                results.append({"score": score, "data": data})
                
        results.sort(key=lambda x: x['score'], reverse=True)
        final = [r['data'] for r in results[:5]]
        
        return {
            "response_text": f"I found {len(final)} matches based on your fallback request.",
            "results": final
        }

    def query(self, user_text):
        if not self.api_key:
            return self.fallback_query(user_text)

        db = self.load_db()
        context = self.get_summary_context()
        
        prompt = f"""
        You are an AI Search Assistant connected to a CCTV tracking database.
        Below is the current record of objects detected in the video:
        
        {context}
        
        The user just asked: "{user_text}"
        
        Task:
        1. Parse the user's intent. If they are asking for a count, count the matches exactly!
        2. Format your response back as a RAW JSON string strictly with no markdown wrappers containing two fields:
           - "response_text": A verbose, conversational, and highly descriptive response answering their query natively. Detail exactly what you found using human-friendly, understandable language. Mention attributes like color, vehicle type, and direction explicitly. Be actively helpful and explanatory (e.g., "I analyzed the footage and found 2 vehicles matching your description. Specifically, there is a red car moving right, and a dark blue truck."). 
           - "target_ids": A list of ID strings that match. If they ask a general question that returns specific matches, provide the top 5 IDs so images can be shown. If they just ask for a count, return an empty list [].
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            # Remove any markdown JSON wrappers just in case
            cleaned = response.choices[0].message.content.replace('```json', '').replace('```', '').strip()
            parsed = json.loads(cleaned)
            
            reply_text = parsed.get("response_text", "Here is the result:")
            ids = parsed.get("target_ids", [])
            
            result_datas = []
            for uid in ids:
                if uid in db:
                    result_datas.append(db[uid])
                    
            return {
                "response_text": reply_text,
                "results": result_datas
            }
            
        except Exception as e:
            print("LLM Error:", e)
            return self.fallback_query(user_text)
