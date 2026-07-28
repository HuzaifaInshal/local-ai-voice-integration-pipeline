document.addEventListener('DOMContentLoaded', () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/alfa`;
    
    let socket = null;
    let wakeWordListener = null;
    let mainVisualizer = new GoogleCapsuleVisualizer('capsuleVisualizer');
    let bottomVisualizer = new GoogleCapsuleVisualizer('capsuleVisualizerBottom');
    let chartRenderer = null;

    const screenInitial = document.getElementById('screenInitial');
    const screenResults = document.getElementById('screenResults');
    const transcriptDisplay = document.getElementById('transcriptDisplay');
    const conversationFeed = document.getElementById('conversationFeed');
    const bottomTranscriptText = document.getElementById('bottomTranscriptText');

    let currentTurnCard = null;
    let currentResponseBox = null;
    let currentVisualContainer = null;
    let isScreenTwo = false;

    function setVisualState(state) {
        if (mainVisualizer) mainVisualizer.setState(state);
        if (bottomVisualizer) bottomVisualizer.setState(state);
    }

    // Markdown Renderer Helper
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

    // Transition from Screen 1 to Screen 2
    function switchToScreenTwo() {
        if (isScreenTwo) return;
        isScreenTwo = true;
        if (screenInitial) screenInitial.classList.add('hidden');
        if (screenResults) screenResults.classList.remove('hidden');
    }

    // Create a new Turn Card (User Query + AI Response Container) in Screen 2
    function createNewTurnCard(queryText) {
        switchToScreenTwo();

        const card = document.createElement('div');
        card.className = 'turn-card';

        const userBubble = document.createElement('div');
        userBubble.className = 'user-query-bubble';
        userBubble.innerText = queryText;
        card.appendChild(userBubble);

        const aiBox = document.createElement('div');
        aiBox.className = 'ai-response-box';
        card.appendChild(aiBox);

        const payloadDiv = document.createElement('div');
        payloadDiv.className = 'visual-payload-container';
        card.appendChild(payloadDiv);

        conversationFeed.appendChild(card);
        conversationFeed.scrollTop = conversationFeed.scrollHeight;

        currentTurnCard = card;
        currentResponseBox = aiBox;
        currentVisualContainer = payloadDiv;
        chartRenderer = new UIChartRenderer(payloadDiv);
    }

    // 1. Establish persistent WebSocket connection
    function connect() {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            initMic();
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleServerMessage(data);
        };

        socket.onclose = () => {
            setVisualState('idle');
            setTimeout(connect, 3000);
        };

        socket.onerror = (err) => {
            console.error('WebSocket Error:', err);
        };
    }

    // 2. Initialize Microphone & Web Speech Listener
    async function initMic() {
        wakeWordListener = new WakeWordListener(
            // On Command Text Ready (Submit to backend)
            (commandText) => {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    createNewTurnCard(commandText);
                    setVisualState('thinking');
                    if (bottomTranscriptText) bottomTranscriptText.innerText = 'Thinking...';
                    socket.send(JSON.stringify({ text: commandText }));
                }
            },
            // On Status Change
            (state) => {
                setVisualState(state);
                if (state === 'listening') {
                    if (!isScreenTwo && transcriptDisplay) {
                        transcriptDisplay.innerText = 'Listening...';
                    }
                    if (bottomTranscriptText) {
                        bottomTranscriptText.innerText = 'Listening...';
                    }
                } else if (state === 'idle') {
                    if (!isScreenTwo && transcriptDisplay) {
                        transcriptDisplay.innerText = 'Say "Hey Alfa" to start';
                    }
                }
            },
            // On Instant Word-by-Word Transcript (0ms delay)
            (instantText) => {
                if (!isScreenTwo && transcriptDisplay) {
                    transcriptDisplay.innerText = instantText || 'Listening...';
                }
                if (bottomTranscriptText) {
                    bottomTranscriptText.innerText = instantText || 'Listening...';
                }
            }
        );

        await wakeWordListener.initMicrophone();
        if (wakeWordListener.analyser) {
            mainVisualizer.setAnalyser(wakeWordListener.analyser);
            bottomVisualizer.setAnalyser(wakeWordListener.analyser);
        }
    }

    // 3. Handle Inbound Server WebSocket Messages
    function handleServerMessage(data) {
        if (data.type === 'status') {
            setVisualState('thinking');
            if (bottomTranscriptText) {
                bottomTranscriptText.innerText = data.message || 'Processing...';
            }
        } else if (data.type === 'token') {
            // First-Token Real-Time Stream: append tokens live into active response box
            if (!currentResponseBox) return;

            const tokenSpan = document.createElement('span');
            tokenSpan.className = 'token-span';
            tokenSpan.innerText = data.content;
            currentResponseBox.appendChild(tokenSpan);

            conversationFeed.scrollTop = conversationFeed.scrollHeight;
        } else if (data.type === 'final_result') {
            setVisualState('idle');
            if (bottomTranscriptText) {
                bottomTranscriptText.innerText = 'Listening for "Hey Alfa"...';
            }

            // Render Markdown formatting for completed response
            if (currentResponseBox && data.content) {
                currentResponseBox.innerHTML = renderMarkdown(data.content);
            }

            // Render visual payload (Chart.js charts, data tables, metric cards)
            if (chartRenderer && data.payload && Object.keys(data.payload).length > 0) {
                chartRenderer.render(data.payload);
            }

            conversationFeed.scrollTop = conversationFeed.scrollHeight;
        } else if (data.type === 'error') {
            setVisualState('idle');
            if (bottomTranscriptText) bottomTranscriptText.innerText = 'Error occurred';
            if (currentResponseBox) {
                currentResponseBox.innerHTML = `<span style="color:#ea4335;">Error: ${data.message}</span>`;
            }
        }
    }

    // Manual tap trigger on canvas or visualizer wrappers
    const wrappers = document.querySelectorAll('.visualizer-wrapper, .bottom-visualizer-wrapper');
    wrappers.forEach(w => {
        w.addEventListener('click', () => {
            if (wakeWordListener) {
                wakeWordListener.triggerManualListening();
            }
        });
    });

    connect();
});
