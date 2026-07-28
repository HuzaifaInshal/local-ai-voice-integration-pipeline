document.addEventListener('DOMContentLoaded', () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/parakeet`;
    
    let socket = null;
    let wakeWordListener = null;
    let chartRenderer = new UIChartRenderer('visualOutput');
    let visualizer = new MusicVisualizer('musicVisualizer');

    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const micBtn = document.getElementById('micBtn');
    const transcriptBox = document.getElementById('transcriptBox');
    const responseCard = document.getElementById('responseCard');
    const visualizerStateTag = document.getElementById('visualizerState');

    function setVisualState(state) {
        if (visualizer) visualizer.setState(state);
        if (visualizerStateTag) {
            visualizerStateTag.innerText = state;
            visualizerStateTag.className = `visualizer-status-tag ${state}`;
        }
    }

    // Markdown Renderer Helper
    function renderMarkdown(text) {
        if (!text) return '';
        let clean = text.replace(/```json[\s\S]*?```/g, '').trim();
        clean = clean.replace(/```[\s\S]*?```/g, '').trim();

        if (window.marked && typeof window.marked.parse === 'function') {
            return window.marked.parse(clean);
        }
        // Fallback markdown parsing
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

        html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

        html = html.replace(/^\s*[-*+]\s+(.*$)/gim, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>');

        html = html.split('\n\n').map(p => {
            if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<li')) return p;
            return `<p>${p.replace(/\n/g, '<br>')}</p>`;
        }).join('');

        return html;
    }

    // Speech Sanitizer helper for smooth natural TTS
    function sanitizeTextForSpeech(text) {
        if (!text) return '';
        let clean = text.replace(/```json[\s\S]*?```/g, ''); // Strip JSON code blocks
        clean = clean.replace(/```[\s\S]*?```/g, '');       // Strip generic code blocks
        clean = clean.replace(/`([^`]+)`/g, '$1');          // Strip inline code backticks
        clean = clean.replace(/\*\*([^*]+)\*\*/g, '$1');    // Strip bold **
        clean = clean.replace(/\*([^*]+)\*/g, '$1');        // Strip italic *
        clean = clean.replace(/__([^_]+)__/g, '$1');        // Strip bold __
        clean = clean.replace(/_([^_]+)_/g, '$1');          // Strip italic _
        clean = clean.replace(/^#+\s+/gm, '');              // Strip headings #
        clean = clean.replace(/^[\s]*[-*+]\s+/gm, '. ');    // Convert list bullets to sentence breaks
        clean = clean.replace(/\|/g, ' ');                  // Strip table pipes
        clean = clean.replace(/\n+/g, '. ');                 // Replace newlines with sentence pauses
        clean = clean.replace(/\.\s*\./g, '.');             // Remove duplicate periods
        return clean.trim();
    }

    // Speech Synthesis TTS Voice Engine
    function speakText(text, isFinal = false) {
        if (!('speechSynthesis' in window)) return;
        
        const cleanText = sanitizeTextForSpeech(text);
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
            setVisualState('speaking');
        };

        utterance.onend = () => {
            if (!window.speechSynthesis.speaking) {
                statusDot.className = 'status-dot online';
                statusText.innerText = 'System Ready. Say "Parakeet"';
                setVisualState('idle');
            }
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
            setVisualState('idle');
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
                    setVisualState('listening');
                } else if (state === 'idle') {
                    micBtn.classList.remove('listening');
                    statusText.innerText = '⚡ Processing command...';
                    setVisualState('thinking');
                }
            },
            'parakeet'
        );
        await wakeWordListener.initMicrophone();
        if (wakeWordListener.analyser) {
            visualizer.setAnalyser(wakeWordListener.analyser);
        }
    }

    // 3. Handle Server Inbound WebSocket Messages
    function handleServerMessage(data) {
        if (data.type === 'transcription') {
            transcriptBox.innerHTML = `<strong>Heard:</strong> "${data.text}"`;
        } else if (data.type === 'status') {
            statusDot.className = 'status-dot thinking';
            setVisualState('thinking');
            const statusDisplay = data.message ? `⚡ ${data.message}` :
                                 (data.state === 'executing_tool' ? '⚡ Fetching database to construct result...' :
                                  data.state === 'analyzing' ? '🧠 Processing retrieved records...' :
                                  '🧠 Reading database essentials...');
            statusText.innerText = statusDisplay;
            if (data.speak) {
                speakText(data.speak, false);
            }
        } else if (data.type === 'final_result') {
            statusDot.className = 'status-dot online';
            statusText.innerText = 'System Ready.';
            
            // Render rich Markdown response
            responseCard.innerHTML = renderMarkdown(data.content || 'Analysis complete.');
            
            // Speak clean summary aloud naturally
            if (data.content) {
                speakText(data.content, true);
            } else {
                setVisualState('idle');
            }

            // Render visual payload (charts, tables, metric cards)
            if (data.payload && Object.keys(data.payload).length > 0) {
                chartRenderer.render(data.payload);
            }
        } else if (data.type === 'error') {
            statusDot.className = 'status-dot';
            statusText.innerText = 'Execution Error';
            setVisualState('idle');
            responseCard.innerHTML = renderMarkdown(`**Execution Error:** ${data.message}`);
            speakText(`Execution Error: ${data.message}`, true);
        }
    }

    // 4. UI Trigger Events
    micBtn.addEventListener('click', () => {
        if (wakeWordListener) {
            wakeWordListener.triggerListeningWindow(15000, 1500);
        }
    });

    // Warmup SpeechSynthesis voices
    if ('speechSynthesis' in window) {
        window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }

    // Initial render of welcome message markdown
    if (responseCard) {
        responseCard.innerHTML = renderMarkdown(responseCard.innerText || 'Welcome to Parakeet Enterprise Assistant.');
    }

    connect();
});
