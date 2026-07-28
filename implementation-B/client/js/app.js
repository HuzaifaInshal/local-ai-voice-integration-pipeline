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
        // Strip raw JSON payload code blocks, SQL code blocks, and internal SQL statements from UI text
        let clean = text.replace(/```sql[\s\S]*?```/gi, '').trim();
        clean = clean.replace(/```json[\s\S]*?```/gi, '').trim();
        clean = clean.replace(/```[\s\S]*?```/g, '').trim();
        clean = clean.replace(/\{[\s\S]*?"display_type"[\s\S]*?\}/gi, '').trim();
        clean = clean.replace(/\bSELECT\s+[\s\S]+?(?:;|$)/gi, '').trim();
        clean = clean.replace(/To find[\s\S]*?SQL query:/gi, '').trim();
        clean = clean.replace(/Let's run this query[\s\S]*?results\./gi, '').trim();


        if (window.marked && typeof window.marked.parse === 'function') {
            return window.marked.parse(clean);
        }
        let html = clean
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
            if (currentResponseBox) {
                let slot = currentResponseBox.querySelector('.inline-payload-slot');
                if (!slot) {
                    slot = document.createElement('div');
                    slot.className = 'inline-payload-slot';
                    slot.style.cssText = 'margin: 0.75rem 0; width: 100%; transition: all 0.3s ease;';
                    slot.innerHTML = `
                        <div class="inline-fetching-badge" style="display: inline-flex; align-items: center; gap: 0.6rem; padding: 0.55rem 1rem; background: rgba(26, 115, 232, 0.08); border: 1px solid rgba(26, 115, 232, 0.25); border-radius: 20px; color: #1a73e8; font-size: 0.9rem; font-weight: 500; animation: slideUpTurn 0.25s ease;">
                            <span style="display: inline-block; width: 12px; height: 12px; border: 2px solid #1a73e8; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite;"></span>
                            <span>${data.message || 'Fetching data...'}</span>
                        </div>
                    `;
                    currentResponseBox.appendChild(slot);
                }
            }
        } else if (data.type === 'token') {
            if (!currentResponseBox) return;

            const tokenSpan = document.createElement('span');
            tokenSpan.className = 'token-span';
            tokenSpan.innerText = data.content;

            const slot = currentResponseBox.querySelector('.inline-payload-slot');
            if (slot) {
                currentResponseBox.insertBefore(tokenSpan, slot);
            } else {
                currentResponseBox.appendChild(tokenSpan);
            }

            conversationFeed.scrollTop = conversationFeed.scrollHeight;
        } else if (data.type === 'final_result') {
            setVisualState('idle');
            if (bottomTranscriptText) {
                bottomTranscriptText.innerText = 'Listening for "Hey Alfa"...';
            }

            if (currentResponseBox) {
                let slot = currentResponseBox.querySelector('.inline-payload-slot');

                // Render markdown text while preserving inline slot position
                if (slot) {
                    const tempPlaceholder = document.createElement('div');
                    tempPlaceholder.id = '__INLINE_SLOT_HOLDER__';
                    slot.parentNode.replaceChild(tempPlaceholder, slot);

                    const textContent = currentResponseBox.innerText.replace('__INLINE_SLOT_HOLDER__', '').trim();
                    currentResponseBox.innerHTML = renderMarkdown(textContent);

                    const reinsertTarget = currentResponseBox.querySelector('#__INLINE_SLOT_HOLDER__');
                    if (reinsertTarget) {
                        reinsertTarget.parentNode.replaceChild(slot, reinsertTarget);
                    } else {
                        currentResponseBox.appendChild(slot);
                    }
                } else {
                    currentResponseBox.innerHTML = renderMarkdown(currentResponseBox.innerText);
                }

                // Smoothly render table or empty state payload directly inside the inline slot
                if (data.payload && Object.keys(data.payload).length > 0) {
                    if (!slot) {
                        slot = document.createElement('div');
                        slot.className = 'inline-payload-slot';
                        slot.style.cssText = 'margin: 0.75rem 0; width: 100%;';
                        currentResponseBox.appendChild(slot);
                    }
                    const inlineRenderer = new UIChartRenderer(slot);
                    inlineRenderer.render(data.payload);
                } else if (slot) {
                    // Remove loader slot if no payload was generated (e.g. simple chat)
                    slot.remove();
                }
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

    // Text Input Submission Handler
    function submitUserQuery(text) {
        if (!text || !text.trim()) return;
        const cleanQuery = text.trim();
        if (socket && socket.readyState === WebSocket.OPEN) {
            createNewTurnCard(cleanQuery);
            setVisualState('thinking');
            socket.send(JSON.stringify({ text: cleanQuery }));
        }
    }

    const queryInput = document.getElementById('queryInput');
    const querySubmitBtn = document.getElementById('querySubmitBtn');
    const queryInputBottom = document.getElementById('queryInputBottom');
    const querySubmitBtnBottom = document.getElementById('querySubmitBtnBottom');

    if (querySubmitBtn && queryInput) {
        querySubmitBtn.addEventListener('click', () => {
            submitUserQuery(queryInput.value);
            queryInput.value = '';
        });
        queryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                submitUserQuery(queryInput.value);
                queryInput.value = '';
            }
        });
    }

    if (querySubmitBtnBottom && queryInputBottom) {
        querySubmitBtnBottom.addEventListener('click', () => {
            submitUserQuery(queryInputBottom.value);
            queryInputBottom.value = '';
        });
        queryInputBottom.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                submitUserQuery(queryInputBottom.value);
                queryInputBottom.value = '';
            }
        });
    }

    connect();
});

