class GoogleCapsuleVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        
        this.numBars = 4;
        this.barHeights = new Float32Array([0.4, 0.7, 0.5, 0.6]);
        this.targetHeights = new Float32Array([0.4, 0.7, 0.5, 0.6]);
        this.state = 'idle'; // 'idle', 'listening', 'thinking'
        this.analyser = null;
        this.phase = 0;

        // Color palette for Google Assistant 4 bars
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
        this.height = rect.height || 80;
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
        this.phase += 0.09;

        if (this.state === 'listening' && this.analyser) {
            const bufferLength = this.analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            this.analyser.getByteFrequencyData(dataArray);

            for (let i = 0; i < 4; i++) {
                const index = Math.floor((i / 4) * bufferLength);
                const val = dataArray[index] / 255.0;
                const target = Math.max(0.2, val * 0.95);
                this.targetHeights[i] = target;
            }
        } else if (this.state === 'thinking') {
            for (let i = 0; i < 4; i++) {
                const wave = Math.sin(this.phase * 2.2 + i * 0.8);
                this.targetHeights[i] = (wave + 1) / 2 * 0.65 + 0.2;
            }
        } else {
            // Idle state: soft subtle wave pulse
            for (let i = 0; i < 4; i++) {
                const wave = Math.sin(this.phase * 0.8 + i * 0.5);
                this.targetHeights[i] = (wave + 1) / 2 * 0.25 + 0.35;
            }
        }

        // Smooth Lerp for fluid capsule movement
        for (let i = 0; i < 4; i++) {
            this.barHeights[i] += (this.targetHeights[i] - this.barHeights[i]) * 0.18;
        }
    }

    draw() {
        const { ctx, width, height, barHeights, colors } = this;
        ctx.clearRect(0, 0, width, height);

        const barWidth = 18;
        const gap = 14;
        const totalWidth = 4 * barWidth + 3 * gap;
        const startX = (width - totalWidth) / 2;

        for (let i = 0; i < 4; i++) {
            const h = Math.max(22, barHeights[i] * (height - 12));
            const x = startX + i * (barWidth + gap);
            const y = (height - h) / 2;

            const colorConfig = colors[i];
            const gradient = ctx.createLinearGradient(x, y, x, y + h);
            gradient.addColorStop(0, colorConfig.top);
            gradient.addColorStop(1, colorConfig.bottom);

            ctx.fillStyle = gradient;
            ctx.shadowColor = colorConfig.top;
            ctx.shadowBlur = this.state === 'idle' ? 4 : 10;

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
