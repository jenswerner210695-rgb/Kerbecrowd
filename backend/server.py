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

# WebSocket Manager for real-time communication with sections
class ConnectionManager:
    def __init__(self):
        self.participant_connections: Dict[str, List[WebSocket]] = {
            'all': [],
            'left': [],
            'center': [],
            'right': []
        }
        self.admin_connections: List[WebSocket] = []
        
    async def connect_participant(self, websocket: WebSocket, section: str = 'all'):
        await websocket.accept()
        if section not in self.participant_connections:
            section = 'all'
        self.participant_connections[section].append(websocket)
        self.participant_connections['all'].append(websocket)
        
    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        self.admin_connections.append(websocket)
        
    def disconnect_participant(self, websocket: WebSocket):
        for section_list in self.participant_connections.values():
            if websocket in section_list:
                section_list.remove(websocket)
            
    def disconnect_admin(self, websocket: WebSocket):
        if websocket in self.admin_connections:
            self.admin_connections.remove(websocket)
            
    async def send_to_participants(self, message: dict, section: str = 'all'):
        """Send message to participants in specific section"""
        target_connections = self.participant_connections.get(section, [])
        if target_connections:
            disconnected = []
            for connection in target_connections:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.disconnect_participant(conn)
                
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
                
    def get_participant_count(self, section: str = 'all'):
        return len(self.participant_connections.get(section, []))
    
    def get_section_stats(self):
        return {
            'total': len(set(self.participant_connections['all'])),
            'left': len(self.participant_connections['left']),
            'center': len(self.participant_connections['center']), 
            'right': len(self.participant_connections['right'])
        }

manager = ConnectionManager()

# Advanced Models
class LightCommand(BaseModel):
    command_type: str  # "color", "effect", "beat_sync", "wave"
    color: str  # hex color code
    effect: Optional[str] = None  # "rainbow", "pulse", "strobe", "fade", "wave", "beat_sync"
    intensity: float = 1.0  # 0.0 to 1.0
    speed: float = 1.0  # 0.1 to 3.0
    duration: Optional[int] = None  # in milliseconds
    section: Optional[str] = "all"  # "all", "left", "right", "center"
    beat_sensitivity: Optional[float] = 0.5  # 0.0 to 1.0 for beat detection
    wave_direction: Optional[str] = "left_to_right"  # "left_to_right", "center_out", "random"

class SectionJoin(BaseModel):
    section: str  # "left", "center", "right"

class BeatData(BaseModel):
    bpm: float
    intensity: float
    timestamp: datetime

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    is_active: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    participant_count: int = 0
    beat_sync_enabled: bool = False

class EventCreate(BaseModel):
    name: str
    description: str

# Store latest command and beat data for polling fallback
latest_command = None
latest_beat_data = None

# Basic CRUD endpoints
@api_router.get("/")
async def root():
    stats = manager.get_section_stats()
    return {
        "message": "Festival Light Sync API - Phase 2", 
        "participants": stats,
        "beat_sync": latest_beat_data is not None
    }

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

@api_router.post("/events/{event_id}/beat-sync/{enabled}")
async def toggle_beat_sync(event_id: str, enabled: bool):
    result = await db.events.update_one(
        {"id": event_id}, 
        {"$set": {"beat_sync_enabled": enabled}}
    )
    if result.modified_count > 0:
        return {"message": f"Beat sync {'enabled' if enabled else 'disabled'}"}
    return {"error": "Event not found"}

@api_router.post("/light-command")
async def send_light_command(command: LightCommand):
    """Admin endpoint to send advanced light commands"""
    global latest_command
    
    command_data = command.dict()
    command_data["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    # Store as latest command for polling fallback
    latest_command = command_data
    
    # Store command in database for history
    await db.light_commands.insert_one(command_data)
    
    # Handle different command types
    if command.effect == "wave":
        await send_wave_effect(command_data)
    else:
        # Send to specific section or all participants
        await manager.send_to_participants({
            "type": "light_command",
            "data": command_data
        }, command.section)
    
    # Notify admins about the command
    stats = manager.get_section_stats()
    await manager.send_to_admins({
        "type": "command_sent",
        "data": command_data,
        "section_stats": stats
    })
    
    return {"message": "Command sent", "section_stats": stats}

async def send_wave_effect(command_data):
    """Send wave effect across sections with timing"""
    sections = ['left', 'center', 'right']
    delay = 300  # milliseconds between sections
    
    if command_data['wave_direction'] == 'center_out':
        sections = ['center', 'left', 'right']
    elif command_data['wave_direction'] == 'right_to_left':
        sections = ['right', 'center', 'left']
    
    for i, section in enumerate(sections):
        # Add delay information to command
        wave_command = command_data.copy()
        wave_command['wave_delay'] = i * delay
        
        await manager.send_to_participants({
            "type": "light_command",
            "data": wave_command
        }, section)
        
        # Small delay between sections for server-side timing
        if i < len(sections) - 1:
            await asyncio.sleep(delay / 1000)

@api_router.post("/beat-data")
async def receive_beat_data(beat_data: BeatData):
    """Receive beat data from admin's audio analysis"""
    global latest_beat_data
    
    beat_dict = beat_data.dict()
    beat_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    # Store clean data without MongoDB ObjectId for latest_beat_data
    latest_beat_data = beat_dict.copy()
    
    # Store beat data in database
    await db.beat_data.insert_one(beat_dict)
    
    # Send beat sync command to all participants if enabled
    active_event = await db.events.find_one({"is_active": True, "beat_sync_enabled": True})
    if active_event:
        beat_command = {
            "command_type": "beat_sync",
            "color": "#FFFFFF",  # White for beat sync
            "effect": "beat_sync",
            "intensity": min(beat_data.intensity, 1.0),
            "bpm": beat_data.bpm,
            "timestamp": beat_dict["timestamp"]
        }
        
        await manager.send_to_participants({
            "type": "beat_sync",
            "data": beat_command
        })
    
    return {"message": "Beat data received", "bpm": beat_data.bpm}

@api_router.get("/latest-command")
async def get_latest_command(timestamp: str = None):
    """Get the latest light command for polling fallback"""
    global latest_command
    
    if latest_command:
        if timestamp:
            try:
                provided_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                command_timestamp = datetime.fromisoformat(latest_command['timestamp'].replace('Z', '+00:00'))
                
                if command_timestamp > provided_timestamp:
                    return {"command": latest_command}
                else:
                    return {"command": None}
            except:
                return {"command": latest_command}
        else:
            return {"command": latest_command}
    
    return {"command": None}

@api_router.get("/latest-beat")
async def get_latest_beat():
    """Get latest beat data"""
    global latest_beat_data
    return {"beat": latest_beat_data}

@api_router.get("/stats")
async def get_stats():
    section_stats = manager.get_section_stats()
    admin_count = len(manager.admin_connections)
    
    return {
        "sections": section_stats,
        "admins": admin_count,
        "total_connections": section_stats['total'] + admin_count,
        "beat_sync_active": latest_beat_data is not None
    }

@api_router.post("/join-section")
async def join_section(section_data: SectionJoin):
    """Endpoint for participants to join a specific section"""
    return {"message": f"Join section {section_data.section} via WebSocket"}

# Preset light patterns
@api_router.post("/preset/{preset_name}")
async def send_preset(preset_name: str):
    """Send predefined light patterns"""
    presets = {
        "party_mode": {
            "command_type": "effect",
            "color": "#FF00FF",
            "effect": "strobe",
            "intensity": 1.0,
            "speed": 2.5,
            "duration": 10000,
            "section": "all"
        },
        "calm_wave": {
            "command_type": "effect", 
            "color": "#4ECDC4",
            "effect": "wave",
            "intensity": 0.7,
            "speed": 1.0,
            "duration": 8000,
            "section": "all",
            "wave_direction": "left_to_right"
        },
        "festival_finale": {
            "command_type": "effect",
            "color": "#FFD700",
            "effect": "rainbow",
            "intensity": 1.0,
            "speed": 3.0,
            "duration": 15000,
            "section": "all"
        }
    }
    
    if preset_name in presets:
        command = LightCommand(**presets[preset_name])
        result = await send_light_command(command)
        return result
    else:
        return {"error": "Preset not found"}

# WebSocket endpoints with section support
@app.websocket("/ws/participant/{section}")
async def websocket_participant(websocket: WebSocket, section: str = "all"):
    await manager.connect_participant(websocket, section)
    print(f"Participant connected to section '{section}'. Stats: {manager.get_section_stats()}")
    
    # Update all admins about new participant
    await manager.send_to_admins({
        "type": "participant_update",
        "section_stats": manager.get_section_stats()
    })
    
    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle participant messages
            if message.get("type") == "heartbeat":
                await websocket.send_text(json.dumps({"type": "heartbeat_ack"}))
            elif message.get("type") == "section_change":
                # Handle section change
                new_section = message.get("section", "all")
                manager.disconnect_participant(websocket)
                await manager.connect_participant(websocket, new_section)
                
    except WebSocketDisconnect:
        manager.disconnect_participant(websocket)
        print(f"Participant disconnected. Stats: {manager.get_section_stats()}")
        
        # Update all admins about disconnection
        await manager.send_to_admins({
            "type": "participant_update",
            "section_stats": manager.get_section_stats()
        })

@app.websocket("/ws/admin")
async def websocket_admin(websocket: WebSocket):
    await manager.connect_admin(websocket)
    print(f"Admin connected. Total admins: {len(manager.admin_connections)}")
    
    try:
        # Send initial stats to admin
        await websocket.send_text(json.dumps({
            "type": "initial_stats",
            "section_stats": manager.get_section_stats(),
            "admin_count": len(manager.admin_connections)
        }))
        
        while True:
            # Listen for admin commands
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "light_command":
                # Forward light command to participants
                command_data = message.get("data", {})
                section = command_data.get("section", "all")
                
                if command_data.get("effect") == "wave":
                    await send_wave_effect(command_data)
                else:
                    await manager.send_to_participants(message, section)
                
                # Store command in database
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