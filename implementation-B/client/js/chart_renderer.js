class UIChartRenderer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentChart = null;
    }

    render(payload) {
        if (!this.container || !payload) return;
        this.clear();

        const displayType = payload.display_type || 'chart';

        if (displayType === 'metric_card') {
            this.renderMetricCard(payload);
        } else if (displayType === 'table') {
            this.renderTable(payload);
        } else {
            this.renderChart(payload);
        }
    }

    clear() {
        if (this.currentChart) {
            this.currentChart.destroy();
            this.currentChart = null;
        }
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    renderMetricCard(payload) {
        const card = document.createElement('div');
        card.className = 'metric-card';
        card.style.cssText = `
            background: linear-gradient(135deg, rgba(66, 133, 244, 0.1), rgba(52, 168, 83, 0.1));
            border: 1px solid rgba(66, 133, 244, 0.3);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
            margin-top: 1rem;
        `;
        card.innerHTML = `
            <div style="font-size: 2rem; font-weight: 700; color: #1967d2;">${payload.metric_value || ''}</div>
            <div style="font-size: 0.85rem; color: #5f6368; margin-top: 0.25rem;">${payload.metric_subtitle || payload.title || ''}</div>
        `;
        this.container.appendChild(card);
    }

    renderTable(payload) {
        const headers = payload.table_headers || [];
        const rows = payload.rows || [];

        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'overflow-x: auto; margin-top: 1rem;';

        const table = document.createElement('table');
        table.style.cssText = `
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            text-align: left;
        `;

        if (headers.length > 0) {
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            headers.forEach(h => {
                const th = document.createElement('th');
                th.innerText = h;
                th.style.cssText = 'padding: 0.6rem 0.8rem; background: #e8f0fe; color: #1967d2; border-bottom: 2px solid #aecbfa; font-weight: 600;';
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
        }

        const tbody = document.createElement('tbody');
        rows.forEach(row => {
            const tr = document.createElement('tr');
            tr.style.cssText = 'border-bottom: 1px solid #e0e0e0;';
            row.forEach(cell => {
                const td = document.createElement('td');
                td.innerText = cell;
                td.style.cssText = 'padding: 0.6rem 0.8rem; color: #3c4043;';
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        wrapper.appendChild(table);
        this.container.appendChild(wrapper);
    }

    renderChart(payload) {
        if (!window.Chart) return;

        const canvas = document.createElement('canvas');
        canvas.style.cssText = 'max-height: 240px; width: 100%; margin-top: 1rem;';
        this.container.appendChild(canvas);

        const chartType = payload.chart_type || 'bar';
        const labels = payload.labels || [];
        const datasets = (payload.datasets || []).map((ds, idx) => ({
            label: ds.label || 'Metric',
            data: ds.data || [],
            backgroundColor: [
                '#4285f4', '#34a853', '#fbbc05', '#ea4335', '#ab47bc', '#00acc1'
            ],
            borderRadius: 6
        }));

        this.currentChart = new window.Chart(canvas, {
            type: chartType,
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: !!payload.title,
                        text: payload.title || '',
                        color: '#1f1f1f',
                        font: { size: 14, weight: '600' }
                    },
                    legend: {
                        display: chartType === 'pie'
                    }
                },
                scales: chartType === 'pie' ? {} : {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0, 0, 0, 0.05)' }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }
}

window.UIChartRenderer = UIChartRenderer;
