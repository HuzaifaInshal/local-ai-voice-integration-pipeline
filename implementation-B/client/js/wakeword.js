class WakeWordListener {
    constructor(onCommandTextReady, onStatusChange, onInstantTranscript) {
        this.onCommandTextReady = onCommandTextReady;
        this.onStatusChange = onStatusChange;
        this.onInstantTranscript = onInstantTranscript;
        
        this.isListeningCommand = false;
        this.stream = null;
        this.audioContext = null;
        this.analyser = null;
        this.recognition = null;
        this.silenceTimer = null;
        this.currentCommandText = "";
    }

    async initMicrophone() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.setupAudioContext();
            this.startContinuousSpeechRecognition();
            return true;
        } catch (err) {
            console.error("Microphone permission denied or unavailable:", err);
            this.onStatusChange('mic_error');
            return false;
        }
    }

    setupAudioContext() {
        if (!this.stream || this.audioContext) return;
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioCtx();
            const source = this.audioContext.createMediaStreamSource(this.stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 64;
            source.connect(this.analyser);
        } catch (e) {
            console.warn("AudioContext setup error:", e);
        }
    }

    startContinuousSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn("Web Speech API not supported. Tap to speak.");
            return;
        }

        try {
            if (this.recognition) {
                try { this.recognition.abort(); } catch (e) {}
            }

            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onresult = (event) => {
                let fullTranscript = '';
                let latestInterim = '';

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    const res = event.results[i];
                    const text = res[0].transcript;
                    if (res.isFinal) {
                        fullTranscript += text;
                    } else {
                        latestInterim += text;
                    }
                }

                const liveText = (fullTranscript + ' ' + latestInterim).trim();

                // 1. Wake-word Detection when in Idle mode
                if (!this.isListeningCommand) {
                    const lowerText = liveText.toLowerCase();
                    const wakeWordRegex = /\b(hey\s+)?(alfa|alpha|elba|elfa)\b/i;

                    if (wakeWordRegex.test(lowerText)) {
                        console.log(`🎯 Wake-word detected in live text: "${liveText}"`);
                        this.startListeningCommand();
                    }
                } else {
                    // 2. Active Command Listening Mode: Instant Word-by-Word Transcript Update
                    let commandSpeech = liveText;
                    // Strip leading wake word if present
                    commandSpeech = commandSpeech.replace(/^.*?\b(hey\s+)?(alfa|alpha|elba|elfa)\b[\s,]*/i, '').trim();

                    if (commandSpeech) {
                        this.currentCommandText = commandSpeech;
                        if (this.onInstantTranscript) {
                            this.onInstantTranscript(commandSpeech);
                        }

                        // Reset silence auto-submit timer on active speech
                        this.resetSilenceTimer();
                    }
                }
            };

            this.recognition.onend = () => {
                if (this.recognition) {
                    try { this.recognition.start(); } catch (e) {}
                }
            };

            this.recognition.onerror = (err) => {
                console.warn("SpeechRecognition error:", err);
            };

            this.recognition.start();
            console.log("👂 Speech listener active for: Hey Alfa");
        } catch (e) {
            console.warn("Could not start continuous speech recognition:", e);
        }
    }

    startListeningCommand() {
        this.isListeningCommand = true;
        this.currentCommandText = "";
        this.onStatusChange('listening');
        this.resetSilenceTimer(2500); // 2.5s silence auto-submit
    }

    resetSilenceTimer(delayMs = 2000) {
        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
        }

        this.silenceTimer = setTimeout(() => {
            if (this.isListeningCommand && this.currentCommandText.trim()) {
                console.log(`🚀 Submitting command text: "${this.currentCommandText}"`);
                const textToSubmit = this.currentCommandText.trim();
                this.isListeningCommand = false;
                this.onStatusChange('idle');
                this.onCommandTextReady(textToSubmit);
            }
        }, delayMs);
    }

    triggerManualListening() {
        this.startListeningCommand();
    }
}

window.WakeWordListener = WakeWordListener;
