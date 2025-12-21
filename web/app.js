const API_URL = '/api/status';

// Chart Instance
let equityChart = null;

function initChart() {
    const ctx = document.getElementById('equityChart').getContext('2d');
    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Total Equity (USDT)',
                data: [],
                borderColor: '#00ff9d',
                backgroundColor: 'rgba(0, 255, 157, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(23, 25, 30, 0.9)',
                    titleColor: '#94a3b8',
                    bodyColor: '#e0e6ed',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

function updateDashboard() {
    fetch(API_URL)
        .then(response => response.json())
        .then(data => {
            renderSystemStatus(data.system);
            renderMarketData(data.market);
            renderAgents(data.agents);
            renderDecision(data.decision);
            renderLogs(data.logs);

            // New Renderers
            if (data.account) renderAccount(data.account);
            if (data.account) {
                // TODO: API should return positions array
                // For now, create mock data if no positions available
                const positions = data.positions || [];
                updatePositionInfo(data.account, positions);
            }
            if (data.chart_data && data.chart_data.equity) renderChart(data.chart_data.equity);

            // Layout v2 Renderers
            if (data.decision_history) renderDecisionTable(data.decision_history);
            if (data.trade_history) renderTradeHistory(data.trade_history);
        })
        .catch(err => console.error('Error fetching data:', err));
}

function renderTradeHistory(trades) {
    const tbody = document.querySelector('#trade-table tbody');
    if (!tbody) return;

    tbody.innerHTML = trades.map(t => {
        const time = t.record_time || t.timestamp || 'N/A';
        // Simplified time if needed: time.substring(5, 16) -> MM-DD HH:MM

        const symbol = t.symbol || 'BTC';
        const action = t.action || 'Trade';

        // Formatting numbers
        const fmtUsd = val => val ? '$' + Number(val).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '-';

        const price = fmtUsd(t.price);
        const cost = fmtUsd(t.cost);
        const exit = Number(t.exit_price) > 0 ? fmtUsd(t.exit_price) : '-';

        // PnL with Color
        let pnlHtml = '-';
        if (t.pnl !== undefined && t.pnl !== 0 && t.pnl !== '0.0') {
            const val = Number(t.pnl);
            const cls = val > 0 ? 'pos' : (val < 0 ? 'neg' : 'neutral');
            const sign = val > 0 ? '+' : '';
            pnlHtml = `<span class="val ${cls}">${sign}${val.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>`;
        }

        // Action Color
        let actCls = 'action-hold';
        if (action.includes('LONG') || action.includes('BUY')) actCls = 'action-buy';
        else if (action.includes('SHORT') || action.includes('SELL')) actCls = 'action-sell';

        return `
            <tr>
                <td>${time}</td>
                <td>${symbol}</td>
                <td class="${actCls}">${action}</td>
                <td>${price}</td>
                <td>${cost}</td>
                <td>${exit}</td>
                <td>${pnlHtml}</td>
            </tr>
        `;
    }).join('');
}

function renderDecisionTable(history) {
    const tbody = document.querySelector('#decision-table tbody');
    if (!tbody) return;

    tbody.innerHTML = history.map(d => {
        const time = d.timestamp || 'Just now';
        const symbol = d.symbol || 'BTCUSDT';
        const action = (d.action || 'HOLD').toUpperCase();
        const conf = d.confidence ? d.confidence.toFixed(0) + '%' : '-';

        let actionClass = 'action-hold';
        if (action.includes('LONG') || action.includes('BUY')) actionClass = 'action-buy';
        else if (action.includes('SHORT') || action.includes('SELL')) actionClass = 'action-sell';

        // Helper to format score cell
        const fmtScore = (key, label) => {
            if (!d.vote_details || d.vote_details[key] === undefined) return '<span class="cell-na">-</span>';
            const val = Math.round(d.vote_details[key]);
            const cls = val > 0 ? 'pos' : (val < 0 ? 'neg' : 'neutral');
            return `<span class="val ${cls}">${val}</span>`;
        };

        // Extract Agent Scores
        const stratHtml = fmtScore('strategist_total');
        const trend1hHtml = fmtScore('trend_1h');
        const osc1hHtml = fmtScore('oscillator_1h');
        const sentHtml = fmtScore('sentiment');

        // Multi-period signals (15m, 5m)
        const trend15mHtml = fmtScore('trend_15m');
        const osc15mHtml = fmtScore('oscillator_15m');
        const trend5mHtml = fmtScore('trend_5m');
        const osc5mHtml = fmtScore('oscillator_5m');

        // Combine 15m and 5m signals
        const signal15m = `<div style="font-size:0.75em">T:${d.vote_details?.trend_15m ? Math.round(d.vote_details.trend_15m) : '-'}<br>O:${d.vote_details?.oscillator_15m ? Math.round(d.vote_details.oscillator_15m) : '-'}</div>`;
        const signal5m = `<div style="font-size:0.75em">T:${d.vote_details?.trend_5m ? Math.round(d.vote_details.trend_5m) : '-'}<br>O:${d.vote_details?.oscillator_5m ? Math.round(d.vote_details.oscillator_5m) : '-'}</div>`;

        // Reason (truncated with tooltip)
        let reasonHtml = '<span class="cell-na">-</span>';
        if (d.reason) {
            const fullReason = d.reason.replace(/"/g, '&quot;'); // Escape quotes for HTML attribute
            const shortReason = d.reason.length > 40 ? d.reason.substring(0, 40) + '...' : d.reason;
            reasonHtml = `<span title="${fullReason}" style="font-size:0.8em;cursor:help;display:block;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${shortReason}</span>`;
        }

        // Position % (exact percentage)
        let posPctHtml = '<span class="cell-na">-</span>';
        if (d.position && d.position.position_pct !== undefined) {
            const pct = d.position.position_pct.toFixed(1);
            posPctHtml = `<span style="font-size:0.85em">${pct}%</span>`;
        }

        // Alignment status
        let alignedHtml = '<span class="cell-na">-</span>';
        if (d.multi_period_aligned !== undefined) {
            alignedHtml = d.multi_period_aligned
                ? '<span class="badge pos" title="Multi-period aligned">✅</span>'
                : '<span class="badge neutral" title="Not aligned">➖</span>';
        }

        // Risk & Guardian
        let riskHtml = '<span class="cell-na">-</span>';
        if (d.risk_level) {
            let cls = 'neutral';
            if (d.risk_level === 'safe') cls = 'pos';
            else if (d.risk_level === 'warning') cls = 'warn'; // Assuming css class exists or we use inline
            else if (d.risk_level === 'danger' || d.risk_level === 'fatal') cls = 'neg';
            riskHtml = `<span class="val ${cls}">${d.risk_level.toUpperCase()}</span>`;
        }

        let guardHtml = '<span class="cell-na">-</span>';
        if (d.guardian_passed !== undefined) {
            if (d.guardian_passed) {
                guardHtml = '<span class="badge pos" title="Passed">✅</span>';
            } else {
                const reason = d.guardian_reason || 'Blocked';
                guardHtml = `<span class="badge neg" title="${reason}">⛔</span>`;
            }
        }

        // Render Context Badges
        let contextHtml = '-';
        if (d.regime && d.position) {
            let reg = (d.regime.regime || 'unknown').toLowerCase();
            if (reg === 'trending_up') reg = 'UP';
            else if (reg === 'trending_down') reg = 'DOWN';
            else if (reg === 'choppy') reg = 'CHOP';
            else reg = reg.toUpperCase().substring(0, 4);

            let pos = (d.position.location || 'unknown').toLowerCase();
            // Simplify position text
            if (pos === 'middle') pos = 'MID';
            else if (pos === 'low') pos = 'LOW';
            else if (pos === 'high') pos = 'HIGH';
            else pos = pos.toUpperCase().substring(0, 3);

            contextHtml = `<span class="badge neutral">${reg}</span> <span class="badge neutral">${pos}</span>`;
        }

        return `
            <tr>
                <td>${time}</td>
                <td>${symbol}</td>
                <td class="${actionClass}">${action}</td>
                <td>${conf}</td>
                <td>${reasonHtml}</td>
                <td>${stratHtml}</td>
                <td>${trend1hHtml}</td>
                <td>${osc1hHtml}</td>
                <td>${signal15m}</td>
                <td>${signal5m}</td>
                <td>${sentHtml}</td>
                <td>${riskHtml}</td>
                <td>${guardHtml}</td>
                <td>${posPctHtml}</td>
                <td>${alignedHtml}</td>
                <td>${contextHtml}</td>
            </tr>
        `;
    }).join('');
}

function renderAccount(account) {
    const fmt = num => `$${num.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

    // Safety check helper
    const setTxt = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    setTxt('acc-equity', fmt(account.total_equity));
    setTxt('acc-wallet', fmt(account.wallet_balance));
    // Header equity also if exists
    setTxt('header-equity', fmt(account.total_equity));

    // PnL Styling
    const pnlEl = document.getElementById('acc-pnl');
    if (pnlEl) {
        pnlEl.textContent = fmt(account.total_pnl);
        if (account.total_pnl > 0) pnlEl.className = 'val pos';
        else if (account.total_pnl < 0) pnlEl.className = 'val neg';
        else pnlEl.className = 'val neutral';
    }
}

function renderChart(history) {
    if (!equityChart) return;

    // Update data safely
    const times = history.map(h => h.time);
    const values = history.map(h => h.value);

    equityChart.data.labels = times;
    equityChart.data.datasets[0].data = values;
    equityChart.update('none'); // Update without full re-animation for smoothness
}

function updatePositionInfo(account, positions = []) {
    const fmt = num => `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    // Update position count
    const countEl = document.getElementById('position-count');
    if (countEl) {
        const posCount = positions.length || 0;
        countEl.textContent = `📊 Positions: ${posCount}`;
    }

    // Update position details
    const detailsEl = document.getElementById('position-details');
    if (detailsEl) {
        if (positions && positions.length > 0) {
            detailsEl.innerHTML = positions.map(pos => {
                const pnlClass = pos.pnl > 0 ? 'pos' : (pos.pnl < 0 ? 'neg' : 'neutral');
                return `
                    <div style="display: flex; align-items: center; gap: 8px; padding: 4px 10px; background: rgba(255,255,255,0.05); border-radius: 4px;">
                        <span style="color: #e0e6ed; font-weight: 600;">${pos.symbol}</span>
                        <span style="color: #a0aec0; font-size: 0.8em;">${pos.quantity}</span>
                        <span class="val ${pnlClass}" style="font-size: 0.85em;">${fmt(pos.pnl)}</span>
                    </div>
        `;
            }).join('');
        } else {
            detailsEl.innerHTML = '<span style="color: #718096; font-size: 0.8em;">No open positions</span>';
        }
    }

    // Update total PnL with color
    const pnlEl = document.getElementById('position-pnl');
    if (pnlEl) {
        pnlEl.textContent = `Total PnL: ${fmt(account.total_pnl)}`;
        if (account.total_pnl > 0) {
            pnlEl.className = 'val pos';
        } else if (account.total_pnl < 0) {
            pnlEl.className = 'val neg';
        } else {
            pnlEl.className = 'val neutral';
        }
    }
}

// ... (renderSystemStatus and others remain same)

// Init
initChart();
setInterval(updateDashboard, 2000); // Poll every 2s
updateDashboard();

// Event Listeners for Controls
document.getElementById('btn-start').addEventListener('click', () => sendControl('start'));
document.getElementById('btn-pause').addEventListener('click', () => sendControl('pause'));
document.getElementById('btn-stop').addEventListener('click', () => sendControl('stop'));

// Symbol Selector
const symbolSelector = document.getElementById('symbol-selector');
if (symbolSelector) {
    symbolSelector.addEventListener('change', (e) => {
        const newSymbol = e.target.value;
        console.log('Symbol changed to:', newSymbol);
        // Note: Backend currently only supports BTCUSDT
        // This is a UI placeholder for future multi-symbol support
        alert(`Symbol switching to ${newSymbol} - Feature coming soon!\nCurrently only BTCUSDT is supported.`);
        // Reset to BTCUSDT
        e.target.value = 'BTCUSDT';
    });
}

function sendControl(action) {
    fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    })
        .then(res => res.json())
        .then(data => {
            console.log('Control sent:', action, data);
            updateDashboard(); // Immediate refresh
        })
        .catch(err => console.error('Control failed:', err));
}

function renderSystemStatus(system) {
    const statusEl = document.getElementById('sys-mode');

    // Status Logic
    if (system.mode) {
        statusEl.textContent = system.mode.toUpperCase();

        if (system.mode === 'Running') statusEl.className = 'value badge online';
        else if (system.mode === 'Paused') statusEl.className = 'value badge warning'; // Yellow-ish
        else statusEl.className = 'value badge offline';
    } else {
        // Fallback
        statusEl.textContent = system.running ? "ONLINE" : "OFFLINE";
    }
}


function renderMarketData(market) {
    // Removed as per request (Context merged into Table/Logs)
}

function updateTagClass(el, text) {
    text = text.toLowerCase();
    el.className = 'value-tag neutral';

    if (text.includes('bull') || text.includes('trend') || text === 'bullish') {
        el.className = 'value-tag bullish';
    } else if (text.includes('bear') || text.includes('volatile') || text === 'bearish') {
        el.className = 'value-tag bearish';
    }
}

function renderAgents(agents) {
    // Updated IDs function renderAgentVisualizers(agents) {
    // Widgets removed as per user request.
    // Data now shown in Logs and Decision Table.
}

function renderDecision(decision) {
    // Deprecated in V2 (Using Table now)
    // But we might want to highlight latest row if needed.
    // For now, do nothing or update if we kept the card.
    // Since we removed #decision-box from HTML, this function can share empty logic or be removed.
}

function renderLogs(logs) {
    const container = document.getElementById('logs-container');
    if (!container) return;

    // Smart Scroll: Check if user is near bottom before update
    const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 100;
    const previousScrollHeight = container.scrollHeight;
    const previousScrollTop = container.scrollTop;

    container.innerHTML = logs.map(logLine => {
        // Strip ANSI colors
        let cleanLine = logLine.replace(/\x1b\[[0-9;]*m/g, '');

        // Parse: [time] message
        let content = cleanLine;
        let time = '';

        const timeMatch = cleanLine.match(/^\[(.*?)\]\s*(.*)/);
        if (timeMatch) {
            time = `<span class="log-time">${timeMatch[1]}</span>`;
            content = timeMatch[2];
        }

        // Agent Badges
        if (content.includes('[Oracle]')) {
            content = content.replace('[Oracle]', '<span class="agent-tag oracle">Oracle</span>');
        } else if (content.includes('[Strategist]')) {
            content = content.replace('[Strategist]', '<span class="agent-tag strategist">Strategist</span>');
        } else if (content.includes('[Critic]')) {
            content = content.replace('[Critic]', '<span class="agent-tag critic">Critic</span>');
        } else if (content.includes('[Guardian]')) {
            content = content.replace('[Guardian]', '<span class="agent-tag guardian">Guardian</span>');
        } else if (content.includes('[Executor]')) {
            content = content.replace('[Executor]', '<span class="agent-tag" style="color:#55efc4">Executor</span>');
        }

        return `<div class="log-entry">${time} ${content}</div>`;
    }).join('');

    // Restore Scroll Position
    if (isScrolledToBottom) {
        container.scrollTop = container.scrollHeight; // Auto-scroll to newest
    } else {
        // Maintain relative position if content size changed (optional, but pure restoration is safer for now)
        container.scrollTop = previousScrollTop;
    }
}

// Init
initChart();
setInterval(updateDashboard, 2000); // Poll every 2s
updateDashboard();
