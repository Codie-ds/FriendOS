import requests
import json
from bson import ObjectId
from pymongo import MongoClient

# 1. Create Learner
print("Creating Learner...")
r = requests.post("http://127.0.0.1:8000/api/onboard", json={
    "name": "Dev", "learning_goal": "Learn Python", "known_topics": [], "weak_topics": []
})
learner_id = r.json()["learner_id"]

# 2. Upload Material
print("Uploading Material...")
with open("test_python.pdf", "rb") as f:
    r = requests.post("http://127.0.0.1:8000/api/material/upload", files={"file": f})
material_id = r.json()["material_id"]
topic = r.json()["topics"][0]["name"]
print(f"Topic: {topic}")

# 3. Inject Bad Behavior directly to MongoDB to simulate struggle
print("Injecting poor performance...")
client = MongoClient("mongodb://localhost:27017")
db = client["friendos"]
db.learners.update_one({"_id": ObjectId(learner_id)}, {"$set": {"skill_profile": {topic: 0.25}}})
for i in range(5):
    db.learning_events.insert_one({
        "learner_id": learner_id, "session_id": "dummy", "material_id": material_id,
        "topic": topic, "question_id": f"q{i}", "event_type": "answer",
        "is_correct": False, "attempt_number": 1, "time_taken_seconds": 45.0,
        "hint_requested": True, "skipped": False
    })

# 4. Get Recommendation (Expected: PRACTICE_EASY or REVIEW_CONCEPT)
print("Requesting Recommendation 1...")
r = requests.post("http://127.0.0.1:8000/api/adaptive/recommend", json={
    "learner_id": learner_id, "material_id": material_id
})
print(json.dumps(r.json(), indent=2))

# 5. Inject Good Behavior
print("Injecting excellent performance...")
db.learners.update_one({"_id": ObjectId(learner_id)}, {"$set": {"skill_profile": {topic: 0.95}}})
for i in range(5):
    db.learning_events.insert_one({
        "learner_id": learner_id, "session_id": "dummy2", "material_id": material_id,
        "topic": topic, "question_id": f"q{i+5}", "event_type": "answer",
        "is_correct": True, "attempt_number": 1, "time_taken_seconds": 5.0,
        "hint_requested": False, "skipped": False
    })

# 6. Get Recommendation (Expected: MOVE_TO_NEXT_TOPIC or PRACTICE_HARD)
print("Requesting Recommendation 2...")
r = requests.post("http://127.0.0.1:8000/api/adaptive/recommend", json={
    "learner_id": learner_id, "material_id": material_id
})
print(json.dumps(r.json(), indent=2))
