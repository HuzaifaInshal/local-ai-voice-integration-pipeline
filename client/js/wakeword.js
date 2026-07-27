class WakeWordListener {
    constructor(onAudioBufferReady, onStatusChange) {
        this.onAudioBufferReady = onAudioBufferReady;
        this.onStatusChange = onStatusChange;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isListening = false;
        this.stream = null;
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
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                this.audioChunks = [];
                const buffer = await audioBlob.arrayBuffer();
                this.onAudioBufferReady(buffer);
                this.isListening = false;
                this.onStatusChange('idle');
            };

            return true;
        } catch (err) {
            console.error("Microphone permission denied or unavailable:", err);
            this.onStatusChange('mic_error');
            return false;
        }
    }

    triggerListeningWindow(durationMs = 4000) {
        if (!this.mediaRecorder) {
            console.warn("Microphone not initialized.");
            return;
        }

        if (this.isListening) return;

        this.isListening = true;
        this.audioChunks = [];
        this.mediaRecorder.start();
        this.onStatusChange('listening');

        setTimeout(() => {
            if (this.mediaRecorder.state === "recording") {
                this.mediaRecorder.stop();
            }
        }, durationMs);
    }
}

window.WakeWordListener = WakeWordListener;
