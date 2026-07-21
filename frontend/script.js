// --- Naira OS Day 1 Frontend Controller ---

// State Management
const appState = {
    currentScreen: 'screen-splash',
    operatorName: 'Operator',
    apiKey: '',
    isMicActive: false,
    activePanel: null, // 'chat', 'monitor', or null
    systemMonitorInterval: null
};

// Ensure DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// App Initialization
function initApp() {
    setupWindowControls();
    setupNavigation();
    setupForms();
    setupSidebar();
    setupSettingsModal();
    setupChat();
    
    // Start splash screen loading simulation
    simulateSplashLoading();
}

// 1. Frameless Window Controls
function setupWindowControls() {
    const btnMinimize = document.getElementById('btn-minimize');
    const btnClose = document.getElementById('btn-close');
    
    if (btnMinimize) {
        btnMinimize.addEventListener('click', () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.minimize_window();
            } else {
                console.log('[Mock Webview] Minimizing window');
            }
        });
    }
    
    if (btnClose) {
        btnClose.addEventListener('click', () => {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.close_window();
            } else {
                console.log('[Mock Webview] Closing window');
            }
        });
    }
}

// 2. SPA Navigation System
function navigateTo(screenId) {
    const targetScreen = document.getElementById(screenId);
    if (!targetScreen) return;
    
    // Deactivate current screen
    const currentScreenEl = document.getElementById(appState.currentScreen);
    if (currentScreenEl) {
        currentScreenEl.classList.remove('active');
    }
    
    // Activate target screen
    targetScreen.classList.add('active');
    appState.currentScreen = screenId;
}

// 3. Splash Screen Sim
function simulateSplashLoading() {
    const loaderBar = document.getElementById('splash-loader-bar');
    if (!loaderBar) return;
    
    let progress = 0;
    const duration = 2800; // slightly under 3 seconds
    const intervalTime = 50;
    const step = (100 / (duration / intervalTime));
    
    const timer = setInterval(() => {
        progress += step;
        if (progress >= 100) {
            progress = 100;
            clearInterval(timer);
            // Delay slightly at 100% for smooth transition
            setTimeout(async () => {
                // Smart bypass: check if backend already has API key
                let hasKey = false;
                try {
                    const res = await fetch('/api/check_key');
                    const data = await res.json();
                    hasKey = data.has_key;
                } catch (e) {
                    // If check fails (e.g. server not yet ready), default to showing dashboard
                    hasKey = true;
                }

                if (hasKey) {
                    navigateTo('screen-dashboard');
                } else {
                    navigateTo('screen-api');
                }
            }, 200);
        }
        loaderBar.style.width = `${progress}%`;
    }, intervalTime);
}

// 4. API Form & Backend Bridge Logic
function setupForms() {
    const btnCheckApi = document.getElementById('btn-check-api');
    const btnSubmitApi = document.getElementById('btn-submit-api');
    const apiKeyInput = document.getElementById('api-key-input');
    const apiSuccessBox = document.getElementById('api-success-box');
    const apiErrorBox = document.getElementById('api-error-box');
    
    // User info screen elements
    const btnSaveUser = document.getElementById('btn-save-user');
    const usernameInput = document.getElementById('username-input');

    // API check click
    btnCheckApi.addEventListener('click', async () => {
        const key = apiKeyInput.value.trim();
        if (!key) {
            showApiStatus('error');
            return;
        }
        
        btnCheckApi.disabled = true;
        btnCheckApi.querySelector('.btn-text').textContent = 'Validating...';
        
        // Hide existing boxes
        apiSuccessBox.classList.add('hidden');
        apiErrorBox.classList.add('hidden');
        btnSubmitApi.classList.add('hidden');
        
        let isValid = false;
        
        try {
            // Save key to backend
            await fetch('/api/save_key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: key })
            });
            
            if (window.pywebview && window.pywebview.api) {
                isValid = await window.pywebview.api.validate_api_key(key);
            } else {
                isValid = key.length > 5;
            }
        } catch (error) {
            console.error('[JS] Bridge validation error: ', error);
            isValid = key.length > 5;
        }
        
        btnCheckApi.disabled = false;
        btnCheckApi.querySelector('.btn-text').textContent = 'Check Validity';
        
        if (isValid) {
            appState.apiKey = key;
            showApiStatus('success');
            btnSubmitApi.classList.remove('hidden');
        } else {
            showApiStatus('error');
            btnSubmitApi.classList.add('hidden');
        }
    });

    // API Submit click
    btnSubmitApi.addEventListener('click', () => {
        navigateTo('screen-user');
    });

    // Save user info click
    btnSaveUser.addEventListener('click', () => {
        const name = usernameInput.value.trim();
        if (name) {
            appState.operatorName = name;
        }
        
        // Update user display details in dashboard
        updateOperatorNameUI();
        
        // Navigate to dashboard
        navigateTo('screen-dashboard');
    });
}

function showApiStatus(status) {
    const apiSuccessBox = document.getElementById('api-success-box');
    const apiErrorBox = document.getElementById('api-error-box');
    
    if (status === 'success') {
        apiSuccessBox.classList.remove('hidden');
        apiErrorBox.classList.add('hidden');
    } else {
        apiSuccessBox.classList.add('hidden');
        apiErrorBox.classList.remove('hidden');
    }
}

function updateOperatorNameUI() {
    // Replace placeholder texts in dashboard chat and settings
    const elements = document.querySelectorAll('.operator-name-display');
    elements.forEach(el => {
        el.textContent = appState.operatorName;
    });
    
    const settingsNameInput = document.getElementById('settings-username');
    if (settingsNameInput) {
        settingsNameInput.value = appState.operatorName;
    }
}

// 5. Sidebar Controls & Slide Panels
function setupSidebar() {
    const navHome = document.getElementById('nav-home');
    const navChat = document.getElementById('nav-chat');
    const navSettings = document.getElementById('nav-settings');
    
    const panelChat = document.getElementById('panel-chat');
    const settingsOverlay = document.getElementById('settings-overlay');
    
    const closeChat = document.getElementById('close-chat');

    // Home Button Closes Everything
    navHome.addEventListener('click', () => {
        resetActiveNav();
        navHome.classList.add('active');
        closeAllPanels();
    });

    // Chat Sidebar Button
    navChat.addEventListener('click', () => {
        if (appState.activePanel === 'chat') {
            closeAllPanels();
            resetActiveNav();
            navHome.classList.add('active');
        } else {
            closeAllPanels();
            resetActiveNav();
            navChat.classList.add('active');
            panelChat.classList.add('active');
            appState.activePanel = 'chat';
        }
    });

    // Settings Sidebar Button
    navSettings.addEventListener('click', () => {
        settingsOverlay.classList.add('active');
    });

    // Close Panel Buttons (X)
    closeChat.addEventListener('click', () => {
        panelChat.classList.remove('active');
        appState.activePanel = null;
        resetActiveNav();
        navHome.classList.add('active');
    });
}

function resetActiveNav() {
    const buttons = document.querySelectorAll('.sidebar-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
}

function closeAllPanels() {
    const panelChat = document.getElementById('panel-chat');
    panelChat.classList.remove('active');
    appState.activePanel = null;
}

// 6. Settings Modal Navigation & Tab Switcher
function setupSettingsModal() {
    const settingsOverlay = document.getElementById('settings-overlay');
    const closeSettings = document.getElementById('close-settings');
    const navButtons = document.querySelectorAll('.settings-nav-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    // Save Settings Config
    const btnSaveSettingsUser = document.getElementById('btn-save-settings-user');
    const settingsUsername = document.getElementById('settings-username');
    const settingsApiKey = document.getElementById('settings-api-key');

    // Close modal click
    closeSettings.addEventListener('click', () => {
        settingsOverlay.classList.remove('active');
    });

    // Close overlay if clicked outside the card
    settingsOverlay.addEventListener('click', (e) => {
        if (e.target === settingsOverlay) {
            settingsOverlay.classList.remove('active');
        }
    });

    // Tab buttons switching
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const targetTab = btn.getAttribute('data-tab');
            tabPanes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === targetTab) {
                    pane.classList.add('active');
                }
            });
        });
    });

    // Save inside modal
    btnSaveSettingsUser.addEventListener('click', () => {
        const newName = settingsUsername.value.trim();
        if (newName) {
            appState.operatorName = newName;
            updateOperatorNameUI();
        }
        
        const newKey = settingsApiKey.value.trim();
        if (newKey && newKey.startsWith('opencode-zen-')) {
            appState.apiKey = newKey;
            document.getElementById('api-key-input').value = newKey;
        }
        
        settingsOverlay.classList.remove('active');
    });
}

// 7. Avatar & Microphone Logic
function setupNavigation() {
    const btnMic = document.getElementById('btn-mic');

    // Resolve cross-browser SpeechRecognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let _recognitionActive = false;
    let silenceTimer = null;
    let accumulatedTranscript = '';

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'hi-IN'; // Default to Hindi/Hinglish multi-lingual mode

        const sendAccumulatedMessage = () => {
            const finalSpeech = accumulatedTranscript.trim();
            accumulatedTranscript = '';
            if (silenceTimer) {
                clearTimeout(silenceTimer);
                silenceTimer = null;
            }

            if (!finalSpeech) return;

            // Mirror the exact same send flow used by the chat text input
            const messagesContainer = document.getElementById('chat-messages-container');

            // Show user bubble
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message user';
            messageDiv.innerHTML = `<div class="message-bubble">${finalSpeech}</div>`;
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            // Avatar → thinking
            setAvatarState('thinking');

            // Send over WebSocket
            if (window._nairaWS && window._nairaWS.readyState === WebSocket.OPEN) {
                window._nairaWS.send(finalSpeech);
            } else {
                console.warn('[Mic] WebSocket not open — cannot send transcript.');
                setAvatarState('idle');
            }
        };

        recognition.onstart = () => {
            _recognitionActive = true;
            appState.isMicActive = true;
            btnMic.classList.add('active');
            setAvatarState('listening');
            accumulatedTranscript = '';
        };

        recognition.onresult = (event) => {
            let currentSpeech = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                currentSpeech += event.results[i][0].transcript;
            }
            if (currentSpeech.trim()) {
                accumulatedTranscript = currentSpeech.trim();
            }

            // Reset silence debounce timer (1.8 seconds of quiet required before sending)
            if (silenceTimer) clearTimeout(silenceTimer);
            silenceTimer = setTimeout(() => {
                sendAccumulatedMessage();
                if (_recognitionActive) {
                    try { recognition.stop(); } catch(e) {}
                }
            }, 1800);
        };

        recognition.onerror = (event) => {
            console.error('[SpeechRecognition] Error:', event.error);
            if (event.error === 'no-speech' || event.error === 'aborted') {
                return;
            }
            _recognitionActive = false;
            appState.isMicActive = false;
            btnMic.classList.remove('active');
            setAvatarState('idle');
            if (silenceTimer) clearTimeout(silenceTimer);
        };

        recognition.onend = () => {
            _recognitionActive = false;
            if (accumulatedTranscript.trim()) {
                sendAccumulatedMessage();
            }
            if (appState.isMicActive) {
                appState.isMicActive = false;
                btnMic.classList.remove('active');
                if (document.getElementById('mic-status-lbl') &&
                    document.getElementById('mic-status-lbl').textContent === 'NAIRA LISTENING') {
                    setAvatarState('idle');
                }
            }
        };
    } else {
        console.warn('[Mic] Web Speech API is not supported in this browser.');
    }

    btnMic.addEventListener('click', () => {
        if (!recognition) {
            // Fallback toggle for browsers without Speech API
            appState.isMicActive = !appState.isMicActive;
            if (appState.isMicActive) {
                btnMic.classList.add('active');
                setAvatarState('listening');
            } else {
                btnMic.classList.remove('active');
                setAvatarState('idle');
            }
            return;
        }

        if (_recognitionActive) {
            if (silenceTimer) clearTimeout(silenceTimer);
            if (accumulatedTranscript.trim()) {
                if (window._nairaWS && window._nairaWS.readyState === WebSocket.OPEN) {
                    const finalSpeech = accumulatedTranscript.trim();
                    accumulatedTranscript = '';
                    const messagesContainer = document.getElementById('chat-messages-container');
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message user';
                    messageDiv.innerHTML = `<div class="message-bubble">${finalSpeech}</div>`;
                    messagesContainer.appendChild(messageDiv);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    setAvatarState('thinking');
                    window._nairaWS.send(finalSpeech);
                }
            }
            recognition.stop();
        } else {
            try {
                accumulatedTranscript = '';
                recognition.start();
            } catch (e) {
                console.error('[Mic] Failed to start recognition:', e);
            }
        }
    });
}

/**
 * Updates the Avatar video source and changes the glowing fallback orb styling.
 * Supports: 'idle', 'listening', 'thinking', 'talking', 'laughing'
 */
function setAvatarState(state) {
    const video = document.getElementById('avatar-video');
    const orb = document.getElementById('avatar-orb');
    const label = document.getElementById('mic-status-lbl');
    
    let videoFile = 'idle.mp4';
    let statusText = 'NAIRA IDLE';
    let labelClass = '';
    
    switch(state) {
        case 'listening':
            videoFile = 'listening.mp4';
            statusText = 'NAIRA LISTENING';
            labelClass = 'active';
            break;
        case 'thinking':
            videoFile = 'thinking.mp4';
            statusText = 'NAIRA THINKING';
            break;
        case 'talking':
            videoFile = 'talking.mp4';
            statusText = 'NAIRA TALKING';
            break;
        case 'laughing':
            videoFile = 'laughing.mp4';
            statusText = 'NAIRA LAUGHING';
            break;
        case 'idle':
        default:
            videoFile = 'idle.mp4';
            statusText = 'NAIRA IDLE';
            break;
    }
    
    // Update label text and activation glow class
    if (label) {
        label.textContent = statusText;
        if (labelClass) {
            label.classList.add('active');
        } else {
            label.classList.remove('active');
        }
    }
    
    // Update video source element cleanly
    if (video) {
        const targetSrc = `assets/${videoFile}`;
        const currentSrc = video.getAttribute('src') || '';
        if (currentSrc !== targetSrc) {
            video.setAttribute('src', targetSrc);
            video.load();
            video.play().catch(err => {
                console.warn(`[Avatar] Video asset '${targetSrc}' loading fallback:`, err);
            });
        } else if (video.paused) {
            video.play().catch(() => {});
        }
    }

    // Animate the fallback CSS orb depending on the state
    if (orb) {
        // Reset manual modifications
        orb.className = 'avatar-fallback-orb';
        orb.removeAttribute('style');

        switch(state) {
            case 'listening':
                orb.style.background = 'radial-gradient(circle, #00f3ff 0%, rgba(0, 243, 255, 0.2) 65%, transparent 100%)';
                orb.style.boxShadow = 'none';
                orb.style.animation = 'pulseOrbState 0.9s ease-in-out infinite alternate';
                break;
            case 'thinking':
                orb.style.background = 'radial-gradient(circle, #00aaff 0%, rgba(0, 170, 255, 0.2) 65%, transparent 100%)';
                orb.style.boxShadow = 'none';
                orb.style.animation = 'pulseOrbState 1.8s ease-in-out infinite alternate';
                break;
            case 'talking':
                orb.style.background = 'radial-gradient(circle, #00f3ff 0%, rgba(0, 243, 255, 0.2) 65%, transparent 100%)';
                orb.style.boxShadow = 'none';
                orb.style.animation = 'pulseOrbState 0.5s ease-in-out infinite alternate';
                break;
            case 'laughing':
                orb.style.background = 'radial-gradient(circle, #39ff14 0%, rgba(57, 255, 20, 0.2) 65%, transparent 100%)';
                orb.style.boxShadow = 'none';
                orb.style.animation = 'pulseOrbState 1.1s ease-in-out infinite alternate';
                break;
            case 'idle':
            default:
                // Base CSS rules apply
                break;
        }
    }
}

// 8. Chat Functionality
function setupChat() {
    const chatInput = document.getElementById('chat-input');
    const btnSendMessage = document.getElementById('btn-send-message');
    const messagesContainer = document.getElementById('chat-messages-container');

    // Initialize WebSocket connection
    const ws = new WebSocket('ws://' + window.location.host + '/ws');
    window._nairaWS = ws; // expose for mic SpeechRecognition handler
    let currentSystemBubble = null;
    let talkTimeout = null;

    ws.onclose = (event) => {
        console.log('[WebSocket] Connection closed:', event.code, event.reason);
    };

    ws.onerror = (error) => {
        console.error('[WebSocket] Error observed:', error);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'wake_word_activated') {
                setAvatarState('listening');
                appState.isMicActive = true;
                const btnMic = document.getElementById('btn-mic');
                if (btnMic) btnMic.classList.add('active');
            } else if (data.type === 'text') {
                let chunk = data.content;
                if (!chunk || !chunk.trim()) {
                    chunk = "[Executing Command...]";
                }
                if (!currentSystemBubble) {
                    setAvatarState('talking');
                    currentSystemBubble = appendMessage('system', chunk);
                } else {
                    currentSystemBubble.textContent += chunk;
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                if (talkTimeout) clearTimeout(talkTimeout);
                talkTimeout = setTimeout(() => {
                    if (appState.isMicActive) {
                        setAvatarState('listening');
                    } else {
                        setAvatarState('idle');
                    }
                }, 3000);
            } else if (data.type === 'audio') {
                const audioData = data.content;
                const audioFormat = data.format || 'mp3';
                const audioUrl = `data:audio/${audioFormat};base64,${audioData}`;
                const audio = new Audio(audioUrl);

                audio.addEventListener('play', () => {
                    setAvatarState('talking');
                });

                audio.addEventListener('ended', () => {
                    if (appState.isMicActive) {
                        setAvatarState('listening');
                    } else {
                        setAvatarState('idle');
                    }
                });

                audio.addEventListener('error', () => {
                    setAvatarState('idle');
                });

                audio.play().then(() => {
                    setAvatarState('talking');
                }).catch(err => {
                    console.error("Audio play error:", err);
                    setAvatarState('idle');
                });
            }
        } catch (err) {
            console.error("WS message error:", err);
        }
    };

    function handleSend() {
        const messageText = chatInput.value.trim();
        if (!messageText) return;

        // Show user's message in the chat UI
        appendMessage('user', messageText);
        chatInput.value = '';

        // Transition avatar to thinking
        setAvatarState('thinking');
        currentSystemBubble = null;

        // Send via WebSocket
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(messageText);
        } else {
            console.warn("WebSocket is not open. Showing offline error...");
            appendMessage('system', "Error: WebSocket connection is offline.");
            setAvatarState('idle');
        }
    }

    function appendMessage(sender, text) {
        if (!text || !text.trim()) return null;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        let messageText = text;
        if (sender === 'system') {
            messageText = text.replace('{user}', appState.operatorName);
        }

        messageDiv.innerHTML = `
            <div class="message-bubble">
                ${messageText}
            </div>
        `;
        messagesContainer.appendChild(messageDiv);

        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return messageDiv.querySelector('.message-bubble');
    }

    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSend();
        }
    });

    btnSendMessage.addEventListener('click', handleSend);
}


