document.addEventListener('DOMContentLoaded', () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/parakeet`;
    
    let socket = null;
    let wakeWordListener = null;
    let chartRenderer = new UIChartRenderer('visualOutput');

    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const micBtn = document.getElementById('micBtn');
    const transcriptBox = document.getElementById('transcriptBox');
    const responseCard = document.getElementById('responseCard');
    const textForm = document.getElementById('textForm');
    const textInput = document.getElementById('textInput');

    // Speech Synthesis TTS Voice Engine
    function speakText(text) {
        if (!('speechSynthesis' in window)) return;
        
        window.speechSynthesis.cancel();
        const cleanText = text.replace(/```json[\s\S]*?```/g, '').replace(/[*_#`]/g, '').trim();
        if (!cleanText) return;

        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;
        
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha')));
        if (preferredVoice) {
            utterance.voice = preferredVoice;
        }

        utterance.onstart = () => {
            statusDot.className = 'status-dot online';
            statusText.innerText = '🔊 Speaking response...';
        };

        utterance.onend = () => {
            statusDot.className = 'status-dot online';
            statusText.innerText = 'System Ready. Say "Parakeet"';
        };

        window.speechSynthesis.speak(utterance);
    }

    // 1. Establish persistent WebSocket connection
    function connect() {
        statusText.innerText = 'Connecting to backend...';
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            statusDot.className = 'status-dot online';
            statusText.innerText = 'System Ready. Say "Parakeet"';
            initMic();
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        };

        socket.onclose = () => {
            statusDot.className = 'status-dot';
            statusText.innerText = 'Disconnected. Retrying in 3s...';
            setTimeout(connect, 3000);
        };

        socket.onerror = (err) => {
            console.error('WebSocket Error:', err);
        };
    }

    // 2. Initialize Microphone & Hands-Free Wake-word Listener
    async function initMic() {
        wakeWordListener = new WakeWordListener(
            (audioBuffer) => {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(audioBuffer);
                }
            },
            (state) => {
                if (state === 'listening') {
                    micBtn.classList.add('listening');
                    statusText.innerText = '🎙️ Listening to command...';
                } else if (state === 'idle') {
                    micBtn.classList.remove('listening');
                    statusText.innerText = '⚡ Processing command...';
                }
            },
            'parakeet'
        );
        await wakeWordListener.initMicrophone();
    }

    // 3. Handle Server Inbound WebSocket Messages
    function handleServerMessage(data) {
        if (data.type === 'transcription') {
            transcriptBox.innerText = `Heard: "${data.text}"`;
        } else if (data.type === 'status') {
            statusDot.className = 'status-dot thinking';
            statusText.innerText = '🧠 Analyzing query with ReAct AI...';
        } else if (data.type === 'final_result') {
            statusDot.className = 'status-dot online';
            statusText.innerText = 'System Ready.';
            responseCard.innerText = data.content || 'Analysis complete.';
            
            // Speak response text aloud via TTS voice
            speakText(data.content || '');

            // Render visual payload (charts, tables, metric cards)
            if (data.payload && Object.keys(data.payload).length > 0) {
                chartRenderer.render(data.payload);
            }
        } else if (data.type === 'error') {
            statusDot.className = 'status-dot';
            statusText.innerText = 'Execution Error';
            responseCard.innerText = `Error: ${data.message}`;
            speakText(`Execution Error: ${data.message}`);
        }
    }

    // 4. UI Trigger Events
    micBtn.addEventListener('click', () => {
        if (wakeWordListener) {
            wakeWordListener.triggerListeningWindow(15000, 1500);
        }
    });

    textForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = textInput.value.trim();
        if (text && socket && socket.readyState === WebSocket.OPEN) {
            transcriptBox.innerText = `Sent: "${text}"`;
            socket.send(JSON.stringify({ text: text }));
            textInput.value = '';
        }
    });

    // Quick prompt chip triggers
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const promptText = chip.dataset.prompt;
            textInput.value = promptText;
            textForm.dispatchEvent(new Event('submit'));
        });
    });

    // Warmup SpeechSynthesis voices
    if ('speechSynthesis' in window) {
        window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }

    connect();
});
