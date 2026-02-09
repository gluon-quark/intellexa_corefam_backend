# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Body, Header
from fastapi.encoders import jsonable_encoder
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import uvicorn
from models import Event, QueryModel, LoginRequest
from passlib.hash import bcrypt
from bson import ObjectId
from datetime import datetime
from collections import defaultdict
import base64
import hashlib
import random
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify ["http://localhost:4200"] for Angular
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
client = MongoClient("mongodb+srv://alfredsam2006:3yQ8LH2sweEt5I0K@cluster0.15hi2x0.mongodb.net/?appName=Cluster0")  # or your MongoDB Atlas URI
db = client.Intellexa  
events = db.events  
users_collection = db.users
queries_collection = db.queries
stats_collection = db.stats

TEAM_COLORS = {
    "AI": "from-indigo-500 to-purple-500",
    "App": "from-pink-500 to-rose-500",
    "Web": "from-pink-500 to-rose-500",
    "Content": "from-amber-500 to-orange-500",
    "IOT": "from-green-500 to-emerald-500",
    "Design": "from-fuchsia-500 to-pink-500",
    "Media": "from-pink-500 to-rose-500",
    "Event": "from-red-500 to-rose-500",
    "Backend": "from-indigo-500 to-purple-500",      
    "Info Sec": "from-pink-500 to-rose-500",        
    "Intellexa": "from-blue-500 to-cyan-500",      
}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed



AUTH_CACHE = {}

def key_match(role:str,team:str,passkey: str):
    # Check cache first
    if passkey in AUTH_CACHE:
        cached = AUTH_CACHE[passkey]
        if cached["role"] == role and cached["team"] == team:
            return True
            
    try:
        user = users_collection.find_one({"passkey": passkey,"role":role,"team":team})
        if user:
            # Cache the successful result
            AUTH_CACHE[passkey] = {"role": role, "team": team}
            return True
    except Exception as e:
        raise HTTPException(status_code=403, detail="Invalid credentials")




@app.get("/")
def home():
    return {"message": "MongoDB connected successfully"}

@app.post("/login")
async def login(payload: LoginRequest):
    email = payload.email
    password = payload.password
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email")
    else:
        if not verify_password(password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid password")
        
        if user["role"]=="Yet to be set" or user["team"]=="Yet to be set":
            raise HTTPException(status_code=401, detail="Login not approved yet, contact admin to set role and team")
        
        passkey = "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/()[]", k=16))
        users_collection.update_one({"email": email}, {"$set": {"passkey": passkey}})
    
        return {"message": "Login successful", "user": {
            "role": user["role"],
            "team": user["team"],
            "name": user["name"],
            "passkey":  passkey
        }}
    

@app.post("/logout")
async def login(passkey:str):
    user = users_collection.find_one({"passkey": passkey})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid key")
    
    # Invalidate cache
    if passkey in AUTH_CACHE:
        del AUTH_CACHE[passkey]
        
    users_collection.update_one({"passkey": passkey}, {"$set": {"passkey": "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/()[]", k=8))}})
    return {"message": "Logout successful"}
    

@app.post("/createaccount")
async def create_account(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    birthdate: Optional[str] = Form(None),
    linkedin: Optional[str] = Form(None),
    github: Optional[str] = Form(None),
    instagram: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    registerNumber: Optional[str] = Form(None),
    profilePhoto: Optional[UploadFile] = File(None)
):
    # Check if email already exists
    if users_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user_data = {
        "name": name,
        "email": email,
        "password": hash_password(password),
        "birthdate": birthdate,
        "team":"Yet to be set",
        "role":"Yet to be set",
        "linkedin": linkedin,
        "github": github,
        "instagram": instagram,
        "department": department,
        "year": year,
        "registerNumber": registerNumber,
        "key": "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/()[]", k=16))
    }

    # Convert uploaded file to base64
    if profilePhoto:
        contents = await profilePhoto.read()
        user_data["profilePhoto"] = base64.b64encode(contents).decode("utf-8")

    result = users_collection.insert_one(user_data)
    return {"message": "User created successfully", "user_id": str(result.inserted_id)}


def serialize_user(user):
    user["_id"] = str(user["_id"])
    user.pop("password", None)  # remove password hash
    return user


@app.get("/users")
async def get_all_users(x_user: Optional[str] = Header(None)):
    try:
        user_info = json.loads(x_user) if x_user else None
        if user_info and key_match(user_info["role"], user_info["team"], user_info["passkey"]):

            users = list(users_collection.find())
            if not users:
                raise HTTPException(status_code=404, detail="No users found")
            serialized_users = [serialize_user(u) for u in users]
            return {"total_users": len(serialized_users), "users": serialized_users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/user/{id}")
async def update_user(id: str, data: dict = Body(...)):
    """
    Updates a user's role and team based on ID.
    Example body: { "role": "Lead", "team": "Development" }
    """
    user = users_collection.find_one({"_id": ObjectId(id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_fields = {}
    if "role" in data:
        update_fields["role"] = data["role"]
    if "team" in data:
        update_fields["team"] = data["team"]

    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields provided")

    users_collection.update_one({"_id": ObjectId(id)}, {"$set": update_fields})

    updated_user = users_collection.find_one({"_id": ObjectId(id)})
    return {"message": "User updated successfully", "user": serialize_user(updated_user)}


@app.delete("/del/user/{id}")
async def delete_user(id: str):
    """
    Deletes a user from the database based on ID.
    """
    result = users_collection.delete_one({"_id": ObjectId(id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": f"User with ID {id} deleted successfully"}


@app.get("/events")
async def get_events(x_user: Optional[str] = Header(None)):
    try:
        # Public access allowed, no auth check needed
        all_events = list(events.find({}))
        # Convert ObjectId to str
        for event in all_events:
            event["_id"] = str(event["_id"])
        return {"events": all_events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_event")
def add_event(event: Event):
    result = events.insert_one(event.dict())
    return {"message": "Event added successfully", "inserted_id": str(result.inserted_id)}

@app.put("/editevent/{id}")
def update_event(id: str, updated_data: Event):
    collection = db["events"]

    # verify event exists
    event = collection.find_one({"_id": ObjectId(id)})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # remove None values (only update submitted fields)
    update_dict = {
        k: v
        for k, v in updated_data.dict(exclude_unset=True).items()
        if v not in (None, "")
    }

    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields provided for update")

    result = collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": jsonable_encoder(update_dict)},
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No changes made")

    updated_event = collection.find_one({"_id": ObjectId(id)})
    updated_event["_id"] = str(updated_event["_id"])

    return {"message": "Event updated successfully", "data": updated_event}

@app.put("/suggest/{id}")
def suggest_event(id: str, data: dict = Body(...)):
    suggestion = data.get("suggestion")
    if not suggestion:
        raise HTTPException(status_code=400, detail="Suggestion text required")

    collection = db["events"]
    event = collection.find_one({"_id": ObjectId(id)})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Reuse same update logic from /editevent
    result = collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"suggestion": suggestion}},
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No changes made")

    updated_event = collection.find_one({"_id": ObjectId(id)})
    updated_event["_id"] = str(updated_event["_id"])
    return {"message": "Suggestion added successfully", "data": updated_event}



@app.post("/submit_query")
async def submit_query(
    name: str = Form(...),
    category: str = Form(...),
    message: str = Form(...)
):
    # Validate category
    allowed_categories = {"query", "help", "suggestion"}
    if category not in allowed_categories:
        raise HTTPException(status_code=400, detail="Invalid category")

    # Prepare data
    query_data = QueryModel(
        name=name,
        category=category,
        message=message,
        created_at=datetime.utcnow()
    ).dict()

    # Insert into DB
    result = queries_collection.insert_one(query_data)

    return {"message": "Query submitted successfully", "id": str(result.inserted_id)}

@app.get("/queries")
async def get_all_queries(x_user: Optional[str] = Header(None)):
    try:
        user_info = json.loads(x_user) if x_user else None
        if user_info and key_match(user_info["role"], user_info["team"], user_info["passkey"]):

            queries = list(queries_collection.find())
            for q in queries:
                q["_id"] = str(q["_id"])
                if "created_at" in q and isinstance(q["created_at"], datetime):
                    q["created_at"] = q["created_at"].isoformat()

            return {"queries": queries}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/address_query/{query_id}")
async def address_query(query_id: str, data: dict = Body(...)):
    solution = data.get("solution")
    addressed_by = data.get("addressed_by")

    if not solution or not addressed_by:
        raise HTTPException(status_code=400, detail="Missing fields")

    result = queries_collection.update_one(
        {"_id": ObjectId(query_id)},
        {
            "$set": {
                "solution": solution,
                "addressed_by": addressed_by,
                "addressed": True,
                "addressed_at": datetime.now(),
            }
        },
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Query not found")

    return {"message": "Query addressed successfully"}


@app.get("/stats/{team_name}")
async def get_team_stats(team_name: str):
    """
    Fetches the stats array for a given team (e.g. 'media')
    """
    team_data = stats_collection.find_one({"team": team_name})
    if not team_data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team_data["_id"] = str(team_data["_id"])
    return {"team": team_name, "stats": team_data.get("stat", [])}

@app.post("/stats/{team_name}/add")
async def add_team_stat(team_name: str, data: dict = Body(...)):
    """
    Adds a new entry to the 'stat' array for the specified team.
    Example body:
    {
        "month": "November",
        "year": 2025,
        "instagram": 1000,
        "linkedin": 700,
        "youtube": 500
    }
    """
    team = stats_collection.find_one({"team": team_name})
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Append the new stat entry
    result = stats_collection.update_one(
        {"team": team_name},
        {"$push": {"stat": jsonable_encoder(data)}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update stats")

    updated_team = stats_collection.find_one({"team": team_name})
    updated_team["_id"] = str(updated_team["_id"])
    return {"message": "Stat added successfully", "updated_data": updated_team}


@app.get("/events/count")
async def get_event_count():
    """Return total number of events in the database"""
    count = events.count_documents({})
    completed = events.count_documents({"status":"completed"})
    youtube = stats_collection.find_one({"team":"media"})["stat"][-1]["youtube"]
    insta = stats_collection.find_one({"team":"media"})["stat"][-1]["instagram"]
    linkedin = stats_collection.find_one({"team":"media"})["stat"][-1]["linkedin"]
    return {"total_events": count,"completed":completed,"youtube":youtube,"insta":insta,"linkedin":linkedin}


@app.get("/teams/stats")
def get_team_statistics():
    users_stats = list(users_collection.find({}, {"name": 1, "team": 1}))
    events_stats = list(events.find({}, {"proposed_by": 1}))


    # Count events per person
    event_count_by_user = defaultdict(int)
    for e in events_stats:
        if e.get("proposed_by"):
            event_count_by_user[e["proposed_by"]] += 1

    # Build teams map
    teams_map = defaultdict(lambda: {
        "name": "",
        "totalEvents": 0,
        "members": [],
        "color": ""
    })

    for u in users_stats:
        team_name = u.get("team")
        user_name = u.get("name")

        if team_name not in TEAM_COLORS:
            continue  # unknown team → skip or handle differently

        teams_map[team_name]["name"] = team_name
        teams_map[team_name]["color"] = TEAM_COLORS[team_name]

        # User event count
        user_event_count = event_count_by_user.get(user_name, 0)

        teams_map[team_name]["members"].append({
            "name": user_name,
            "events": user_event_count
        })

    # After building members, compute team total events
    for team_name in teams_map:
        total = sum(m["events"] for m in teams_map[team_name]["members"])
        teams_map[team_name]["totalEvents"] = total

    # Convert dict → list
    return list(teams_map.values())

@app.get("/stats/events/increment")
def increment_event_count():
    try:
        now = datetime.now()
        current_month = now.strftime("%B")   # e.g., "February"
        current_year = now.year

        # Find team document
        doc = stats_collection.find_one({"team": "event"})
        if not doc:
            raise HTTPException(status_code=404, detail="Event stats document not found")

        stats_list = doc.get("stat", [])
        updated = False

        # Search existing month-year block
        for entry in stats_list:
            if entry.get("month") == current_month and entry.get("year") == current_year:
                entry["events"] = entry.get("events", 0) + 1
                updated = True
                break

        # Create new month-year entry if missing
        if not updated:
            stats_list.append({
                "month": current_month,
                "year": current_year,
                "events": 1
            })

        # Push back to DB
        stats_collection.update_one(
            {"team": "event"},
            {"$set": {"stat": stats_list}}
        )

        return {
            "team": "event",
            "updated": True,
            "month": current_month,
            "year": current_year
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

