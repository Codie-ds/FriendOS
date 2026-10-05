import requests
import json
from bson import ObjectId
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["friendos"]

# Get any material
mat = db.learning_materials.find_one()
if not mat:
    print("NO MATERIAL FOUND IN DB!")
    exit(1)

material_id = str(mat["_id"])
topic = mat["topics"][0]["name"] if mat.get("topics") else "test_topic"

# 1. Create Learner
print("Creating Learner...")
r = requests.post("http://127.0.0.1:8000/api/onboard", json={
    "name": "Dev", "learning_goal": "Learn Python", "known_topics": [], "weak_topics": []
})
learner_id = r.json()["learner_id"]
print(f"Learner ID: {learner_id}, Material ID: {material_id}, Topic: {topic}")

# 2. Inject Bad Behavior directly to MongoDB
print("Injecting poor performance...")
db.learners.update_one({"_id": ObjectId(learner_id)}, {"$set": {"skill_profile": {topic: 0.25}}})
for i in range(5):
    db.learning_events.insert_one({
        "learner_id": learner_id, "session_id": "dummy", "material_id": material_id,
        "topic": topic, "question_id": f"q{i}", "event_type": "answer",
        "is_correct": False, "attempt_number": 1, "time_taken_seconds": 45.0,
        "hint_requested": True, "skipped": False
    })

# 3. Get Recommendation 1
print("Requesting Recommendation 1...")
r = requests.post("http://127.0.0.1:8000/api/adaptive/recommend", json={
    "learner_id": learner_id, "material_id": material_id
})
print(json.dumps(r.json(), indent=2))

# 4. Inject Good Behavior
print("Injecting excellent performance...")
db.learners.update_one({"_id": ObjectId(learner_id)}, {"$set": {"skill_profile": {topic: 0.95}}})
for i in range(5):
    db.learning_events.insert_one({
        "learner_id": learner_id, "session_id": "dummy2", "material_id": material_id,
        "topic": topic, "question_id": f"q{i+5}", "event_type": "answer",
        "is_correct": True, "attempt_number": 1, "time_taken_seconds": 5.0,
        "hint_requested": False, "skipped": False
    })

# 5. Get Recommendation 2
print("Requesting Recommendation 2...")
r = requests.post("http://127.0.0.1:8000/api/adaptive/recommend", json={
    "learner_id": learner_id, "material_id": material_id
})
print(json.dumps(r.json(), indent=2))
