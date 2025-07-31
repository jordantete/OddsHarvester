"""Flask application for Betfair arbitrage tool dashboard."""

import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import redis
import json
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

# Initialize extensions
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

# In-memory storage for demo (replace with database in production)
active_bets = []
bet_queue = []
opportunities = []
performance_data = {
    'total_bets': 0,
    'active_bets': 0,
    'total_profit': 0.0,
    'win_rate': 0.0,
    'roi': 0.0,
    'balance': 10000.0  # Starting balance
}


@app.route('/')
def index():
    """Render main dashboard."""
    return render_template('dashboard.html')


@app.route('/api/dashboard/stats')
def get_dashboard_stats():
    """Get current dashboard statistics."""
    stats = {
        'timestamp': datetime.utcnow().isoformat(),
        'performance': performance_data,
        'active_bets_count': len(active_bets),
        'queued_bets_count': len(bet_queue),
        'opportunities_count': len(opportunities),
        'automation_status': get_automation_status()
    }
    return jsonify(stats)


@app.route('/api/bets/active')
def get_active_bets():
    """Get list of active bets."""
    return jsonify({
        'bets': active_bets[-50:],  # Last 50 active bets
        'total': len(active_bets)
    })


@app.route('/api/bets/queue')
def get_bet_queue():
    """Get current bet queue."""
    return jsonify({
        'queue': bet_queue[:20],  # Next 20 bets in queue
        'total': len(bet_queue)
    })


@app.route('/api/opportunities/current')
def get_current_opportunities():
    """Get current arbitrage and value bet opportunities."""
    return jsonify({
        'opportunities': opportunities[:20],  # Top 20 opportunities
        'total': len(opportunities)
    })


@app.route('/api/automation/toggle', methods=['POST'])
def toggle_automation():
    """Toggle automated betting on/off."""
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    # Store automation state in Redis
    redis_client.set('automation_enabled', str(enabled))
    
    # Emit status change via WebSocket
    socketio.emit('automation_status_changed', {
        'enabled': enabled,
        'timestamp': datetime.utcnow().isoformat()
    })
    
    return jsonify({'success': True, 'enabled': enabled})


@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Get or update automation settings."""
    if request.method == 'GET':
        settings = {
            'max_stake': float(redis_client.get('max_stake') or 100),
            'min_odds': float(redis_client.get('min_odds') or 1.5),
            'max_odds': float(redis_client.get('max_odds') or 10.0),
            'min_profit_percentage': float(redis_client.get('min_profit_percentage') or 0.5),
            'max_exposure': float(redis_client.get('max_exposure') or 1000),
            'bet_delay': int(redis_client.get('bet_delay') or 2)
        }
        return jsonify(settings)
    
    else:  # POST
        data = request.get_json()
        for key, value in data.items():
            redis_client.set(key, str(value))
        
        socketio.emit('settings_updated', data)
        return jsonify({'success': True, 'settings': data})


# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'data': 'Connected to bet monitoring dashboard'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('request_update')
def handle_update_request():
    """Handle request for immediate data update."""
    emit('dashboard_update', {
        'performance': performance_data,
        'active_bets': active_bets[-10:],
        'bet_queue': bet_queue[:5],
        'opportunities': opportunities[:5]
    })


def get_automation_status():
    """Get current automation status."""
    enabled = redis_client.get('automation_enabled')
    return enabled.decode() == 'True' if enabled else False


# Simulation functions for demo (replace with real implementation)
def emit_new_bet(bet_data):
    """Emit new bet via WebSocket."""
    socketio.emit('new_bet', bet_data)
    active_bets.append(bet_data)
    
    # Update performance data
    performance_data['total_bets'] += 1
    performance_data['active_bets'] = len(active_bets)


def emit_bet_settled(bet_id, profit):
    """Emit bet settlement via WebSocket."""
    socketio.emit('bet_settled', {
        'bet_id': bet_id,
        'profit': profit,
        'timestamp': datetime.utcnow().isoformat()
    })
    
    # Update performance data
    performance_data['total_profit'] += profit
    performance_data['balance'] += profit
    
    # Remove from active bets
    global active_bets
    active_bets = [b for b in active_bets if b.get('id') != bet_id]
    performance_data['active_bets'] = len(active_bets)


def emit_new_opportunity(opportunity):
    """Emit new opportunity via WebSocket."""
    socketio.emit('new_opportunity', opportunity)
    opportunities.append(opportunity)
    
    # Keep only recent opportunities
    if len(opportunities) > 100:
        opportunities.pop(0)


def emit_performance_update():
    """Emit performance update via WebSocket."""
    socketio.emit('performance_update', performance_data)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)