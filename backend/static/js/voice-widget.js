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
    
    init: function(config) {
      this.config = config;
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
      
      console.log('Connecting to:', wsUrl);
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        console.log('Connected to voice agent');
        this.isConnected = true;
        this.startAudioCapture();
      };
      
      this.ws.onmessage = (event) => {
        // Check if data is binary (Blob/ArrayBuffer) or text (JSON)
        if (event.data instanceof Blob) {
          // Handle binary audio data
          this.playAudio(event.data);
        } else if (typeof event.data === 'string') {
          // Handle JSON messages
          try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'transcript') {
              this.updateTranscript(data.text);
            } else if (data.type === 'audio') {
              this.playAudio(data.data);
            } else if (data.type === 'error') {
              this.showError(data.message || 'An error occurred');
            }
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
        console.log('Disconnected from voice agent');
        this.isConnected = false;
        this.stopAudioCapture();
      };
    },
    
    startAudioCapture: function() {
      navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
          channelCount: 1
        }
      })
        .then(stream => {
          this.audioStream = stream;
          this.audioContext = new AudioContext({ sampleRate: 16000 });
          const source = this.audioContext.createMediaStreamSource(stream);
          
          // Note: ScriptProcessorNode is deprecated but still works
          // For production, consider migrating to AudioWorkletNode
          this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
          
          // Don't connect processor to destination to avoid echo
          source.connect(this.processor);
          // this.processor.connect(this.audioContext.destination); // REMOVED to prevent echo
          
          this.processor.onaudioprocess = (e) => {
            if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
              const inputData = e.inputBuffer.getChannelData(0);
              const pcmData = this.floatTo16BitPCM(inputData);
              
              // Send as binary data
              this.ws.send(pcmData);
            }
          };
          
          console.log('✓ Microphone connected');
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
      console.log('Audio received from agent');
      
      // Initialize audio context if not already done
      if (!this.playbackAudioContext) {
        this.playbackAudioContext = new AudioContext({ sampleRate: 24000 });
      }
      
      // Handle Blob audio data (raw PCM from Gemini)
      if (audioData instanceof Blob) {
        audioData.arrayBuffer().then(buffer => {
          this.playRawPCM(buffer);
        });
      } else if (audioData instanceof ArrayBuffer) {
        this.playRawPCM(audioData);
      }
    },
    
    playRawPCM: function(arrayBuffer) {
      // Skip if buffer is too small (might be noise)
      if (arrayBuffer.byteLength < 100) {
        console.log('Skipping tiny audio chunk');
        return;
      }
      
      // Convert raw PCM16 to playable audio
      const int16Array = new Int16Array(arrayBuffer);
      const float32Array = new Float32Array(int16Array.length);
      
      // Convert Int16 PCM to Float32 for Web Audio API
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }
      
      // Create audio buffer
      const audioBuffer = this.playbackAudioContext.createBuffer(
        1, // mono
        float32Array.length,
        24000 // sample rate (Gemini uses 24kHz)
      );
      
      // Copy data to buffer
      audioBuffer.getChannelData(0).set(float32Array);
      
      // Create and play source
      const source = this.playbackAudioContext.createBufferSource();
      source.buffer = audioBuffer;
      
      // Add a gain node to control volume
      const gainNode = this.playbackAudioContext.createGain();
      gainNode.gain.value = 0.8; // Slightly reduce volume to prevent clipping
      
      source.connect(gainNode);
      gainNode.connect(this.playbackAudioContext.destination);
      source.start(0);
      
      // Update UI
      const transcript = document.getElementById('weevoice-transcript');
      if (transcript) {
        transcript.textContent = 'Agent is speaking...';
        transcript.style.color = '#10b981'; // green
      }
      
      // Reset after audio finishes
      source.onended = () => {
        if (transcript) {
          transcript.textContent = 'Listening...';
          transcript.style.color = '#6b7280'; // gray
        }
      };
      
      console.log('🔊 Playing audio response');
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

