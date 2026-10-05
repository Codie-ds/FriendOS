"""
Phase 5 Behavioral Verification — Scenario B retry with extended timeout.
No production files are modified.
"""

import time
import json
import os
import sys
import requests
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGODB_URI")
BASE_URL = "http://127.0.0.1:8000"
TOPIC = "Python Characteristics"

# Reuse the SAME learner + material from Scenario A run
LEARNER_ID = "6ac2e76b3c37456f53ac0742"
MATERIAL_ID = "6ac2e76baa827d1693d0e356"

db = MongoClient(MONGO_URI)["friendos"]


def call_recommend(learner_id, material_id, timeout=180, retries=2):
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(
                f"{BASE_URL}/api/adaptive/recommend",
                json={"learner_id": learner_id, "material_id": material_id},
                timeout=timeout,
            )
            if r.status_code == 200:
                return r.json()
            print(f"  ⚠️  HTTP {r.status_code} on attempt {attempt}. Body: {r.text[:200]}")
        except requests.exceptions.ReadTimeout:
            print(f"  ⚠️  Timeout on attempt {attempt}/{retries}. Waiting 10s before retry…")
            if attempt < retries:
                time.sleep(10)
    return None


def check_no_psych_claims(text):
    banned = ["lazy", "unmotivated", "hates", "cannot concentrate", "not motivated", "bad student"]
    return not any(w in text.lower() for w in banned)


# ══════════════════════════════════════════════════════════════════════
# SCENARIO B — Strong evidence
# ══════════════════════════════════════════════════════════════════════

print("=" * 60)
print("SCENARIO B — Strong Learner Evidence (Retry)")
print("=" * 60)

scenario_b_skill = {TOPIC: 0.93}
scenario_b_events = [
    {"session_id": "sB", "question_id": "q6",  "is_correct": True, "attempt_number": 1, "time_taken_seconds": 7.0,  "hint_requested": False},
    {"session_id": "sB", "question_id": "q7",  "is_correct": True, "attempt_number": 1, "time_taken_seconds": 5.0,  "hint_requested": False},
    {"session_id": "sB", "question_id": "q8",  "is_correct": True, "attempt_number": 1, "time_taken_seconds": 9.0,  "hint_requested": False},
    {"session_id": "sB", "question_id": "q9",  "is_correct": True, "attempt_number": 1, "time_taken_seconds": 6.0,  "hint_requested": False},
    {"session_id": "sB", "question_id": "q10", "is_correct": True, "attempt_number": 1, "time_taken_seconds": 8.0,  "hint_requested": False},
]

print(f"\n  Learner ID  : {LEARNER_ID}")
print(f"  Material ID : {MATERIAL_ID}")
print(f"  Topic       : {TOPIC}")
print(f"\nInput Evidence:")
print(f"  skill_profile : {scenario_b_skill}")
print(f"  events        : {len(scenario_b_events)} answers, all correct")
print(f"  hints         : 0 hints requested")
print(f"  avg time      : {sum(e['time_taken_seconds'] for e in scenario_b_events)/len(scenario_b_events):.1f}s")

# Inject into DB
db.learners.update_one({"_id": ObjectId(LEARNER_ID)}, {"$set": {"skill_profile": scenario_b_skill}})
docs = []
for e in scenario_b_events:
    docs.append({
        "learner_id": LEARNER_ID, "session_id": e["session_id"],
        "material_id": MATERIAL_ID, "topic": TOPIC,
        "question_id": e["question_id"], "event_type": "answer",
        "is_correct": e["is_correct"], "attempt_number": e["attempt_number"],
        "time_taken_seconds": e["time_taken_seconds"],
        "hint_requested": e["hint_requested"], "skipped": False,
    })
db.learning_events.insert_many(docs)

recs_before = db.adaptive_recommendations.count_documents({"learner_id": LEARNER_ID})

print(f"\nCalling /api/adaptive/recommend (timeout=180s, retries=2)…")
rec_b = call_recommend(LEARNER_ID, MATERIAL_ID)

recs_after = db.adaptive_recommendations.count_documents({"learner_id": LEARNER_ID})

if rec_b is None:
    print("❌ Scenario B failed after all retries (Gemma API unavailable).")
    sys.exit(1)

print("\nScenario B — Recommendation:")
print(json.dumps(rec_b, indent=2))

no_psych = check_no_psych_claims(
    rec_b["recommendation"]["reason"] + " " + rec_b["recommendation"]["activity"]
)
print(f"\n  Psychological claims absent : {'✅ YES' if no_psych else '❌ NO — PROBLEM'}")
print(f"  Persisted in DB            : {'✅ YES' if recs_after > recs_before else '❌ NO'}")

# ── Adaptation Check ─────────────────────────────────────────────────
SCENARIO_A_TYPE = "REVIEW_CONCEPT"
SCENARIO_A_DIFF = "beginner"

type_b = rec_b["recommendation"]["recommendation_type"]
diff_b = rec_b["recommendation"]["difficulty"]
adapted = (SCENARIO_A_TYPE != type_b) or (SCENARIO_A_DIFF != diff_b)

print("\n" + "=" * 60)
print("ADAPTATION CHECK")
print("=" * 60)
print(f"\n  Scenario A : {SCENARIO_A_TYPE} / {SCENARIO_A_DIFF}")
print(f"  Scenario B : {type_b} / {diff_b}")
print(f"  Adapted    : {'✅ YES' if adapted else '⚠️  SAME TYPE — check reason text'}")
if not adapted:
    print(f"  Reason B   : {rec_b['recommendation']['reason']}")

total = db.adaptive_recommendations.count_documents({"learner_id": LEARNER_ID})
print(f"\n  Total recommendations persisted for this learner : {total}")
print(f"  Expected ≥ 2 : {'✅' if total >= 2 else '❌'}")
print("\n" + "=" * 60)
print("Scenario B verification complete.")
print("=" * 60)
