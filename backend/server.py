from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import uuid
from datetime import datetime, timezone
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# WebSocket Manager for real-time communication
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.admin_connections: List[WebSocket] = []
        
    async def connect_participant(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        self.admin_connections.append(websocket)
        
    def disconnect_participant(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
    def disconnect_admin(self, websocket: WebSocket):
        if websocket in self.admin_connections:
            self.admin_connections.remove(websocket)
            
    async def send_to_participants(self, message: dict):
        """Send message to all connected participants"""
        if self.active_connections:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.active_connections.remove(conn)
                
    async def send_to_admins(self, message: dict):
        """Send message to all connected admins"""
        if self.admin_connections:
            disconnected = []
            for connection in self.admin_connections:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.admin_connections.remove(conn)
                
    def get_participant_count(self):
        return len(self.active_connections)

manager = ConnectionManager()

# Models
class LightCommand(BaseModel):
    command_type: str  # "color", "effect", "pulse", "strobe"
    color: str  # hex color code
    effect: Optional[str] = None  # "rainbow", "pulse", "strobe", "fade"
    intensity: float = 1.0  # 0.0 to 1.0
    speed: float = 1.0  # 0.1 to 3.0
    duration: Optional[int] = None  # in milliseconds
    section: Optional[str] = "all"  # "all", "left", "right", "center"

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    is_active: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    participant_count: int = 0

class EventCreate(BaseModel):
    name: str
    description: str

# Basic CRUD endpoints
@api_router.get("/")
async def root():
    return {"message": "Festival Light Sync API", "participants": manager.get_participant_count()}

@api_router.post("/events", response_model=Event)
async def create_event(event_data: EventCreate):
    event_dict = event_data.dict()
    event = Event(**event_dict)
    await db.events.insert_one(event.dict())
    return event

@api_router.get("/events", response_model=List[Event])
async def get_events():
    events = await db.events.find().to_list(1000)
    return [Event(**event) for event in events]

@api_router.get("/events/active")
async def get_active_event():
    active_event = await db.events.find_one({"is_active": True})
    if active_event:
        return Event(**active_event)
    return None

@api_router.post("/events/{event_id}/activate")
async def activate_event(event_id: str):
    # Deactivate all events first
    await db.events.update_many({}, {"$set": {"is_active": False}})
    # Activate selected event
    result = await db.events.update_one(
        {"id": event_id}, 
        {"$set": {"is_active": True}}
    )
    if result.modified_count > 0:
        return {"message": "Event activated"}
    return {"error": "Event not found"}

@api_router.post("/light-command")
async def send_light_command(command: LightCommand):
    """Admin endpoint to send light commands to all participants"""
    command_data = command.dict()
    command_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    # Store command in database for history
    await db.light_commands.insert_one(command_data)
    
    # Send to all participants
    await manager.send_to_participants({
        "type": "light_command",
        "data": command_data
    })
    
    # Notify admins about the command
    await manager.send_to_admins({
        "type": "command_sent",
        "data": command_data,
        "participant_count": manager.get_participant_count()
    })
    
    return {"message": "Command sent", "participant_count": manager.get_participant_count()}

@api_router.get("/stats")
async def get_stats():
    participant_count = manager.get_participant_count()
    admin_count = len(manager.admin_connections)
    
    return {
        "participants": participant_count,
        "admins": admin_count,
        "total_connections": participant_count + admin_count
    }

# WebSocket endpoints
@app.websocket("/ws/participant")
async def websocket_participant(websocket: WebSocket):
    await manager.connect_participant(websocket)
    print(f"Participant connected. Total participants: {manager.get_participant_count()}")
    
    # Update all admins about new participant
    await manager.send_to_admins({
        "type": "participant_update",
        "participant_count": manager.get_participant_count()
    })
    
    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle participant messages if needed
            if message.get("type") == "heartbeat":
                await websocket.send_text(json.dumps({"type": "heartbeat_ack"}))
                
    except WebSocketDisconnect:
        manager.disconnect_participant(websocket)
        print(f"Participant disconnected. Total participants: {manager.get_participant_count()}")
        
        # Update all admins about disconnection
        await manager.send_to_admins({
            "type": "participant_update",
            "participant_count": manager.get_participant_count()
        })

@app.websocket("/ws/admin")
async def websocket_admin(websocket: WebSocket):
    await manager.connect_admin(websocket)
    print(f"Admin connected. Total admins: {len(manager.admin_connections)}")
    
    try:
        # Send initial stats to admin
        await websocket.send_text(json.dumps({
            "type": "initial_stats",
            "participant_count": manager.get_participant_count(),
            "admin_count": len(manager.admin_connections)
        }))
        
        while True:
            # Listen for admin commands
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "light_command":
                # Forward light command to all participants
                await manager.send_to_participants(message)
                
                # Store command in database
                command_data = message.get("data", {})
                command_data["timestamp"] = datetime.now(timezone.utc).isoformat()
                await db.light_commands.insert_one(command_data)
                
    except WebSocketDisconnect:
        manager.disconnect_admin(websocket)
        print(f"Admin disconnected. Total admins: {len(manager.admin_connections)}")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()