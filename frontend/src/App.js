import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('http', 'ws');

// Participant Light Screen Component
const ParticipantScreen = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [currentColor, setCurrentColor] = useState('#3B82F6');
  const [isActive, setIsActive] = useState(false);
  const wsRef = useRef(null);
  const animationRef = useRef(null);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        if (wsRef.current.close && typeof wsRef.current.close === 'function') {
          wsRef.current.close();
        } else if (wsRef.current.pollInterval) {
          clearInterval(wsRef.current.pollInterval);
        }
      }
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  const connectWebSocket = () => {
    try {
      wsRef.current = new WebSocket(`${WS_URL}/ws/participant`);
      
      wsRef.current.onopen = () => {
        setIsConnected(true);
        console.log('Connected to light sync system');
      };
      
      wsRef.current.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleLightCommand(message);
      };
      
      wsRef.current.onclose = () => {
        setIsConnected(false);
        console.log('Disconnected from light sync system - using polling fallback');
        // Start polling fallback
        startPollingFallback();
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
        // Start polling fallback immediately on error
        startPollingFallback();
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      startPollingFallback();
    }
  };

  const startPollingFallback = () => {
    // Use polling to get latest commands when WebSocket fails
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API}/latest-command?timestamp=${Date.now()}`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.command) {
            handleLightCommand({
              type: 'light_command',
              data: data.command
            });
          }
        }
      } catch (error) {
        console.error('Polling fallback error:', error);
      }
    }, 1000); // Poll every second
    
    // Store interval ref to clear later
    wsRef.current = { pollInterval };
  };

  const handleLightCommand = (message) => {
    if (message.type === 'light_command') {
      const { command_type, color, effect, intensity, speed, duration } = message.data;
      
      setCurrentColor(color);
      setIsActive(true);
      
      // Handle different effects
      switch (effect) {
        case 'pulse':
          startPulseEffect(color, intensity, speed, duration);
          break;
        case 'strobe':
          startStrobeEffect(color, intensity, speed, duration);
          break;
        case 'rainbow':
          startRainbowEffect(intensity, speed, duration);
          break;
        case 'fade':
          startFadeEffect(color, intensity, speed, duration);
          break;
        default:
          // Solid color
          setSolidColor(color, intensity, duration);
      }
    }
  };

  const setSolidColor = (color, intensity, duration) => {
    const adjustedColor = adjustColorIntensity(color, intensity);
    setCurrentColor(adjustedColor);
    
    if (duration) {
      setTimeout(() => {
        setIsActive(false);
        setCurrentColor('#000000');
      }, duration);
    }
  };

  const startPulseEffect = (color, intensity, speed, duration) => {
    let startTime = Date.now();
    const animate = () => {
      const elapsed = Date.now() - startTime;
      if (duration && elapsed > duration) {
        setIsActive(false);
        return;
      }
      
      const pulseValue = (Math.sin(elapsed * speed * 0.01) + 1) / 2;
      const adjustedColor = adjustColorIntensity(color, intensity * pulseValue);
      setCurrentColor(adjustedColor);
      
      animationRef.current = requestAnimationFrame(animate);
    };
    animate();
  };

  const startStrobeEffect = (color, intensity, speed, duration) => {
    let startTime = Date.now();
    let isOn = true;
    const strobeInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      if (duration && elapsed > duration) {
        clearInterval(strobeInterval);
        setIsActive(false);
        return;
      }
      
      isOn = !isOn;
      setCurrentColor(isOn ? adjustColorIntensity(color, intensity) : '#000000');
    }, 1000 / (speed * 10));
  };

  const startRainbowEffect = (intensity, speed, duration) => {
    let startTime = Date.now();
    const animate = () => {
      const elapsed = Date.now() - startTime;
      if (duration && elapsed > duration) {
        setIsActive(false);
        return;
      }
      
      const hue = (elapsed * speed * 0.1) % 360;
      const color = `hsl(${hue}, 100%, 50%)`;
      setCurrentColor(adjustColorIntensity(color, intensity));
      
      animationRef.current = requestAnimationFrame(animate);
    };
    animate();
  };

  const startFadeEffect = (targetColor, intensity, speed, duration) => {
    let startTime = Date.now();
    const startColor = currentColor;
    
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / (1000 / speed), 1);
      
      if (progress >= 1 || (duration && elapsed > duration)) {
        setCurrentColor(adjustColorIntensity(targetColor, intensity));
        setIsActive(false);
        return;
      }
      
      // Interpolate between colors
      const interpolatedColor = interpolateColors(startColor, targetColor, progress);
      setCurrentColor(adjustColorIntensity(interpolatedColor, intensity));
      
      animationRef.current = requestAnimationFrame(animate);
    };
    animate();
  };

  const adjustColorIntensity = (color, intensity) => {
    if (color.startsWith('#')) {
      const r = parseInt(color.slice(1, 3), 16);
      const g = parseInt(color.slice(3, 5), 16);
      const b = parseInt(color.slice(5, 7), 16);
      
      return `rgb(${Math.round(r * intensity)}, ${Math.round(g * intensity)}, ${Math.round(b * intensity)})`;
    }
    return color;
  };

  const interpolateColors = (color1, color2, progress) => {
    // Simple color interpolation
    return color2; // Simplified for now
  };

  return (
    <div 
      className="participant-screen"
      style={{ backgroundColor: currentColor }}
    >
      <div className="connection-status">
        <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '🔗 Verbunden' : '❌ Getrennt'}
        </div>
        <div className="festival-info">
          <h1>🎵 Festival Light Sync</h1>
          <p>Halten Sie Ihr Handy hoch und lassen Sie es leuchten!</p>
        </div>
      </div>
    </div>
  );
};

// Admin Control Panel Component
const AdminPanel = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [participantCount, setParticipantCount] = useState(0);
  const [selectedColor, setSelectedColor] = useState('#FF0000');
  const [selectedEffect, setSelectedEffect] = useState('solid');
  const [intensity, setIntensity] = useState(1.0);
  const [speed, setSpeed] = useState(1.0);
  const wsRef = useRef(null);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    try {
      wsRef.current = new WebSocket(`${WS_URL}/ws/admin`);
      
      wsRef.current.onopen = () => {
        setIsConnected(true);
        console.log('Admin connected to control system');
      };
      
      wsRef.current.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'participant_update' || message.type === 'initial_stats') {
          setParticipantCount(message.participant_count);
        }
      };
      
      wsRef.current.onclose = () => {
        setIsConnected(false);
        console.log('Admin WebSocket disconnected - using HTTP fallback');
        startAdminPolling();
      };
      
      wsRef.current.onerror = (error) => {
        console.error('Admin WebSocket error:', error);
        setIsConnected(false);
        startAdminPolling();
      };
    } catch (error) {
      console.error('Admin WebSocket connection failed:', error);
      startAdminPolling();
    }
  };

  const startAdminPolling = () => {
    // Poll stats every 2 seconds for participant count
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API}/stats`);
        if (response.ok) {
          const stats = await response.json();
          setParticipantCount(stats.participants);
          // Set connected if we can get stats
          setIsConnected(true);
        }
      } catch (error) {
        console.error('Admin polling error:', error);
        setIsConnected(false);
      }
    }, 2000);
    
    wsRef.current = { pollInterval };
  };

  const sendLightCommand = async (overrideEffect = null) => {
    const command = {
      command_type: 'effect',
      color: selectedColor,
      effect: overrideEffect || selectedEffect,
      intensity: intensity,
      speed: speed,
      duration: selectedEffect === 'solid' ? null : 5000,
      section: 'all'
    };

    try {
      // Use HTTP API directly since WebSocket may not work due to infrastructure
      const response = await fetch(`${API}/light-command`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(command)
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log('Light command sent successfully:', result);
      } else {
        console.error('Failed to send light command');
      }
    } catch (error) {
      console.error('Error sending light command:', error);
    }
  };

  const presetColors = [
    { name: 'Rot', color: '#FF0000' },
    { name: 'Grün', color: '#00FF00' },
    { name: 'Blau', color: '#0000FF' },
    { name: 'Gelb', color: '#FFFF00' },
    { name: 'Magenta', color: '#FF00FF' },
    { name: 'Cyan', color: '#00FFFF' },
    { name: 'Weiß', color: '#FFFFFF' },
    { name: 'Orange', color: '#FFA500' }
  ];

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <h1>🎛️ Festival Light Control</h1>
        <div className="connection-info">
          <span className={`admin-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '✅ Verbunden' : '❌ Getrennt'}
          </span>
          <span className="participant-count">
            👥 {participantCount} Teilnehmer
          </span>
        </div>
      </div>

      <div className="control-sections">
        {/* Quick Color Presets */}
        <div className="control-section">
          <h3>Schnell-Farben</h3>
          <div className="color-presets">
            {presetColors.map((preset) => (
              <button
                key={preset.name}
                className="color-preset-btn"
                style={{ backgroundColor: preset.color }}
                onClick={() => {
                  setSelectedColor(preset.color);
                  sendLightCommand('solid');
                }}
                title={preset.name}
              />
            ))}
          </div>
        </div>

        {/* Custom Controls */}
        <div className="control-section">
          <h3>Benutzerdefinierte Steuerung</h3>
          <div className="custom-controls">
            <div className="control-group">
              <label>Farbe:</label>
              <input
                type="color"
                value={selectedColor}
                onChange={(e) => setSelectedColor(e.target.value)}
              />
            </div>
            
            <div className="control-group">
              <label>Effekt:</label>
              <select 
                value={selectedEffect} 
                onChange={(e) => setSelectedEffect(e.target.value)}
              >
                <option value="solid">Vollfarbe</option>
                <option value="pulse">Pulsieren</option>
                <option value="strobe">Stroboskop</option>
                <option value="rainbow">Regenbogen</option>
                <option value="fade">Verblassen</option>
              </select>
            </div>

            <div className="control-group">
              <label>Intensität: {Math.round(intensity * 100)}%</label>
              <input
                type="range"
                min="0.1"
                max="1"
                step="0.1"
                value={intensity}
                onChange={(e) => setIntensity(parseFloat(e.target.value))}
              />
            </div>

            <div className="control-group">
              <label>Geschwindigkeit: {speed}x</label>
              <input
                type="range"
                min="0.1"
                max="3"
                step="0.1"
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
              />
            </div>

            <button className="send-command-btn" onClick={() => sendLightCommand()}>
              Lichteffekt Senden
            </button>
          </div>
        </div>

        {/* Quick Effects */}
        <div className="control-section">
          <h3>Schnell-Effekte</h3>
          <div className="quick-effects">
            <button onClick={() => sendLightCommand('rainbow')}>
              🌈 Regenbogen
            </button>
            <button onClick={() => sendLightCommand('pulse')}>
              💓 Puls-Beat
            </button>
            <button onClick={() => sendLightCommand('strobe')}>
              ⚡ Stroboskop
            </button>
            <button 
              onClick={() => {
                const command = {
                  type: 'light_command',
                  data: {
                    command_type: 'off',
                    color: '#000000',
                    effect: 'solid',
                    intensity: 0,
                    speed: 1,
                    section: 'all'
                  }
                };
                wsRef.current.send(JSON.stringify(command));
              }}
            >
              🔴 Aus
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Main App Component
const App = () => {
  const [mode, setMode] = useState('participant'); // 'participant' or 'admin'

  return (
    <div className="App">
      {mode === 'participant' ? (
        <ParticipantScreen />
      ) : (
        <AdminPanel />
      )}
      
      <button 
        className="mode-switch"
        onClick={() => setMode(mode === 'participant' ? 'admin' : 'participant')}
      >
        {mode === 'participant' ? '🎛️ Admin-Modus' : '📱 Teilnehmer-Modus'}
      </button>
    </div>
  );
};

export default App;