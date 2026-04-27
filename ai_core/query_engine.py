import json
import re
import os
from groq import Groq

class QueryEngine:
    def __init__(self, db_path="database.json"):
        self.db_path = db_path
        self.api_key = "your_api_key"
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
            self.model_name = 'llama-3.3-70b-versatile'

    def load_db(self):
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except:
            return {}

    def load_suspicious_db(self):
        try:
            with open('data/suspicious_events.json', 'r') as f:
                return json.load(f)
        except:
            return {}

    def get_summary_context(self):
        """ Creates a minified string of the DB for the LLM to read without blowing up context window """
        db = self.load_db()
        items = []
        vehicles = db.get("vehicles", []) if isinstance(db, dict) else []
        for v in vehicles:
             items.append(
                 f"ID: {v['vehicle_id']}, Type: {v.get('type', 'vehicle')}, "
                 f"Color: {v.get('color', 'N/A')}, "
                 f"Plate: {v.get('plate', 'N/A')}"
             )
             
        s_db = self.load_suspicious_db()
        events = s_db.get("events", []) if isinstance(s_db, dict) else []
        if events:
            items.append("\n--- SUSPICIOUS EVENTS LOG ---")
            for e in events:
                target = e.get('vehicle_id') or e.get('person_id') or 'Unknown'
                items.append(
                    f"Event: {e.get('event_type')}, Target ID: {target}, "
                    f"Risk: {e.get('risk_level')}, Time: {e.get('start_time')}, "
                    f"Reasons: {', '.join(e.get('reasons', []))}"
                )
                
        return "\n".join(items)

    def extract_attributes_fallback(self, text):
        """ Legacy logic if no API key """
        text = text.lower()
        extracted = {}
        colors = ["red", "green", "blue", "black", "white", "silver", "gray", "yellow", "unknown"]
        types = ["car", "truck", "bus", "motorcycle", "person", "vehicle"]
        for c in colors:
            if c in text: extracted["color"] = c
        for t in types:
            if t in text: extracted["type"] = t
        return extracted

    def fallback_query(self, text):
        db = self.load_db()
        vehicles = db.get("vehicles", []) if isinstance(db, dict) else []
        if not vehicles:
            return {"response_text": "The database is empty.", "results": []}
            
        text_lower = text.lower()
        
        # Simple count check
        if "total" in text_lower or "how many" in text_lower:
            count = len(vehicles)
            return {"response_text": f"There are {count} total objects detected in the system history.", "results": []}
            
        attrs = self.extract_attributes_fallback(text)
        if not attrs:
             # sorting vehicles is a bit trickier since last_seen is a string format now, but we can just reverse
             return {"response_text": "Here are the most recent detections:", "results": vehicles[::-1][:5]}
             
        results = []
        for data in vehicles:
            score = 0
            t = attrs.get('type')
            is_vehicle = data.get('type') != 'person'
            is_person = data.get('type') == 'person'
            v_type = data.get('type', '')
            
            if t:
                if t == 'person' and is_person: score += 5
                elif t == 'vehicle' and is_vehicle: score += 2
                elif t == v_type: score += 5
                else: score -= 5
                
            c = attrs.get('color')
            if c and c == data.get('color'): score += 3
            
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
        vehicles = db.get("vehicles", []) if isinstance(db, dict) else []
        context = self.get_summary_context()
        
        prompt = f"""
        You are an AI Search Assistant connected to a CCTV tracking database.
        Below is the current record of objects detected in the video, alongside a log of any Suspicious Events detected:
        
        {context}
        
        The user just asked: "{user_text}"
        
        Task:
        1. Parse the user's intent. If they are asking for a count, count the matches exactly!
        2. Format your response back as a RAW JSON string strictly with no markdown wrappers containing two fields:
           - "response_text": A highly detailed and professional forensic analysis response. Do NOT be brief. For each suspicious activity or object found, explicitly provide: 1) The exact timestamp/frame period, 2) The Risk Level (High/Medium/Low), and 3) A clear, multi-sentence explanation of why it was flagged. Present this information in a clear, structured way that is easy for a security operator to read. If multiple matches exist, discuss the most critical ones first.
           - "target_ids": A list of ID strings that match. CRITICAL RULE: If you reference any suspicious event or specific object, you MUST find its Target ID and include it in this list. This is mathematically required so the frontend UI can display the snapshot image. If you just ask for a count, return an empty list [].
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
            
            vehicles_list = db.get("vehicles", []) if isinstance(db, dict) else []
            v_dict = {v["vehicle_id"]: v for v in vehicles_list if "vehicle_id" in v}
            
            result_datas = []
            for uid in ids:
                if uid in v_dict:
                    result_datas.append(v_dict[uid])
                    
            return {
                "response_text": reply_text,
                "results": result_datas
            }
            
        except Exception as e:
            print("LLM Error:", e)
            return self.fallback_query(user_text)
