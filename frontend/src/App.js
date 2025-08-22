import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('http', 'ws');

// Audio Analysis Hook for Beat Detection
const useAudioAnalysis = () => {
  const [audioContext, setAudioContext] = useState(null);
  const [analyser, setAnalyser] = useState(null);
  const [isListening, setIsListening] = useState(false);
  const [bpm, setBpm] = useState(0);
  const [beatIntensity, setBeatIntensity] = useState(0);
  
  const beatDetectionRef = useRef(null);
  const beatTimesRef = useRef([]);

  const startAudioAnalysis = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const context = new AudioContext();
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      
      analyser.fftSize = 2048;
      source.connect(analyser);
      
      setAudioContext(context);
      setAnalyser(analyser);
      setIsListening(true);
      
      // Start beat detection
      detectBeats(analyser);
      
    } catch (error) {
      console.error('Error accessing microphone:', error);
    }
  };

  const detectBeats = (analyser) => {
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    const detectBeat = () => {
      if (!isListening) return;
      
      analyser.getByteFrequencyData(dataArray);
      
      // Focus on bass frequencies (0-100Hz roughly corresponds to first 10-20% of bins)
      const bassEnd = Math.floor(bufferLength * 0.15);
      let bassSum = 0;
      
      for (let i = 0; i < bassEnd; i++) {
        bassSum += dataArray[i];
      }
      
      const bassAverage = bassSum / bassEnd;
      const normalizedIntensity = bassAverage / 255;
      
      setBeatIntensity(normalizedIntensity);
      
      // Simple beat detection: if bass exceeds threshold
      if (normalizedIntensity > 0.7) {
        const currentTime = Date.now();
        beatTimesRef.current.push(currentTime);
        
        // Keep only beats from last 10 seconds
        beatTimesRef.current = beatTimesRef.current.filter(
          time => currentTime - time < 10000
        );
        
        // Calculate BPM from recent beats
        if (beatTimesRef.current.length > 2) {
          const intervals = [];
          for (let i = 1; i < beatTimesRef.current.length; i++) {
            intervals.push(beatTimesRef.current[i] - beatTimesRef.current[i-1]);
          }
          
          const averageInterval = intervals.reduce((a, b) => a + b) / intervals.length;
          const calculatedBpm = Math.round(60000 / averageInterval);
          
          if (calculatedBpm > 60 && calculatedBpm < 200) {
            setBpm(calculatedBpm);
          }
        }
      }
      
      beatDetectionRef.current = requestAnimationFrame(detectBeat);
    };
    
    detectBeat();
  };

  const stopAudioAnalysis = () => {
    setIsListening(false);
    if (beatDetectionRef.current) {
      cancelAnimationFrame(beatDetectionRef.current);
    }
    if (audioContext) {
      audioContext.close();
    }
  };

  return {
    startAudioAnalysis,
    stopAudioAnalysis,
    isListening,
    bpm,
    beatIntensity
  };
};

// Participant Light Screen Component with Beat Sync
const ParticipantScreen = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [currentColor, setCurrentColor] = useState('#3B82F6');
  const [isActive, setIsActive] = useState(false);
  const [section, setSection] = useState('all');
  const [beatSyncMode, setBeatSyncMode] = useState(false);
  
  const wsRef = useRef(null);
  const animationRef = useRef(null);
  const beatSyncRef = useRef(null);

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
  }, [section]);

  const connectWebSocket = () => {
    try {
      const wsUrl = `${WS_URL}/ws/participant/${section}`;
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        setIsConnected(true);
        console.log(`Connected to light sync system - Section: ${section}`);
      };
      
      wsRef.current.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleLightCommand(message);
      };
      
      wsRef.current.onclose = () => {
        setIsConnected(false);
        console.log('Disconnected from light sync system - using polling fallback');
        startPollingFallback();
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
        startPollingFallback();
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      startPollingFallback();
    }
  };

  const startPollingFallback = () => {
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
        
        // Also check for beat data
        const beatResponse = await fetch(`${API}/latest-beat`);
        if (beatResponse.ok) {
          const beatData = await beatResponse.json();
          if (beatData && beatData.beat) {
            handleBeatSync(beatData.beat);
          }
        }
      } catch (error) {
        console.error('Polling fallback error:', error);
      }
    }, 1000);
    
    wsRef.current = { pollInterval };
  };

  const handleLightCommand = (message) => {
    if (message.type === 'light_command') {
      const { command_type, color, effect, intensity, speed, duration, wave_delay } = message.data;
      
      // Handle wave delay
      const delay = wave_delay || 0;
      
      setTimeout(() => {
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
          case 'wave':
            startWaveEffect(color, intensity, speed, duration);
            break;
          default:
            setSolidColor(color, intensity, duration);
        }
      }, delay);
      
    } else if (message.type === 'beat_sync') {
      handleBeatSync(message.data);
    }
  };

  const handleBeatSync = (beatData) => {
    if (!beatData) return;
    
    setBeatSyncMode(true);
    
    // Create beat-responsive flash
    const beatColor = adjustColorIntensity('#FFFFFF', beatData.intensity);
    setCurrentColor(beatColor);
    
    // Quick flash effect
    setTimeout(() => {
      setCurrentColor('#000000');
    }, 100);
    
    // Clear beat sync mode after a short time
    clearTimeout(beatSyncRef.current);
    beatSyncRef.current = setTimeout(() => {
      setBeatSyncMode(false);
    }, 2000);
  };

  const startWaveEffect = (color, intensity, speed, duration) => {
    const waveIntensity = intensity;
    let startTime = Date.now();
    
    const animate = () => {
      const elapsed = Date.now() - startTime;
      if (duration && elapsed > duration) {
        setIsActive(false);
        return;
      }
      
      // Create wave effect with varying intensity
      const waveValue = Math.sin(elapsed * speed * 0.005) * 0.5 + 0.5;
      const adjustedColor = adjustColorIntensity(color, waveIntensity * waveValue);
      setCurrentColor(adjustedColor);
      
      animationRef.current = requestAnimationFrame(animate);
    };
    animate();
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
    return color2; // Simplified for now
  };

  const changeSectionAndReconnect = (newSection) => {
    setSection(newSection);
    if (wsRef.current && wsRef.current.close) {
      wsRef.current.close();
    }
    // Reconnection will happen automatically via useEffect dependency on section
  };

  return (
    <div 
      className={`participant-screen ${beatSyncMode ? 'beat-sync-mode' : ''}`}
      style={{ backgroundColor: currentColor }}
    >
      <div className="connection-status">
        <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '🔗 Verbunden' : '❌ Getrennt'}
        </div>
        <div className="festival-info">
          <h1>🎵 Festival Light Sync</h1>
          <p>Halten Sie Ihr Handy hoch und lassen Sie es leuchten!</p>
          
          {/* Section Selection */}
          <div className="section-selector">
            <h3>Wählen Sie Ihren Bereich:</h3>
            <div className="section-buttons">
              <button 
                className={section === 'left' ? 'active' : ''}
                onClick={() => changeSectionAndReconnect('left')}
              >
                ⬅️ Links
              </button>
              <button 
                className={section === 'center' ? 'active' : ''}
                onClick={() => changeSectionAndReconnect('center')}
              >
                🎯 Mitte
              </button>
              <button 
                className={section === 'right' ? 'active' : ''}
                onClick={() => changeSectionAndReconnect('right')}
              >
                ➡️ Rechts
              </button>
              <button 
                className={section === 'all' ? 'active' : ''}
                onClick={() => changeSectionAndReconnect('all')}
              >
                🌐 Alle
              </button>
            </div>
          </div>
          
          {beatSyncMode && (
            <div className="beat-sync-indicator">
              🎵 Beat-Synchronisation Aktiv
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Enhanced Admin Control Panel
const AdminPanel = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [sectionStats, setSectionStats] = useState({
    total: 0, left: 0, center: 0, right: 0
  });
  const [selectedColor, setSelectedColor] = useState('#FF0000');
  const [selectedEffect, setSelectedEffect] = useState('solid');
  const [selectedSection, setSelectedSection] = useState('all');
  const [intensity, setIntensity] = useState(1.0);
  const [speed, setSpeed] = useState(1.0);
  const [beatSyncEnabled, setBeatSyncEnabled] = useState(false);
  
  const wsRef = useRef(null);
  const { startAudioAnalysis, stopAudioAnalysis, isListening, bpm, beatIntensity } = useAudioAnalysis();

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
    };
  }, []);

  // Send beat data to backend when detecting beats
  useEffect(() => {
    if (isListening && beatSyncEnabled && bpm > 0) {
      const sendBeatData = async () => {
        try {
          await fetch(`${API}/beat-data`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              bpm: bpm,
              intensity: beatIntensity,
              timestamp: new Date().toISOString()
            })
          });
        } catch (error) {
          console.error('Error sending beat data:', error);
        }
      };
      
      const beatInterval = setInterval(sendBeatData, 100); // Send beat data every 100ms
      return () => clearInterval(beatInterval);
    }
  }, [isListening, beatSyncEnabled, bpm, beatIntensity]);

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
          setSectionStats(message.section_stats || message.participant_count);
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
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API}/stats`);
        if (response.ok) {
          const stats = await response.json();
          setSectionStats(stats.sections);
          setIsConnected(true);
        }
      } catch (error) {
        console.error('Admin polling error:', error);
        setIsConnected(false);
      }
    }, 2000);
    
    wsRef.current = { pollInterval };
  };

  const sendLightCommand = async (overrideEffect = null, overrideSection = null) => {
    const command = {
      command_type: 'effect',
      color: selectedColor,
      effect: overrideEffect || selectedEffect,
      intensity: intensity,
      speed: speed,
      duration: selectedEffect === 'solid' ? null : 5000,
      section: overrideSection || selectedSection,
      wave_direction: 'left_to_right'
    };

    try {
      const response = await fetch(`${API}/light-command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

  const sendPreset = async (presetName) => {
    try {
      const response = await fetch(`${API}/preset/${presetName}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        console.log(`Preset ${presetName} sent successfully`);
      }
    } catch (error) {
      console.error('Error sending preset:', error);
    }
  };

  const toggleBeatSync = async () => {
    if (!beatSyncEnabled) {
      await startAudioAnalysis();
    } else {
      stopAudioAnalysis();
    }
    setBeatSyncEnabled(!beatSyncEnabled);
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
        <h1>🎛️ Festival Light Control - Phase 2</h1>
        <div className="connection-info">
          <span className={`admin-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '✅ Verbunden' : '❌ Getrennt'}
          </span>
          <div className="section-stats">
            <div>👥 Gesamt: {sectionStats.total}</div>
            <div>⬅️ Links: {sectionStats.left}</div>
            <div>🎯 Mitte: {sectionStats.center}</div>
            <div>➡️ Rechts: {sectionStats.right}</div>
          </div>
        </div>
      </div>

      <div className="control-sections">
        
        {/* Beat Sync Control */}
        <div className="control-section beat-sync-section">
          <h3>🎵 Beat-Synchronisation</h3>
          <div className="beat-controls">
            <button 
              className={`beat-sync-btn ${beatSyncEnabled ? 'active' : ''}`}
              onClick={toggleBeatSync}
            >
              {beatSyncEnabled ? '⏹️ Beat Sync Stop' : '🎵 Beat Sync Start'}
            </button>
            
            {isListening && (
              <div className="beat-display">
                <div className="bpm-display">BPM: {bpm}</div>
                <div className="intensity-bar">
                  <div 
                    className="intensity-fill" 
                    style={{ width: `${beatIntensity * 100}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Section Control */}
        <div className="control-section">
          <h3>🎯 Bereich-Steuerung</h3>
          <div className="section-controls">
            <select 
              value={selectedSection} 
              onChange={(e) => setSelectedSection(e.target.value)}
            >
              <option value="all">🌐 Alle Bereiche</option>
              <option value="left">⬅️ Links ({sectionStats.left})</option>
              <option value="center">🎯 Mitte ({sectionStats.center})</option>
              <option value="right">➡️ Rechts ({sectionStats.right})</option>
            </select>
          </div>
        </div>

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

        {/* Advanced Effects */}
        <div className="control-section">
          <h3>Erweiterte Effekte</h3>
          <div className="advanced-effects">
            <button onClick={() => sendLightCommand('wave')}>
              🌊 Wellen-Effekt
            </button>
            <button onClick={() => sendPreset('party_mode')}>
              🎉 Party-Modus
            </button>
            <button onClick={() => sendPreset('calm_wave')}>
              🌊 Ruhige Welle
            </button>
            <button onClick={() => sendPreset('festival_finale')}>
              🎆 Festival Finale
            </button>
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
                <option value="wave">Welle</option>
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
                fetch(`${API}/light-command`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    command_type: 'off',
                    color: '#000000',
                    effect: 'solid',
                    intensity: 0,
                    speed: 1,
                    section: 'all'
                  })
                });
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
  const [mode, setMode] = useState('participant');

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