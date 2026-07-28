class UIChartRenderer {
    constructor(containerId) {
        this.container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
        this.currentChart = null;
    }

    render(payload) {
        if (!this.container || !payload) return;
        this.clear();

        const displayType = payload.display_type || 'chart';

        if (displayType === 'metric_card') {
            this.renderMetricCard(payload);
        } else if (displayType === 'table' && payload.rows && payload.rows.length > 0) {
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
        card.innerHTML = `
            <div class="metric-val">${payload.metric_value || ''}</div>
            <div class="metric-sub">${payload.metric_subtitle || payload.title || ''}</div>
        `;
        this.container.appendChild(card);
    }

    renderTable(payload) {
        const headers = payload.table_headers || payload.labels || [];
        const rows = payload.rows || [];

        const wrapper = document.createElement('div');
        wrapper.className = 'table-responsive';

        const table = document.createElement('table');
        table.className = 'custom-table';

        if (headers.length > 0) {
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            headers.forEach(h => {
                const th = document.createElement('th');
                th.innerText = h;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
        }

        const tbody = document.createElement('tbody');
        rows.forEach(row => {
            const tr = document.createElement('tr');
            row.forEach(cell => {
                const td = document.createElement('td');
                td.innerText = cell;
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
        canvas.style.cssText = 'max-height: 280px; width: 100%; margin-top: 1rem;';
        this.container.appendChild(canvas);

        const chartType = payload.chart_type || 'bar';

        let labels = payload.labels || [];
        let datasets = payload.datasets || [];

        if (labels.length === 0 && datasets.length > 0 && datasets[0].label) {
            labels = datasets.map(d => d.label);
            const dataValues = datasets.map(d => (Array.isArray(d.data) ? d.data[0] : d.data));
            datasets = [{
                label: payload.title || 'Metrics',
                data: dataValues,
                backgroundColor: [
                    '#10b981', '#06b6d4', '#8b5cf6', '#f59e0b', '#ef4444', '#3b82f6'
                ],
                borderRadius: 6
            }];
        } else {
            datasets = datasets.map((ds, idx) => ({
                label: ds.label || 'Metric',
                data: ds.data || [],
                backgroundColor: [
                    '#10b981', '#06b6d4', '#8b5cf6', '#f59e0b', '#ef4444', '#3b82f6'
                ],
                borderRadius: 6
            }));
        }

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
                        color: '#f8fafc',
                        font: { size: 14, weight: '600' }
                    },
                    legend: {
                        display: chartType === 'pie' || datasets.length > 1,
                        labels: { color: '#94a3b8' }
                    }
                },
                scales: chartType === 'pie' ? {} : {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: '#94a3b8' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#94a3b8' }
                    }
                }
            }
        });
    }
}

window.UIChartRenderer = UIChartRenderer;
