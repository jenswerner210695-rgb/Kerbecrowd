#!/usr/bin/env python3
"""
Festival Light Sync Backend Testing Suite
Tests WebSocket communication, API endpoints, and real-time functionality
"""

import asyncio
import json
import requests
import websockets
import time
from datetime import datetime
import uuid

# Configuration
BASE_URL = "https://fest-community.preview.emergentagent.com/api"
WS_PARTICIPANT_URL = "wss://fest-community.preview.emergentagent.com/ws/participant"
WS_ADMIN_URL = "wss://fest-community.preview.emergentagent.com/ws/admin"

class FestivalLightSyncTester:
    def __init__(self):
        self.test_results = []
        self.participant_ws = None
        self.admin_ws = None
        self.test_event_id = None
        
    def log_test(self, test_name, success, message="", details=None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"   {message}")
        if details:
            print(f"   Details: {details}")
        print()

    def test_api_root(self):
        """Test basic API connectivity"""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("API Root Endpoint", True, 
                            f"API accessible, participants: {data.get('participants', 0)}")
                return True
            else:
                self.log_test("API Root Endpoint", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("API Root Endpoint", False, f"Connection error: {str(e)}")
            return False

    def test_stats_api(self):
        """Test statistics API endpoint with section support"""
        try:
            response = requests.get(f"{BASE_URL}/stats", timeout=10)
            if response.status_code == 200:
                data = response.json()
                required_fields = ['sections', 'admins', 'total_connections']
                if all(field in data for field in required_fields):
                    sections = data.get('sections', {})
                    required_sections = ['total', 'left', 'center', 'right']
                    if all(section in sections for section in required_sections):
                        self.log_test("Statistics API", True, 
                                    f"Section stats: {sections['total']} total, {sections['left']} left, {sections['center']} center, {sections['right']} right, {data['admins']} admins")
                        return True
                    else:
                        self.log_test("Statistics API", False, 
                                    f"Missing section fields in response: {sections}")
                        return False
                else:
                    self.log_test("Statistics API", False, 
                                f"Missing required fields in response: {data}")
                    return False
            else:
                self.log_test("Statistics API", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Statistics API", False, f"Error: {str(e)}")
            return False

    def test_event_management(self):
        """Test event management APIs"""
        # Test creating an event
        try:
            event_data = {
                "name": "Sommerfest Lichtshow 2025",
                "description": "Spektakuläre Lichtshow für das Stadtfest mit synchronisierten Smartphone-Effekten"
            }
            
            response = requests.post(f"{BASE_URL}/events", json=event_data, timeout=10)
            if response.status_code == 200:
                event = response.json()
                self.test_event_id = event.get('id')
                self.log_test("Create Event", True, 
                            f"Event created: {event.get('name')} (ID: {self.test_event_id})")
            else:
                self.log_test("Create Event", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Create Event", False, f"Error: {str(e)}")
            return False

        # Test listing events
        try:
            response = requests.get(f"{BASE_URL}/events", timeout=10)
            if response.status_code == 200:
                events = response.json()
                if isinstance(events, list) and len(events) > 0:
                    self.log_test("List Events", True, 
                                f"Retrieved {len(events)} events")
                else:
                    self.log_test("List Events", False, "No events returned")
                    return False
            else:
                self.log_test("List Events", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("List Events", False, f"Error: {str(e)}")
            return False

        # Test activating an event
        if self.test_event_id:
            try:
                response = requests.post(f"{BASE_URL}/events/{self.test_event_id}/activate", timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    self.log_test("Activate Event", True, 
                                f"Event activated: {result.get('message')}")
                else:
                    self.log_test("Activate Event", False, 
                                f"HTTP {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                self.log_test("Activate Event", False, f"Error: {str(e)}")
                return False

        # Test getting active event
        try:
            response = requests.get(f"{BASE_URL}/events/active", timeout=10)
            if response.status_code == 200:
                active_event = response.json()
                if active_event and active_event.get('is_active'):
                    self.log_test("Get Active Event", True, 
                                f"Active event: {active_event.get('name')}")
                else:
                    self.log_test("Get Active Event", False, "No active event found")
                    return False
            else:
                self.log_test("Get Active Event", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Get Active Event", False, f"Error: {str(e)}")
            return False

        return True

    def test_light_command_api(self):
        """Test light command API with different effects and sections"""
        light_commands = [
            {
                "command_type": "color",
                "color": "#FF6B35",  # Festival orange
                "effect": "solid",
                "intensity": 1.0,
                "speed": 1.0,
                "section": "all"
            },
            {
                "command_type": "effect",
                "color": "#4ECDC4",  # Turquoise
                "effect": "pulse",
                "intensity": 0.8,
                "speed": 1.5,
                "duration": 5000,
                "section": "left"
            },
            {
                "command_type": "effect",
                "color": "#45B7D1",  # Blue
                "effect": "strobe",
                "intensity": 1.0,
                "speed": 2.0,
                "duration": 3000,
                "section": "center"
            },
            {
                "command_type": "effect",
                "color": "#96CEB4",  # Green
                "effect": "rainbow",
                "intensity": 0.9,
                "speed": 0.8,
                "duration": 10000,
                "section": "right"
            },
            {
                "command_type": "effect",
                "color": "#FFEAA7",  # Yellow
                "effect": "wave",
                "intensity": 0.7,
                "speed": 1.2,
                "duration": 8000,
                "section": "all",
                "wave_direction": "left_to_right"
            },
            {
                "command_type": "effect",
                "color": "#DDA0DD",  # Plum
                "effect": "wave",
                "intensity": 0.8,
                "speed": 1.0,
                "duration": 6000,
                "section": "all",
                "wave_direction": "center_out"
            },
            {
                "command_type": "effect",
                "color": "#FFB6C1",  # Light pink
                "effect": "wave",
                "intensity": 0.9,
                "speed": 1.5,
                "duration": 7000,
                "section": "all",
                "wave_direction": "right_to_left"
            }
        ]

        for i, command in enumerate(light_commands):
            try:
                response = requests.post(f"{BASE_URL}/light-command", json=command, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    section_stats = result.get('section_stats', {})
                    effect_desc = f"{command['effect']}"
                    if command.get('wave_direction'):
                        effect_desc += f" ({command['wave_direction']})"
                    self.log_test(f"Light Command {i+1} ({effect_desc})", True, 
                                f"Command sent to section '{command['section']}', stats: {section_stats}")
                    time.sleep(0.5)  # Brief pause between commands
                else:
                    self.log_test(f"Light Command {i+1} ({command['effect']})", False, 
                                f"HTTP {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                self.log_test(f"Light Command {i+1} ({command['effect']})", False, f"Error: {str(e)}")
                return False

        return True

    def test_beat_synchronization_api(self):
        """Test beat synchronization system"""
        # Test beat data submission
        beat_data = {
            "bpm": 128.5,
            "intensity": 0.85,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(f"{BASE_URL}/beat-data", json=beat_data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                self.log_test("Beat Data Submission", True, 
                            f"Beat data received: {result.get('bpm')} BPM")
            else:
                self.log_test("Beat Data Submission", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Beat Data Submission", False, f"Error: {str(e)}")
            return False

        # Test latest beat retrieval
        try:
            response = requests.get(f"{BASE_URL}/latest-beat", timeout=10)
            if response.status_code == 200:
                result = response.json()
                beat = result.get('beat')
                if beat and beat.get('bpm') == beat_data['bpm']:
                    self.log_test("Latest Beat Retrieval", True, 
                                f"Retrieved beat: {beat.get('bpm')} BPM, intensity: {beat.get('intensity')}")
                else:
                    self.log_test("Latest Beat Retrieval", False, 
                                f"Beat data mismatch or not found: {beat}")
                    return False
            else:
                self.log_test("Latest Beat Retrieval", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Latest Beat Retrieval", False, f"Error: {str(e)}")
            return False

        return True

    def test_preset_patterns(self):
        """Test preset light patterns"""
        presets = ["party_mode", "calm_wave", "festival_finale"]
        
        for preset in presets:
            try:
                response = requests.post(f"{BASE_URL}/preset/{preset}", timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    section_stats = result.get('section_stats', {})
                    self.log_test(f"Preset Pattern: {preset}", True, 
                                f"Preset activated, stats: {section_stats}")
                    time.sleep(1)  # Brief pause between presets
                else:
                    self.log_test(f"Preset Pattern: {preset}", False, 
                                f"HTTP {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                self.log_test(f"Preset Pattern: {preset}", False, f"Error: {str(e)}")
                return False

        return True

    def test_section_join_api(self):
        """Test section join functionality"""
        sections = ["left", "center", "right"]
        
        for section in sections:
            try:
                section_data = {"section": section}
                response = requests.post(f"{BASE_URL}/join-section", json=section_data, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    self.log_test(f"Section Join: {section}", True, 
                                f"Join message: {result.get('message')}")
                else:
                    self.log_test(f"Section Join: {section}", False, 
                                f"HTTP {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                self.log_test(f"Section Join: {section}", False, f"Error: {str(e)}")
                return False

        return True

    async def test_participant_websocket(self):
        """Test participant WebSocket connection with sections"""
        try:
            # Test connection to 'all' section
            self.participant_ws = await websockets.connect(f"{WS_PARTICIPANT_URL}/all")
            self.log_test("Participant WebSocket Connection (all)", True, "Connected successfully")
            
            # Send heartbeat
            heartbeat_msg = {"type": "heartbeat"}
            await self.participant_ws.send(json.dumps(heartbeat_msg))
            
            # Wait for heartbeat acknowledgment
            try:
                response = await asyncio.wait_for(self.participant_ws.recv(), timeout=5.0)
                response_data = json.loads(response)
                if response_data.get("type") == "heartbeat_ack":
                    self.log_test("Participant WebSocket Heartbeat", True, "Heartbeat acknowledged")
                else:
                    self.log_test("Participant WebSocket Heartbeat", False, 
                                f"Unexpected response: {response_data}")
            except asyncio.TimeoutError:
                self.log_test("Participant WebSocket Heartbeat", False, "Heartbeat timeout")
                
            return True
            
        except Exception as e:
            self.log_test("Participant WebSocket Connection", False, f"Error: {str(e)}")
            return False

    async def test_section_websocket_connections(self):
        """Test section-based WebSocket connections"""
        sections = ["left", "center", "right", "all"]
        section_connections = {}
        
        for section in sections:
            try:
                ws_url = f"{WS_PARTICIPANT_URL}/{section}"
                ws = await websockets.connect(ws_url)
                section_connections[section] = ws
                self.log_test(f"Section WebSocket Connection: {section}", True, 
                            f"Connected to section '{section}'")
                await asyncio.sleep(0.5)  # Brief pause between connections
            except Exception as e:
                self.log_test(f"Section WebSocket Connection: {section}", False, f"Error: {str(e)}")
                return False
        
        # Test section change functionality
        try:
            if "all" in section_connections:
                section_change_msg = {"type": "section_change", "section": "left"}
                await section_connections["all"].send(json.dumps(section_change_msg))
                self.log_test("Section Change Message", True, "Section change message sent")
        except Exception as e:
            self.log_test("Section Change Message", False, f"Error: {str(e)}")
        
        # Clean up section connections
        for section, ws in section_connections.items():
            try:
                await ws.close()
            except:
                pass
                
        return True

    async def test_admin_websocket(self):
        """Test admin WebSocket connection"""
        try:
            self.admin_ws = await websockets.connect(WS_ADMIN_URL)
            self.log_test("Admin WebSocket Connection", True, "Connected successfully")
            
            # Wait for initial stats
            try:
                response = await asyncio.wait_for(self.admin_ws.recv(), timeout=5.0)
                response_data = json.loads(response)
                if response_data.get("type") == "initial_stats":
                    stats = response_data.get('section_stats', {})
                    admin_count = response_data.get('admin_count', 0)
                    self.log_test("Admin WebSocket Initial Stats", True, 
                                f"Received section stats: {stats}, {admin_count} admins")
                else:
                    self.log_test("Admin WebSocket Initial Stats", False, 
                                f"Unexpected response: {response_data}")
            except asyncio.TimeoutError:
                self.log_test("Admin WebSocket Initial Stats", False, "Initial stats timeout")
                
            return True
            
        except Exception as e:
            self.log_test("Admin WebSocket Connection", False, f"Error: {str(e)}")
            return False

    async def test_websocket_light_command_broadcast(self):
        """Test light command broadcasting through WebSocket"""
        if not self.admin_ws or not self.participant_ws:
            self.log_test("WebSocket Light Command Broadcast", False, "WebSocket connections not established")
            return False
            
        try:
            # Send light command from admin WebSocket
            light_command = {
                "type": "light_command",
                "data": {
                    "command_type": "effect",
                    "color": "#E17055",  # Coral
                    "effect": "pulse",
                    "intensity": 0.9,
                    "speed": 1.3,
                    "duration": 6000,
                    "section": "all"
                }
            }
            
            await self.admin_ws.send(json.dumps(light_command))
            self.log_test("Admin WebSocket Send Command", True, "Light command sent from admin")
            
            # Check if participant receives the command
            try:
                response = await asyncio.wait_for(self.participant_ws.recv(), timeout=5.0)
                response_data = json.loads(response)
                if response_data.get("type") == "light_command":
                    command_data = response_data.get("data", {})
                    self.log_test("Participant WebSocket Receive Command", True, 
                                f"Received command: {command_data.get('effect')} effect in {command_data.get('color')}")
                    return True
                else:
                    self.log_test("Participant WebSocket Receive Command", False, 
                                f"Unexpected message type: {response_data.get('type')}")
                    return False
            except asyncio.TimeoutError:
                self.log_test("Participant WebSocket Receive Command", False, "Command receive timeout")
                return False
                
        except Exception as e:
            self.log_test("WebSocket Light Command Broadcast", False, f"Error: {str(e)}")
            return False

    async def test_beat_sync_websocket(self):
        """Test beat synchronization through WebSocket"""
        if not self.admin_ws or not self.participant_ws:
            self.log_test("Beat Sync WebSocket Test", False, "WebSocket connections not established")
            return False
            
        try:
            # Enable beat sync for the test event
            if self.test_event_id:
                response = requests.post(f"{BASE_URL}/events/{self.test_event_id}/beat-sync/true", timeout=10)
                if response.status_code != 200:
                    self.log_test("Beat Sync Enable", False, "Could not enable beat sync")
                    return False
            
            # Send beat data
            beat_data = {
                "bpm": 140.0,
                "intensity": 0.9,
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(f"{BASE_URL}/beat-data", json=beat_data, timeout=10)
            if response.status_code != 200:
                self.log_test("Beat Sync WebSocket - Send Beat", False, "Could not send beat data")
                return False
            
            # Check if participant receives beat sync command
            try:
                response = await asyncio.wait_for(self.participant_ws.recv(), timeout=5.0)
                response_data = json.loads(response)
                if response_data.get("type") == "beat_sync":
                    beat_command = response_data.get("data", {})
                    self.log_test("Beat Sync WebSocket", True, 
                                f"Received beat sync: {beat_command.get('bpm')} BPM, intensity: {beat_command.get('intensity')}")
                    return True
                else:
                    self.log_test("Beat Sync WebSocket", False, 
                                f"Unexpected message type: {response_data.get('type')}")
                    return False
            except asyncio.TimeoutError:
                self.log_test("Beat Sync WebSocket", False, "Beat sync message timeout")
                return False
                
        except Exception as e:
            self.log_test("Beat Sync WebSocket", False, f"Error: {str(e)}")
            return False

    async def test_websocket_connection_tracking(self):
        """Test WebSocket connection tracking"""
        try:
            # Get initial stats
            initial_response = requests.get(f"{BASE_URL}/stats", timeout=10)
            if initial_response.status_code != 200:
                self.log_test("Connection Tracking - Initial Stats", False, "Could not get initial stats")
                return False
                
            initial_stats = initial_response.json()
            initial_participants = initial_stats.get('participants', 0)
            
            # Connect a new participant
            test_participant_ws = await websockets.connect(WS_PARTICIPANT_URL)
            await asyncio.sleep(1)  # Allow time for connection to register
            
            # Check updated stats
            updated_response = requests.get(f"{BASE_URL}/stats", timeout=10)
            if updated_response.status_code == 200:
                updated_stats = updated_response.json()
                updated_participants = updated_stats.get('participants', 0)
                
                if updated_participants > initial_participants:
                    self.log_test("Connection Tracking - Participant Join", True, 
                                f"Participant count increased from {initial_participants} to {updated_participants}")
                else:
                    self.log_test("Connection Tracking - Participant Join", False, 
                                f"Participant count did not increase: {initial_participants} -> {updated_participants}")
                    
            # Disconnect the test participant
            await test_participant_ws.close()
            await asyncio.sleep(1)  # Allow time for disconnection to register
            
            # Check final stats
            final_response = requests.get(f"{BASE_URL}/stats", timeout=10)
            if final_response.status_code == 200:
                final_stats = final_response.json()
                final_participants = final_stats.get('participants', 0)
                
                if final_participants == initial_participants:
                    self.log_test("Connection Tracking - Participant Leave", True, 
                                f"Participant count returned to {final_participants}")
                    return True
                else:
                    self.log_test("Connection Tracking - Participant Leave", False, 
                                f"Participant count mismatch: expected {initial_participants}, got {final_participants}")
                    return False
            else:
                self.log_test("Connection Tracking - Final Stats", False, "Could not get final stats")
                return False
                
        except Exception as e:
            self.log_test("Connection Tracking", False, f"Error: {str(e)}")
            return False

    async def cleanup_websockets(self):
        """Clean up WebSocket connections"""
        try:
            if self.participant_ws:
                await self.participant_ws.close()
            if self.admin_ws:
                await self.admin_ws.close()
        except:
            pass

    async def run_all_tests(self):
        """Run all backend tests"""
        print("🎪 Festival Light Sync Backend Testing Suite")
        print("=" * 50)
        print()
        
        # Basic API tests
        print("📡 Testing Basic API Connectivity...")
        api_working = self.test_api_root()
        
        print("📊 Testing Statistics API...")
        stats_working = self.test_stats_api()
        
        print("🎭 Testing Event Management...")
        events_working = self.test_event_management()
        
        print("💡 Testing Light Command API...")
        light_api_working = self.test_light_command_api()
        
        # WebSocket tests
        print("🔌 Testing WebSocket Connections...")
        participant_ws_working = await self.test_participant_websocket()
        admin_ws_working = await self.test_admin_websocket()
        
        print("📡 Testing WebSocket Broadcasting...")
        broadcast_working = await self.test_websocket_light_command_broadcast()
        
        print("👥 Testing Connection Tracking...")
        tracking_working = await self.test_websocket_connection_tracking()
        
        # Cleanup
        await self.cleanup_websockets()
        
        # Summary
        print("\n" + "=" * 50)
        print("🎯 TEST SUMMARY")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\n📋 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}")
            if result['message']:
                print(f"   {result['message']}")
        
        # Component-level assessment
        print("\n🏗️ COMPONENT STATUS:")
        
        # WebSocket Communication
        ws_tests = [r for r in self.test_results if 'WebSocket' in r['test']]
        ws_success = all(r['success'] for r in ws_tests)
        print(f"{'✅' if ws_success else '❌'} WebSocket Communication: {'WORKING' if ws_success else 'ISSUES FOUND'}")
        
        # Light Command API
        light_tests = [r for r in self.test_results if 'Light Command' in r['test']]
        light_success = all(r['success'] for r in light_tests)
        print(f"{'✅' if light_success else '❌'} Light Command API: {'WORKING' if light_success else 'ISSUES FOUND'}")
        
        # Event Management
        event_tests = [r for r in self.test_results if any(keyword in r['test'] for keyword in ['Event', 'Create', 'List', 'Activate'])]
        event_success = all(r['success'] for r in event_tests)
        print(f"{'✅' if event_success else '❌'} Event Management: {'WORKING' if event_success else 'ISSUES FOUND'}")
        
        # Statistics API
        stats_tests = [r for r in self.test_results if 'Statistics' in r['test'] or 'Connection Tracking' in r['test']]
        stats_success = all(r['success'] for r in stats_tests)
        print(f"{'✅' if stats_success else '❌'} Statistics API: {'WORKING' if stats_success else 'ISSUES FOUND'}")
        
        return {
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'websocket_working': ws_success,
            'light_api_working': light_success,
            'event_management_working': event_success,
            'statistics_working': stats_success,
            'overall_success': failed_tests == 0
        }

async def main():
    """Main test execution"""
    tester = FestivalLightSyncTester()
    results = await tester.run_all_tests()
    
    # Return exit code based on results
    return 0 if results['overall_success'] else 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)