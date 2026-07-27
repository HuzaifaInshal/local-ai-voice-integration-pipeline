class UIChartRenderer {
    constructor(containerElementId) {
        this.container = document.getElementById(containerElementId);
        this.activeChart = null;
    }

    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        if (this.activeChart) {
            this.activeChart.destroy();
            this.activeChart = null;
        }
    }

    render(payload) {
        this.clear();
        if (!payload || !payload.display_type) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'visual-container';

        if (payload.display_type === 'chart') {
            this.renderChart(wrapper, payload);
        } else if (payload.display_type === 'table') {
            this.renderTable(wrapper, payload);
        } else if (payload.display_type === 'metric_card') {
            this.renderMetricCard(wrapper, payload);
        }

        this.container.appendChild(wrapper);
    }

    renderChart(parent, payload) {
        const canvas = document.createElement('canvas');
        canvas.id = 'parakeetChart';
        parent.appendChild(canvas);

        const ctx = canvas.getContext('2d');
        if (typeof Chart === 'undefined') {
            parent.innerHTML = `<p style="color:#94a3b8;">Chart.js loading... (Title: ${payload.title || 'Report'})</p>`;
            return;
        }

        const datasets = (payload.datasets || []).map(ds => ({
            label: ds.label || 'Value',
            data: ds.data || [],
            backgroundColor: 'rgba(16, 185, 129, 0.5)',
            borderColor: '#10b981',
            borderWidth: 2,
            borderRadius: 6
        }));

        this.activeChart = new Chart(ctx, {
            type: payload.chart_type || 'bar',
            data: {
                labels: payload.labels || [],
                datasets: datasets
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { labels: { color: '#f8fafc' } },
                    title: { display: true, text: payload.title || '', color: '#06b6d4', font: { size: 16 } }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                }
            }
        });
    }

    renderTable(parent, payload) {
        let html = `<h4 style="color:#06b6d4; margin-bottom:0.5rem;">${payload.title || 'Data Table'}</h4>`;
        html += `<div class="table-responsive"><table class="custom-table"><thead><tr>`;
        
        (payload.table_headers || []).forEach(h => {
            html += `<th>${h}</th>`;
        });
        html += `</tr></thead><tbody>`;

        (payload.rows || []).forEach(row => {
            html += `<tr>`;
            row.forEach(cell => { html += `<td>${cell}</td>`; });
            html += `</tr>`;
        });

        html += `</tbody></table></div>`;
        parent.innerHTML = html;
    }

    renderMetricCard(parent, payload) {
        parent.innerHTML = `
            <div class="metric-card">
                <div class="metric-sub">${payload.title || 'Key Metric'}</div>
                <div class="metric-val">${payload.metric_value || '0'}</div>
                <div class="metric-sub">${payload.metric_subtitle || ''}</div>
            </div>
        `;
    }
}

window.UIChartRenderer = UIChartRenderer;
