# main.py
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Body, Header, Response, Cookie
from fastapi.encoders import jsonable_encoder
from typing import Optional, List
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import uvicorn
from models import Event, QueryModel, LoginRequest
from passlib.hash import bcrypt
from bson import ObjectId
from collections import defaultdict
import base64
import hashlib
import random
import json

app = FastAPI()

# Security Constants
SECRET_KEY = "your-very-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

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

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(access_token: Optional[str] = Cookie(None)):
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = users_collection.find_one({"email": email})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

@app.post("/login")
async def login(payload: LoginRequest, response: Response):
    email = payload.email
    password = payload.password
    user = users_collection.find_one({"email": email})
    
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user["role"] == "Yet to be set" or user["team"] == "Yet to be set":
        raise HTTPException(status_code=401, detail="Login not approved yet")
    
    access_token = create_access_token(data={"sub": user["email"]})
    refresh_token = create_refresh_token(data={"sub": user["email"]})
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )
    
    return {
        "message": "Login successful",
        "user": {
            "role": user["role"],
            "team": user["team"],
            "name": user["name"],
            "email": user["email"]
        }
    }

@app.post("/refresh")
async def refresh(response: Response, refresh_token: Optional[str] = Cookie(None)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
            
        new_access_token = create_access_token(data={"sub": email})
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        return {"message": "Token refreshed"}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logout successful"}

@app.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "role": user["role"],
        "team": user["team"],
        "name": user["name"],
        "email": user["email"]
    }
    

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
async def get_all_users(user: dict = Depends(get_current_user)):
    if user["role"] != "Admin":
         raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        users = list(users_collection.find())
        return {"total_users": len(users), "users": [serialize_user(u) for u in users]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/user/{id}")
async def update_user(id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    if user["role"] != "Admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    update_fields = {}
    if "role" in data: update_fields["role"] = data["role"]
    if "team" in data: update_fields["team"] = data["team"]

    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields")

    users_collection.update_one({"_id": ObjectId(id)}, {"$set": update_fields})
    updated_user = users_collection.find_one({"_id": ObjectId(id)})
    return {"message": "User updated", "user": serialize_user(updated_user)}


@app.delete("/del/user/{id}")
async def delete_user(id: str, user: dict = Depends(get_current_user)):
    if user["role"] != "Admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    result = users_collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User with ID {id} deleted successfully"}


@app.get("/events")
async def get_events():
    all_events = list(events.find({}))
    for event in all_events:
        event["_id"] = str(event["_id"])
    return {"events": all_events}

@app.post("/add_event")
def add_event(event: Event, user: dict = Depends(get_current_user)):
    result = events.insert_one(event.dict())
    return {"message": "Event added", "inserted_id": str(result.inserted_id)}

@app.put("/editevent/{id}")
def update_event(id: str, updated_data: Event, user: dict = Depends(get_current_user)):
    collection = db["events"]
    update_dict = {k: v for k, v in updated_data.dict(exclude_unset=True).items() if v not in (None, "")}
    collection.update_one({"_id": ObjectId(id)}, {"$set": jsonable_encoder(update_dict)})
    updated_event = collection.find_one({"_id": ObjectId(id)})
    updated_event["_id"] = str(updated_event["_id"])
    return {"message": "Event updated", "data": updated_event}

@app.put("/suggest/{id}")
def suggest_event(id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    suggestion = data.get("suggestion")
    if not suggestion:
        raise HTTPException(status_code=400, detail="Suggestion text required")
    db["events"].update_one({"_id": ObjectId(id)}, {"$set": {"suggestion": suggestion}})
    updated_event = db["events"].find_one({"_id": ObjectId(id)})
    updated_event["_id"] = str(updated_event["_id"])
    return {"message": "Suggestion added", "data": updated_event}



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
async def get_all_queries(user: dict = Depends(get_current_user)):
    if user["role"] != "Admin":
         raise HTTPException(status_code=403, detail="Not authorized")
    queries = list(queries_collection.find())
    for q in queries:
        q["_id"] = str(q["_id"])
        if "created_at" in q and isinstance(q["created_at"], datetime):
            q["created_at"] = q["created_at"].isoformat()
    return {"queries": queries}


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
async def add_team_stat(team_name: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    stats_collection.update_one({"team": team_name}, {"$push": {"stat": jsonable_encoder(data)}})
    updated_team = stats_collection.find_one({"team": team_name})
    return {"message": "Stat added", "updated_data": updated_team}


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

