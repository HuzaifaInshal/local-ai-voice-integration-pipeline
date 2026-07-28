class MusicVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        
        this.numBars = 28;
        this.barHeights = new Float32Array(this.numBars);
        this.targetHeights = new Float32Array(this.numBars);
        this.state = 'idle'; // 'idle', 'listening', 'speaking', 'thinking'
        this.analyser = null;
        this.phase = 0;
        this.animId = null;

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
        this.width = rect.width || 300;
        this.height = rect.height || 100;
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = this.width * dpr;
        this.canvas.height = this.height * dpr;
        this.ctx.scale(dpr, dpr);
    }

    startAnimation() {
        const render = () => {
            this.update();
            this.draw();
            this.animId = requestAnimationFrame(render);
        };
        render();
    }

    update() {
        this.phase += 0.08;
        const count = this.numBars;

        if (this.state === 'listening' && this.analyser) {
            const bufferLength = this.analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            this.analyser.getByteFrequencyData(dataArray);

            for (let i = 0; i < count; i++) {
                const dataIndex = Math.floor((i / count) * bufferLength);
                const val = dataArray[dataIndex] / 255.0;
                const target = Math.max(0.08, val * 0.95);
                this.targetHeights[i] = target;
            }
        } else if (this.state === 'speaking') {
            for (let i = 0; i < count; i++) {
                const wave1 = Math.sin(this.phase * 1.5 + i * 0.25);
                const wave2 = Math.cos(this.phase * 2.2 - i * 0.35);
                const wave3 = Math.sin(this.phase * 0.8 + i * 0.15);
                const combined = (wave1 * 0.4 + wave2 * 0.35 + wave3 * 0.25 + 1) / 2;
                const noise = Math.sin(this.phase * 3.7 + i * 1.3) * 0.15;
                const target = Math.min(0.95, Math.max(0.1, combined * 0.8 + noise));
                this.targetHeights[i] = target;
            }
        } else if (this.state === 'thinking') {
            for (let i = 0; i < count; i++) {
                const wave = Math.sin(this.phase * 2.5 + i * 0.4);
                const target = (wave + 1) / 2 * 0.6 + 0.15;
                this.targetHeights[i] = target;
            }
        } else {
            // Idle state: soft subtle wave flow
            for (let i = 0; i < count; i++) {
                const wave = Math.sin(this.phase * 0.6 + i * 0.2);
                const target = (wave + 1) / 2 * 0.18 + 0.06;
                this.targetHeights[i] = target;
            }
        }

        // Lerp for smooth movements
        for (let i = 0; i < count; i++) {
            this.barHeights[i] += (this.targetHeights[i] - this.barHeights[i]) * 0.2;
        }
    }

    draw() {
        const { ctx, width, height, numBars, barHeights } = this;
        ctx.clearRect(0, 0, width, height);

        const totalSpacing = width * 0.28;
        const barWidth = (width - totalSpacing) / numBars;
        const gap = totalSpacing / (numBars + 1);

        for (let i = 0; i < numBars; i++) {
            const h = Math.max(6, barHeights[i] * (height - 24));
            const x = gap + i * (barWidth + gap);
            const y = (height - h) / 2;

            // Gradient: Cyan to Emerald to Purple glow
            const hue = (175 + (i / numBars) * 90 + Math.sin(this.phase * 0.5) * 15) % 360;
            const gradient = ctx.createLinearGradient(x, y, x, y + h);
            gradient.addColorStop(0, `hsl(${hue}, 100%, 65%)`);
            gradient.addColorStop(0.5, `hsl(${(hue + 25) % 360}, 95%, 55%)`);
            gradient.addColorStop(1, `hsl(${(hue + 50) % 360}, 90%, 45%)`);

            ctx.fillStyle = gradient;
            ctx.shadowColor = `hsl(${hue}, 100%, 60%)`;
            ctx.shadowBlur = this.state === 'idle' ? 4 : 14;

            const radius = Math.min(barWidth / 2, 4);
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

window.MusicVisualizer = MusicVisualizer;
