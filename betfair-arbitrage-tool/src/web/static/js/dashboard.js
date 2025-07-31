// Dashboard JavaScript

// Initialize Socket.IO connection
const socket = io();

// Dashboard state
let automationEnabled = false;
let activeBets = [];
let betQueue = [];
let opportunities = [];
let performanceData = {};

// Chart instances
let profitChart = null;
let bookmakerChart = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeCharts();
    loadSettings();
    setupEventListeners();
    connectWebSocket();
    updateDashboard();
});

// Setup event listeners
function setupEventListeners() {
    // Automation toggle
    document.getElementById('automationToggle').addEventListener('change', function(e) {
        toggleAutomation(e.target.checked);
    });
    
    // Save settings
    document.getElementById('saveSettings').addEventListener('click', saveSettings);
    
    // Refresh data every 5 seconds
    setInterval(updateDashboard, 5000);
}

// WebSocket connection and events
function connectWebSocket() {
    socket.on('connect', function() {
        console.log('Connected to server');
        addActivityFeedItem('Connected to server', 'info');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        addActivityFeedItem('Disconnected from server', 'danger');
    });
    
    socket.on('new_bet', function(data) {
        handleNewBet(data);
    });
    
    socket.on('bet_settled', function(data) {
        handleBetSettled(data);
    });
    
    socket.on('new_opportunity', function(data) {
        handleNewOpportunity(data);
    });
    
    socket.on('performance_update', function(data) {
        updatePerformanceMetrics(data);
    });
    
    socket.on('automation_status_changed', function(data) {
        updateAutomationStatus(data.enabled);
    });
}

// Toggle automation
function toggleAutomation(enabled) {
    fetch('/api/automation/toggle', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled: enabled })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateAutomationStatus(enabled);
            addActivityFeedItem(`Automation ${enabled ? 'enabled' : 'disabled'}`, enabled ? 'success' : 'warning');
        }
    });
}

// Update automation status
function updateAutomationStatus(enabled) {
    automationEnabled = enabled;
    const toggle = document.getElementById('automationToggle');
    const status = document.getElementById('automationStatus');
    
    toggle.checked = enabled;
    status.textContent = enabled ? 'ON' : 'OFF';
    status.className = enabled ? 'badge bg-success' : 'badge bg-danger';
}

// Update dashboard data
function updateDashboard() {
    // Fetch dashboard stats
    fetch('/api/dashboard/stats')
        .then(response => response.json())
        .then(data => {
            updatePerformanceMetrics(data.performance);
            document.getElementById('activeBetsCount').textContent = data.active_bets_count;
            document.getElementById('queueCount').textContent = data.queued_bets_count;
            updateAutomationStatus(data.automation_status);
        });
    
    // Fetch active bets
    fetch('/api/bets/active')
        .then(response => response.json())
        .then(data => {
            updateActiveBetsTable(data.bets);
        });
    
    // Fetch bet queue
    fetch('/api/bets/queue')
        .then(response => response.json())
        .then(data => {
            updateBetQueueTable(data.queue);
        });
    
    // Fetch opportunities
    fetch('/api/opportunities/current')
        .then(response => response.json())
        .then(data => {
            updateOpportunitiesList(data.opportunities);
        });
}

// Update performance metrics
function updatePerformanceMetrics(data) {
    performanceData = data;
    
    // Update stat cards
    document.getElementById('balance').textContent = `£${formatNumber(data.balance)}`;
    document.getElementById('todayPL').textContent = `£${formatNumber(data.total_profit)}`;
    document.getElementById('roi').textContent = `${data.roi.toFixed(1)}%`;
    document.getElementById('winRate').textContent = `${data.win_rate.toFixed(1)}%`;
    
    // Update charts
    updateProfitChart();
}

// Handle new bet
function handleNewBet(betData) {
    activeBets.unshift(betData);
    updateActiveBetsTable(activeBets.slice(0, 50));
    
    addActivityFeedItem(
        `New bet placed: ${betData.selection_name} @ ${betData.odds} (£${betData.stake})`,
        'primary'
    );
    
    // Show notification
    showNotification('New Bet Placed', `${betData.selection_name} @ ${betData.odds}`);
}

// Handle bet settled
function handleBetSettled(data) {
    // Remove from active bets
    activeBets = activeBets.filter(bet => bet.id !== data.bet_id);
    updateActiveBetsTable(activeBets.slice(0, 50));
    
    const profitClass = data.profit >= 0 ? 'success' : 'danger';
    addActivityFeedItem(
        `Bet settled: ${data.profit >= 0 ? '+' : ''}£${data.profit.toFixed(2)}`,
        profitClass
    );
}

// Handle new opportunity
function handleNewOpportunity(opportunity) {
    opportunities.unshift(opportunity);
    updateOpportunitiesList(opportunities.slice(0, 20));
    
    if (opportunity.profit_percentage > 1) {
        showNotification('High Value Opportunity!', `${opportunity.profit_percentage.toFixed(2)}% profit`);
    }
}

// Update active bets table
function updateActiveBetsTable(bets) {
    const tbody = document.getElementById('activeBetsTable');
    
    if (bets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No active bets</td></tr>';
        return;
    }
    
    tbody.innerHTML = bets.map(bet => `
        <tr>
            <td>${formatTime(bet.placed_at)}</td>
            <td>${bet.market_name}</td>
            <td>${bet.selection_name}</td>
            <td><span class="badge bg-${bet.bet_type === 'BACK' ? 'primary' : 'info'}">${bet.bet_type}</span></td>
            <td>${bet.odds}</td>
            <td>£${bet.stake}</td>
            <td><span class="bet-status ${bet.status.toLowerCase()}">${bet.status}</span></td>
        </tr>
    `).join('');
}

// Update bet queue table
function updateBetQueueTable(queue) {
    const tbody = document.getElementById('betQueueTable');
    
    if (queue.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No bets in queue</td></tr>';
        return;
    }
    
    tbody.innerHTML = queue.map((item, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${item.opportunity_type}</td>
            <td class="profit">+£${item.expected_profit.toFixed(2)}</td>
            <td>
                <button class="btn btn-sm btn-outline-danger" onclick="removeFromQueue('${item.id}')">
                    <i class="fas fa-times"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

// Update opportunities list
function updateOpportunitiesList(opps) {
    const list = document.getElementById('opportunitiesList');
    
    if (opps.length === 0) {
        list.innerHTML = '<div class="list-group-item text-center text-muted">No opportunities found</div>';
        return;
    }
    
    list.innerHTML = opps.map(opp => `
        <div class="list-group-item opportunity-item">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-1">${opp.market_name}</h6>
                    <small class="text-muted">${opp.bookmakers.join(' vs ')}</small>
                </div>
                <div class="text-end">
                    <div class="profit mb-1">+${opp.profit_percentage.toFixed(2)}%</div>
                    <span class="badge bg-${opp.type === 'ARBITRAGE' ? 'success' : 'primary'} opportunity-badge">
                        ${opp.type}
                    </span>
                </div>
            </div>
        </div>
    `).join('');
}

// Add activity feed item
function addActivityFeedItem(message, type = 'info') {
    const feed = document.getElementById('activityFeed');
    const timestamp = new Date().toLocaleTimeString();
    
    const item = document.createElement('div');
    item.className = 'feed-item';
    item.innerHTML = `
        <div class="d-flex justify-content-between">
            <span class="text-${type}">${message}</span>
            <span class="timestamp">${timestamp}</span>
        </div>
    `;
    
    feed.insertBefore(item, feed.firstChild);
    
    // Keep only last 50 items
    while (feed.children.length > 50) {
        feed.removeChild(feed.lastChild);
    }
}

// Initialize charts
function initializeCharts() {
    // Profit/Loss Chart
    const profitCtx = document.getElementById('profitChart').getContext('2d');
    profitChart = new Chart(profitCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Cumulative Profit',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '£' + value;
                        }
                    }
                }
            }
        }
    });
    
    // Bookmaker Distribution Chart
    const bookmakerCtx = document.getElementById('bookmakerChart').getContext('2d');
    bookmakerChart = new Chart(bookmakerCtx, {
        type: 'doughnut',
        data: {
            labels: ['Betfair', 'Paddy Power', 'William Hill', 'Bet365', 'BetMGM', 'Ladbrokes'],
            datasets: [{
                data: [30, 20, 15, 15, 10, 10],
                backgroundColor: [
                    '#FF6384',
                    '#36A2EB',
                    '#FFCE56',
                    '#4BC0C0',
                    '#9966FF',
                    '#FF9F40'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// Update profit chart
function updateProfitChart() {
    // Add dummy data for demo
    const labels = [];
    const data = [];
    let cumulative = 0;
    
    for (let i = 0; i < 24; i++) {
        labels.push(`${i}:00`);
        cumulative += Math.random() * 100 - 30;
        data.push(cumulative);
    }
    
    profitChart.data.labels = labels;
    profitChart.data.datasets[0].data = data;
    profitChart.update();
}

// Load settings
function loadSettings() {
    fetch('/api/settings')
        .then(response => response.json())
        .then(settings => {
            document.getElementById('maxStake').value = settings.max_stake;
            document.getElementById('minOdds').value = settings.min_odds;
            document.getElementById('maxOdds').value = settings.max_odds;
            document.getElementById('minProfitPercentage').value = settings.min_profit_percentage;
            document.getElementById('maxExposure').value = settings.max_exposure;
            document.getElementById('betDelay').value = settings.bet_delay;
        });
}

// Save settings
function saveSettings() {
    const settings = {
        max_stake: parseFloat(document.getElementById('maxStake').value),
        min_odds: parseFloat(document.getElementById('minOdds').value),
        max_odds: parseFloat(document.getElementById('maxOdds').value),
        min_profit_percentage: parseFloat(document.getElementById('minProfitPercentage').value),
        max_exposure: parseFloat(document.getElementById('maxExposure').value),
        bet_delay: parseInt(document.getElementById('betDelay').value)
    };
    
    fetch('/api/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
            modal.hide();
            
            addActivityFeedItem('Settings updated successfully', 'success');
        }
    });
}

// Utility functions
function formatNumber(num) {
    return num.toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
}

function showNotification(title, message) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, {
            body: message,
            icon: '/static/img/icon.png'
        });
    }
}

// Request notification permission
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}