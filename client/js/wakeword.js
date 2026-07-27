class WakeWordListener {
    constructor(onAudioBufferReady, onStatusChange, wakeWord = "parakeet") {
        this.onAudioBufferReady = onAudioBufferReady;
        this.onStatusChange = onStatusChange;
        this.wakeWord = wakeWord.toLowerCase();
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isListeningCommand = false;
        this.stream = null;
        this.audioContext = null;
        this.analyser = null;
        this.vadInterval = null;
        this.maxSafetyTimeout = null;
        this.recognition = null;
    }

    async initMicrophone() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(this.stream);
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = async () => {
                this.stopVAD();
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                this.audioChunks = [];
                const buffer = await audioBlob.arrayBuffer();
                this.onAudioBufferReady(buffer);
                this.isListeningCommand = false;
                this.onStatusChange('idle');

                // Resume background wake-word listener after command finishes
                setTimeout(() => this.startWakeWordDetection(), 1000);
            };

            // Start active hands-free wake-word detection
            this.startWakeWordDetection();
            return true;
        } catch (err) {
            console.error("Microphone permission denied or unavailable:", err);
            this.onStatusChange('mic_error');
            return false;
        }
    }

    // 1. Hands-Free Wake-Word Detector ("Parakeet")
    startWakeWordDetection() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn("Web Speech API not supported in this browser. Use manual mic button.");
            return;
        }

        if (this.isListeningCommand) return;

        try {
            if (this.recognition) {
                this.recognition.abort();
            }

            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onresult = (event) => {
                if (this.isListeningCommand) return;

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    const transcript = event.results[i][0].transcript.toLowerCase().trim();
                    console.log("Background listening transcript:", transcript);

                    if (transcript.includes(this.wakeWord)) {
                        console.log(`🎯 Wake-word "${this.wakeWord}" detected! Activating command recorder...`);
                        this.stopWakeWordDetection();
                        this.triggerListeningWindow(15000, 1500);
                        break;
                    }
                }
            };

            this.recognition.onend = () => {
                if (!this.isListeningCommand && this.recognition) {
                    try { this.recognition.start(); } catch(e) {}
                }
            };

            this.recognition.start();
            console.log(`👂 Background wake-word listener active for: "${this.wakeWord}"`);
        } catch (e) {
            console.warn("Could not start background wake-word recognition:", e);
        }
    }

    stopWakeWordDetection() {
        if (this.recognition) {
            try {
                this.recognition.onend = null;
                this.recognition.abort();
            } catch (e) {}
            this.recognition = null;
        }
    }

    // 2. Command Voice Activity Detection (VAD) Recorder
    triggerListeningWindow(maxDurationMs = 15000, silenceDelayMs = 1500, noiseThreshold = 0.015) {
        if (!this.mediaRecorder) {
            console.warn("Microphone not initialized.");
            return;
        }

        if (this.isListeningCommand) return;

        this.stopWakeWordDetection();
        this.isListeningCommand = true;
        this.audioChunks = [];
        this.mediaRecorder.start();
        this.onStatusChange('listening');

        // WebAudio VAD: Dynamic silence detection
        this.startVAD(silenceDelayMs, noiseThreshold);

        // Safety max timeout
        this.maxSafetyTimeout = setTimeout(() => {
            this.stopListening();
        }, maxDurationMs);
    }

    startVAD(silenceDelayMs, noiseThreshold) {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioCtx();
            const source = this.audioContext.createMediaStreamSource(this.stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 512;
            source.connect(this.analyser);

            const bufferLength = this.analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            let lastSpeechTime = Date.now();
            let hasSpeechStarted = false;

            this.vadInterval = setInterval(() => {
                if (!this.isListeningCommand) return;

                this.analyser.getByteFrequencyData(dataArray);
                let sum = 0;
                for (let i = 0; i < bufferLength; i++) {
                    sum += dataArray[i];
                }
                const averageVolume = sum / bufferLength / 255.0;

                if (averageVolume > noiseThreshold) {
                    hasSpeechStarted = true;
                    lastSpeechTime = Date.now();
                } else if (hasSpeechStarted) {
                    const silentDuration = Date.now() - lastSpeechTime;
                    if (silentDuration >= silenceDelayMs) {
                        console.log(`VAD: Silence detected (${silentDuration}ms). Auto-stopping recording.`);
                        this.stopListening();
                    }
                }
            }, 100);
        } catch (e) {
            console.warn("VAD WebAudio setup error, falling back to safety timeout:", e);
        }
    }

    stopVAD() {
        if (this.vadInterval) {
            clearInterval(this.vadInterval);
            this.vadInterval = null;
        }
        if (this.maxSafetyTimeout) {
            clearTimeout(this.maxSafetyTimeout);
            this.maxSafetyTimeout = null;
        }
        if (this.audioContext) {
            this.audioContext.close().catch(() => {});
            this.audioContext = null;
        }
    }

    stopListening() {
        if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
            this.mediaRecorder.stop();
        }
    }
}

window.WakeWordListener = WakeWordListener;
