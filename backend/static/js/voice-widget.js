/**
 * WeeVoice Widget - Voice Agent Embed Widget
 * This widget allows users to interact with voice agents on any website
 */

(function() {
  'use strict';

  window.WeeVoiceWidget = {
    config: null,
    isOpen: false,
    isConnected: false,
    audioQueue: [],  // Queue for smooth audio playback
    nextPlayTime: 0,  // Track next scheduled play time for seamless playback
    
    init: function(config) {
      this.config = config;
      this.audioQueue = [];
      this.nextPlayTime = 0;
      this.createWidget();
      this.attachEventListeners();
    },
    
    createWidget: function() {
      // Create widget container
      const container = document.createElement('div');
      container.id = 'weevoice-widget';
      container.className = `weevoice-widget ${this.config.position}`;
      
      // Create widget button
      const button = document.createElement('button');
      button.id = 'weevoice-button';
      button.className = 'weevoice-button';
      button.style.backgroundColor = this.config.color;
      button.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="24" height="24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
        </svg>
      `;
      
      // Create widget panel
      const panel = document.createElement('div');
      panel.id = 'weevoice-panel';
      panel.className = 'weevoice-panel hidden';
      panel.innerHTML = `
        <div class="weevoice-header" style="background-color: ${this.config.color}">
          <h3>${this.config.agentName}</h3>
          <button id="weevoice-close" class="weevoice-close">×</button>
        </div>
        <div class="weevoice-body">
          <div id="weevoice-status" class="weevoice-status">
            <p>${this.config.greeting}</p>
            <button id="weevoice-start" class="weevoice-start-btn" style="background-color: ${this.config.color}">
              Start Voice Call
            </button>
          </div>
          <div id="weevoice-call" class="weevoice-call hidden">
            <div class="weevoice-waveform">
              <div class="weevoice-wave"></div>
              <div class="weevoice-wave"></div>
              <div class="weevoice-wave"></div>
              <div class="weevoice-wave"></div>
            </div>
            <p id="weevoice-transcript" class="weevoice-transcript"></p>
            <button id="weevoice-end" class="weevoice-end-btn">
              End Call
            </button>
          </div>
        </div>
      `;
      
      container.appendChild(button);
      container.appendChild(panel);
      document.body.appendChild(container);
    },
    
    attachEventListeners: function() {
      const button = document.getElementById('weevoice-button');
      const panel = document.getElementById('weevoice-panel');
      const closeBtn = document.getElementById('weevoice-close');
      const startBtn = document.getElementById('weevoice-start');
      const endBtn = document.getElementById('weevoice-end');
      
      button.addEventListener('click', () => {
        this.togglePanel();
      });
      
      closeBtn.addEventListener('click', () => {
        this.closePanel();
      });
      
      startBtn.addEventListener('click', () => {
        this.startCall();
      });
      
      endBtn.addEventListener('click', () => {
        this.endCall();
      });
    },
    
    togglePanel: function() {
      const panel = document.getElementById('weevoice-panel');
      if (this.isOpen) {
        this.closePanel();
      } else {
        panel.classList.remove('hidden');
        this.isOpen = true;
      }
    },
    
    closePanel: function() {
      const panel = document.getElementById('weevoice-panel');
      panel.classList.add('hidden');
      this.isOpen = false;
      
      if (this.isConnected) {
        this.endCall();
      }
    },
    
    startCall: function() {
      // Show call interface
      document.getElementById('weevoice-status').classList.add('hidden');
      document.getElementById('weevoice-call').classList.remove('hidden');
      
      // Connect to voice agent
      this.connectToAgent();
    },
    
    connectToAgent: function() {
      // Connect to the WebSocket endpoint
      const wsUrl = `${this.config.apiUrl.replace('http', 'ws')}/api/v1/ws/voice/${this.config.agentId}`;
      
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        this.isConnected = true;
        this.startAudioCapture();
      };
      
      this.ws.onmessage = (event) => {
        // Track message count for diagnostics
        if (!this._wsMessageCount) this._wsMessageCount = 0;
        this._wsMessageCount++;
        
        // Check if data is binary (Blob) or text (JSON)
        if (event.data instanceof Blob) {
          // Handle binary audio data (raw PCM from Gemini)
          if (this._wsMessageCount <= 5) {
            console.log(`📨 WS Message #${this._wsMessageCount}: Blob audio (${event.data.size} bytes)`);
          }
          this.playAudio(event.data);
        } else if (typeof event.data === 'string') {
          // Handle JSON messages (session_started, error, etc.)
          try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'session_started') {
              console.log('✓ Session started');
            } else if (data.type === 'error') {
              console.error('Backend error:', data.message);
              this.showError(data.message || 'An error occurred');
            }
            // Note: Transcript and audio come as separate Blob messages, not in JSON
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        }
      };
      
      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.showError('Connection error. Please try again.');
      };
      
      this.ws.onclose = () => {
        this.isConnected = false;
        this.stopAudioCapture();
      };
    },
    
    startAudioCapture: function() {
      // CRITICAL: Use simple audio constraint matching DemoPage.tsx exactly
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
          this.audioStream = stream;
          
          // Clear audio queue and reset timing (matching DemoPage)
          this.audioQueue = [];
          this.nextPlayTime = 0;
          
          // Set up audio context for recording
          this.audioContext = new AudioContext({ sampleRate: 16000 });
          const source = this.audioContext.createMediaStreamSource(stream);
          
          // Create processor for audio chunks
          this.processor = this.audioContext.createScriptProcessor(2048, 1, 1);
          
          // Connect audio graph (MUST match working apps exactly)
          source.connect(this.processor);
          this.processor.connect(this.audioContext.destination);
          
          this.processor.onaudioprocess = (e) => {
            if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
              const inputData = e.inputBuffer.getChannelData(0);
              const int16Array = new Int16Array(inputData.length);
              
              // Convert float32 to int16 (matching DemoPage exactly)
              for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
              }
              
              // Send as binary data
              this.ws.send(int16Array.buffer);
            }
          };
          
          // Set up audio player for responses (BEFORE WebSocket)
          // DON'T force 24kHz - let browser use native rate and resample automatically
          this.playbackAudioContext = new AudioContext();
          
          // Check browser's native sample rate
          const actualRate = this.playbackAudioContext.sampleRate;
          
          // if (actualRate !== 24000) {
          //   console.log(`   ℹ️ This is NORMAL and should work correctly`);
          // } else {
          //   console.log('   ✓ Rates match perfectly!');
          // }
          
          this._actualSampleRate = actualRate;
        })
        .catch(error => {
          console.error('Error accessing microphone:', error);
          this.showError('Could not access microphone. Please allow microphone access and try again.');
        });
    },
    
    stopAudioCapture: function() {
      if (this.audioStream) {
        this.audioStream.getTracks().forEach(track => track.stop());
        this.audioStream = null;
      }
      
      if (this.processor) {
        this.processor.disconnect();
        this.processor = null;
      }
      
      if (this.audioContext) {
        this.audioContext.close();
        this.audioContext = null;
      }
      
      // Close playback context too
      if (this.playbackAudioContext) {
        this.playbackAudioContext.close();
        this.playbackAudioContext = null;
      }
      
      // Clear audio queue and reset timing
      this.audioQueue = [];
      this.nextPlayTime = 0;
    },
    
    floatTo16BitPCM: function(float32Array) {
      const buffer = new ArrayBuffer(float32Array.length * 2);
      const view = new DataView(buffer);
      let offset = 0;
      
      for (let i = 0; i < float32Array.length; i++, offset += 2) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      }
      
      return buffer;
    },
    
    playAudio: function(audioData) {
      // Ensure audio context is running (required for playback)
      if (this.playbackAudioContext && this.playbackAudioContext.state === 'suspended') {
        console.warn('⚠️ AudioContext suspended, resuming...');
        this.playbackAudioContext.resume().then(() => {
          this.processAudioData(audioData);
        });
      } else {
        this.processAudioData(audioData);
      }
    },
    
    processAudioData: function(audioData) {
      // Handle Blob audio data (raw PCM from Gemini)
      if (audioData instanceof Blob) {
        audioData.arrayBuffer().then(buffer => {
          this.playRawPCM(buffer);
        }).catch(error => {
          console.error('❌ Error converting Blob to ArrayBuffer:', error);
        });
      } else if (audioData instanceof ArrayBuffer) {
        this.playRawPCM(audioData);
      }
    },
    
    playRawPCM: function(arrayBuffer) {
      // Skip if buffer is too small (might be noise/silence)
      if (arrayBuffer.byteLength < 200) {
        return;
      }
      
      // Verify playback context exists
      if (!this.playbackAudioContext) {
        console.error('❌ Playback context not initialized!');
        return;
      }
      
      // Initialize chunk counter
      if (!this._audioChunkCount) {
        this._audioChunkCount = 0;
      }
      this._audioChunkCount++;
      
      // Convert raw PCM16 to Float32
      // Int16Array reads little-endian by default (matches backend output)
      const int16Array = new Int16Array(arrayBuffer);
      const float32Array = new Float32Array(int16Array.length);
      
      // Convert Int16 PCM to Float32 (range -1 to 1)
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }
      
      // Log first few chunks for debugging
      if (this._audioChunkCount <= 3) {
        if (this._audioChunkCount === 1) {
          let sum = 0;
          for (let i = 0; i < Math.min(1000, float32Array.length); i++) {
            sum += float32Array[i] * float32Array[i];
          }
          const rms = Math.sqrt(sum / Math.min(1000, float32Array.length));
        }
      }
      
      // Add to queue and schedule immediately
      this.audioQueue.push(float32Array);
      this.playAudioQueue();
      
      // Update UI
      const transcript = document.getElementById('weevoice-transcript');
      if (transcript) {
        transcript.textContent = 'Agent is speaking...';
        transcript.style.color = '#10b981'; // green
      }
    },
    
    playAudioQueue: function() {
      if (!this.playbackAudioContext || this.audioQueue.length === 0) {
        return;
      }
      
      const audioContext = this.playbackAudioContext;
      const currentTime = audioContext.currentTime;
      
      // Initialize next play time if not set or if it's in the past
      if (this.nextPlayTime < currentTime) {
        this.nextPlayTime = currentTime;
      }
      
      // Schedule all queued chunks
      let chunkCount = 0;
      while (this.audioQueue.length > 0) {
        const audioData = this.audioQueue.shift();
        chunkCount++;
        
        try {
          // CRITICAL: Always create buffer at 24000 Hz (Gemini's actual output)
          // If context is different, browser will resample automatically
          const audioBuffer = audioContext.createBuffer(1, audioData.length, 24000);
          audioBuffer.getChannelData(0).set(audioData);
          
          // Log buffer creation details for first few chunks
          if (chunkCount <= 2) {
            if (audioContext.sampleRate !== 24000) {
              console.log(`   Browser resamples: 24kHz → ${audioContext.sampleRate}Hz (automatic)`);
            }
          }
          
          // Create source
          const source = audioContext.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(audioContext.destination);
          
          // Schedule to start exactly when the previous chunk ends
          source.start(this.nextPlayTime);
          
          // Update next play time (add duration of this chunk)
          this.nextPlayTime += audioBuffer.duration;
          
          // Reset transcript when last chunk finishes
          if (this.audioQueue.length === 0) {
            source.onended = () => {
              const transcript = document.getElementById('weevoice-transcript');
              if (transcript) {
                transcript.textContent = 'Listening...';
                transcript.style.color = '#6b7280'; // gray
              }
            };
          }
        } catch (error) {
          console.error('Error scheduling audio chunk:', error, error.stack);
        }
      }
    },
    
    updateTranscript: function(text) {
      const transcript = document.getElementById('weevoice-transcript');
      transcript.textContent = text;
    },
    
    showError: function(message) {
      const transcript = document.getElementById('weevoice-transcript');
      transcript.textContent = '❌ ' + message;
      transcript.style.color = '#ef4444';
    },
    
    endCall: function() {
      if (this.ws) {
        this.ws.close();
      }
      
      this.stopAudioCapture();
      
      // Reset UI
      document.getElementById('weevoice-call').classList.add('hidden');
      document.getElementById('weevoice-status').classList.remove('hidden');
      document.getElementById('weevoice-transcript').textContent = '';
      
      this.isConnected = false;
    }
  };
})();

