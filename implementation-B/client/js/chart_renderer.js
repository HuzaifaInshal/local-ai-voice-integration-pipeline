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
        } else if (displayType === 'empty_state') {
            this.renderEmptyState(payload);
        } else if (displayType === 'table' && payload.rows && payload.rows.length > 0) {
            this.renderTable(payload);
        } else {
            // Default or fallback to dynamic Chart rendering
            this.renderChart(payload);
        }
    }

    renderEmptyState(payload) {
        const card = document.createElement('div');
        card.className = 'empty-state-card';
        card.style.cssText = `
            background: #f8f9fa;
            border: 1.5px dashed #dadce0;
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            text-align: center;
            margin: 0.75rem 0;
            color: #5f6368;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
            animation: fadeInScreen 0.3s ease forwards;
        `;
        card.innerHTML = `
            <div style="font-size: 1.6rem; margin-bottom: 0.4rem; color: #1a73e8;">🔍</div>
            <div style="font-weight: 600; font-size: 0.95rem; color: #3c4043;">${payload.title || 'No Matching Records Found'}</div>
            <div style="font-size: 0.85rem; margin-top: 0.3rem; color: #70757a; line-height: 1.4;">${payload.message || 'No data was returned for your query criteria.'}</div>
        `;
        this.container.appendChild(card);
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
        if (!payload || !payload.rows || !Array.isArray(payload.rows) || payload.rows.length === 0) return;

        let headers = payload.table_headers || payload.labels || [];
        const rawRows = payload.rows;

        // Normalize rows and headers if rows are objects
        let normalizedRows = [];
        if (typeof rawRows[0] === 'object' && rawRows[0] !== null && !Array.isArray(rawRows[0])) {
            const keys = Object.keys(rawRows[0]);
            if (headers.length === 0) {
                headers = keys.map(k => k.replace(/_/g, ' ').toUpperCase());
            }
            normalizedRows = rawRows.map(obj => keys.map(k => obj[k]));
        } else {
            normalizedRows = rawRows;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'table-wrapper';
        wrapper.style.cssText = 'overflow-x: auto; margin-top: 1rem; border-radius: 8px; border: 1px solid rgba(0,0,0,0.1);';

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
        normalizedRows.forEach(row => {
            const tr = document.createElement('tr');
            tr.style.cssText = 'border-bottom: 1px solid #e0e0e0;';
            const cellList = Array.isArray(row) ? row : [row];
            cellList.forEach(cell => {
                const td = document.createElement('td');
                let displayVal = cell;
                if (typeof cell === 'number') {
                    displayVal = cell >= 1000 ? cell.toLocaleString() : cell;
                } else if (cell === null || cell === undefined) {
                    displayVal = '-';
                } else {
                    displayVal = String(cell);
                }
                td.innerText = displayVal;
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
        canvas.style.cssText = 'max-height: 260px; width: 100%; margin-top: 1rem;';
        this.container.appendChild(canvas);

        const chartType = payload.chart_type || 'bar';

        // Auto-adapt datasets if model provided datasets array with individual labels
        let labels = payload.labels || [];
        let datasets = payload.datasets || [];

        if (labels.length === 0 && datasets.length > 0 && datasets[0].label) {
            labels = datasets.map(d => d.label);
            const dataValues = datasets.map(d => (Array.isArray(d.data) ? d.data[0] : d.data));
            datasets = [{
                label: payload.title || 'Metrics',
                data: dataValues,
                backgroundColor: [
                    '#4285f4', '#34a853', '#fbbc05', '#ea4335', '#ab47bc', '#00acc1'
                ],
                borderRadius: 6
            }];
        } else {
            datasets = datasets.map((ds, idx) => ({
                label: ds.label || 'Metric',
                data: ds.data || [],
                backgroundColor: [
                    '#4285f4', '#34a853', '#fbbc05', '#ea4335', '#ab47bc', '#00acc1'
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
                        color: '#1f1f1f',
                        font: { size: 14, weight: '600' }
                    },
                    legend: {
                        display: chartType === 'pie' || datasets.length > 1
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
