class GoogleCapsuleVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        
        this.numBars = 4;
        this.barHeights = new Float32Array([0.25, 0.25, 0.25, 0.25]);
        this.targetHeights = new Float32Array([0.25, 0.25, 0.25, 0.25]);
        this.state = 'idle'; // 'idle', 'listening', 'thinking'
        this.analyser = null;
        this.phase = 0;

        this.colors = [
            { top: '#4285f4', bottom: '#8ab4f8' }, // Blue
            { top: '#34a853', bottom: '#81c995' }, // Green
            { top: '#fbbc05', bottom: '#fde293' }, // Yellow
            { top: '#ea4335', bottom: '#f28b82' }  // Red
        ];

        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.startAnimation();
    }

    setAnalyser(analyser) {
        this.analyser = analyser;
    }

    setState(state) {
        this.state = state;
    }

    resize() {
        if (!this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        this.width = rect.width || 240;
        this.height = rect.height || 70;
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = this.width * dpr;
        this.canvas.height = this.height * dpr;
        this.ctx.scale(dpr, dpr);
    }

    startAnimation() {
        const render = () => {
            this.update();
            this.draw();
            requestAnimationFrame(render);
        };
        render();
    }

    update() {
        if (this.state === 'listening') {
            this.phase += 0.12;
            if (this.analyser) {
                const bufferLength = this.analyser.frequencyBinCount;
                const dataArray = new Uint8Array(bufferLength);
                this.analyser.getByteFrequencyData(dataArray);

                for (let i = 0; i < 4; i++) {
                    const index = Math.floor((i / 4) * bufferLength);
                    const val = dataArray[index] / 255.0;
                    this.targetHeights[i] = Math.max(0.2, val * 0.95);
                }
            } else {
                for (let i = 0; i < 4; i++) {
                    const wave = Math.sin(this.phase * 2.0 + i * 0.7);
                    this.targetHeights[i] = (wave + 1) / 2 * 0.65 + 0.25;
                }
            }
        } else if (this.state === 'thinking') {
            this.phase += 0.08;
            for (let i = 0; i < 4; i++) {
                const wave = Math.sin(this.phase * 1.5 + i * 0.5);
                this.targetHeights[i] = (wave + 1) / 2 * 0.4 + 0.2;
            }
        } else {
            // IDLE / DORMANT STATE: Static small capsules, NO animation!
            for (let i = 0; i < 4; i++) {
                this.targetHeights[i] = 0.25;
            }
        }

        for (let i = 0; i < 4; i++) {
            this.barHeights[i] += (this.targetHeights[i] - this.barHeights[i]) * 0.2;
        }
    }

    draw() {
        const { ctx, width, height, barHeights, colors, state } = this;
        ctx.clearRect(0, 0, width, height);

        const barWidth = 16;
        const gap = 12;
        const totalWidth = 4 * barWidth + 3 * gap;
        const startX = (width - totalWidth) / 2;

        for (let i = 0; i < 4; i++) {
            const h = Math.max(16, barHeights[i] * (height - 10));
            const x = startX + i * (barWidth + gap);
            const y = (height - h) / 2;

            const colorConfig = colors[i];
            const gradient = ctx.createLinearGradient(x, y, x, y + h);

            if (state === 'idle') {
                // Static dim capsules when waiting for wake-word
                gradient.addColorStop(0, '#bdc1c6');
                gradient.addColorStop(1, '#dadce0');
                ctx.shadowColor = 'transparent';
                ctx.shadowBlur = 0;
            } else {
                // Vibrant Google colored gradient when listening / active
                gradient.addColorStop(0, colorConfig.top);
                gradient.addColorStop(1, colorConfig.bottom);
                ctx.shadowColor = colorConfig.top;
                ctx.shadowBlur = 10;
            }

            ctx.fillStyle = gradient;
            const radius = barWidth / 2;
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(x, y, barWidth, h, radius);
            } else {
                ctx.rect(x, y, barWidth, h);
            }
            ctx.fill();
        }
    }
}

window.GoogleCapsuleVisualizer = GoogleCapsuleVisualizer;
