document.addEventListener('DOMContentLoaded', () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/alfa`;
    
    let socket = null;
    let wakeWordListener = null;
    let chartRenderer = new UIChartRenderer('visualOutput');
    let visualizer = new GoogleCapsuleVisualizer('capsuleVisualizer');

    const statusDot = document.getElementById('statusDot');
    const transcriptDisplay = document.getElementById('transcriptDisplay');
    const pillStatusText = document.getElementById('pillStatusText');
    const streamOutputCard = document.getElementById('streamOutputCard');
    const streamTextContent = document.getElementById('streamTextContent');

    function setVisualState(state) {
        if (visualizer) visualizer.setState(state);
        if (statusDot) {
            statusDot.className = `status-dot ${state === 'listening' ? 'listening' : ''}`;
        }
    }

    // Markdown Renderer Helper for Final Card Output
    function renderMarkdown(text) {
        if (!text) return '';
        if (window.marked && typeof window.marked.parse === 'function') {
            return window.marked.parse(text);
        }
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/^\s*[-*+]\s+(.*$)/gim, '<li>$1</li>');
        return html;
    }

    // 1. WebSocket Persistent Connection
    function connect() {
        if (pillStatusText) pillStatusText.innerText = 'Connecting to Alfa...';
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            if (pillStatusText) pillStatusText.innerText = 'Auto search is on';
            initMic();
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        };

        socket.onclose = () => {
            if (pillStatusText) pillStatusText.innerText = 'Disconnected. Retrying...';
            setVisualState('idle');
            setTimeout(connect, 3000);
        };

        socket.onerror = (err) => {
            console.error('WebSocket Error:', err);
        };
    }

    // 2. Microphone & Wake-word Listener Setup
    async function initMic() {
        wakeWordListener = new WakeWordListener(
            (audioBuffer) => {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    // Reset Output Card for new query stream
                    streamTextContent.innerHTML = '';
                    streamOutputCard.classList.remove('hidden');
                    socket.send(audioBuffer);
                }
            },
            (state) => {
                if (state === 'listening') {
                    setVisualState('listening');
                    transcriptDisplay.innerText = 'Listening...';
                    if (pillStatusText) pillStatusText.innerText = 'Listening to command...';
                } else if (state === 'idle') {
                    setVisualState('thinking');
                    if (pillStatusText) pillStatusText.innerText = 'Thinking...';
                }
            },
            'hey alfa'
        );
        await wakeWordListener.initMicrophone();
        if (wakeWordListener.analyser) {
            visualizer.setAnalyser(wakeWordListener.analyser);
        }
    }

    // 3. Inbound Server Message Handler (First-Token Streaming)
    function handleServerMessage(data) {
        if (data.type === 'transcription') {
            transcriptDisplay.innerText = data.text || 'Listening...';
        } else if (data.type === 'status') {
            setVisualState('thinking');
            if (pillStatusText) pillStatusText.innerText = data.message || 'Processing...';
        } else if (data.type === 'token') {
            // First-Token Stream Handler: append each token with a smooth fade-in animation
            if (streamOutputCard.classList.contains('hidden')) {
                streamOutputCard.classList.remove('hidden');
            }
            
            const tokenSpan = document.createElement('span');
            tokenSpan.className = 'token-span';
            tokenSpan.innerText = data.content;
            streamTextContent.appendChild(tokenSpan);

            // Auto-scroll stream container to latest token
            streamOutputCard.scrollTop = streamOutputCard.scrollHeight;
        } else if (data.type === 'final_result') {
            setVisualState('idle');
            if (pillStatusText) pillStatusText.innerText = 'Auto search is on';
            
            // Format full final response text with rich Markdown
            if (data.content) {
                streamTextContent.innerHTML = renderMarkdown(data.content);
            }

            // Render visual payload (Chart.js charts, data tables, metric cards)
            if (data.payload && Object.keys(data.payload).length > 0) {
                chartRenderer.render(data.payload);
            }
        } else if (data.type === 'error') {
            setVisualState('idle');
            if (pillStatusText) pillStatusText.innerText = 'Execution Error';
            streamOutputCard.classList.remove('hidden');
            streamTextContent.innerHTML = `<span style="color:#ea4335;">Error: ${data.message}</span>`;
        }
    }

    // Tap Visualizer canvas or transcript to manually trigger voice input
    const canvas = document.getElementById('capsuleVisualizer');
    if (canvas) {
        canvas.addEventListener('click', () => {
            if (wakeWordListener) {
                wakeWordListener.triggerListeningWindow(15000, 1500);
            }
        });
    }

    connect();
});
