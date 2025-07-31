# Betfair Exchange Arbitrage & Value Bet Tool

A comprehensive automated betting tool that identifies arbitrage opportunities and value bets across Betfair Exchange and major bookmakers including PaddyPower, William Hill, Bet365, BetMGM, and Ladbrokes.

## Features

### 🎯 Core Functionality
- **Multi-Bookmaker Support**: Integrates with Betfair Exchange, PaddyPower, William Hill, Bet365, BetMGM, and Ladbrokes
- **Arbitrage Detection**: Real-time identification of arbitrage opportunities across bookmakers
- **Value Bet Analysis**: Advanced algorithms to identify positive expected value bets
- **Automated Bet Placement**: Configurable automation with safety controls
- **Live Dashboard**: Real-time monitoring of bets, opportunities, and performance

### 📊 Analytics & Tracking
- **Profit Tracking**: Comprehensive profit/loss tracking with historical data
- **ROI Analytics**: Detailed ROI tracking by bookmaker, sport, and strategy
- **Performance Metrics**: Win rate, Sharpe ratio, maximum drawdown analysis
- **Custom Reports**: Generate detailed performance reports

### 🛡️ Risk Management
- **Bankroll Management**: Kelly criterion and fractional staking strategies
- **Exposure Limits**: Configurable maximum exposure limits
- **Stop Loss**: Automated stop-loss functionality
- **Bet Validation**: Pre-bet validation to ensure profitable opportunities

### 🖥️ Dashboard Features
- **Real-time Updates**: WebSocket-based live updates
- **Active Bet Monitoring**: Track all active bets across bookmakers
- **Opportunity Feed**: Live feed of arbitrage and value bet opportunities
- **Performance Charts**: Visual representation of profit/loss and ROI
- **Activity Log**: Detailed log of all betting activity

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Betfair API credentials
- API access for other bookmakers (where available)

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/betfair-arbitrage-tool.git
cd betfair-arbitrage-tool
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API credentials and configuration
```

5. **Set up PostgreSQL database**
```bash
createdb betfair_arbitrage
# Run migrations (implementation needed)
```

6. **Start Redis**
```bash
redis-server
```

## Configuration

### API Credentials

Edit the `.env` file with your credentials:

```env
# Betfair API
BETFAIR_USERNAME=your_username
BETFAIR_PASSWORD=your_password
BETFAIR_APP_KEY=your_app_key
BETFAIR_CERT_FILE=path/to/certificate.crt
BETFAIR_KEY_FILE=path/to/key.key

# Other bookmaker credentials
PADDYPOWER_API_KEY=your_key
WILLIAMHILL_API_KEY=your_key
# ... etc
```

### Automation Settings

Configure automation parameters in the dashboard or `.env`:

- `MIN_ARBITRAGE_PROFIT`: Minimum profit percentage for arbitrage alerts (default: 0.5%)
- `MIN_VALUE_BET_EDGE`: Minimum edge percentage for value bets (default: 2.0%)
- `MAX_STAKE`: Maximum stake per bet (default: £1000)
- `UPDATE_INTERVAL`: Market update interval in seconds (default: 10)

## Usage

### Starting the Application

1. **Start the web dashboard**
```bash
python src/web/app.py
```

2. **Access the dashboard**
Open your browser and navigate to `http://localhost:5000`

3. **Enable automation**
Toggle the "Auto-Betting" switch in the dashboard to start automated betting

### Manual Operation

You can also use the tool programmatically:

```python
from src.strategies.arbitrage import ArbitrageScanner
from src.api.betfair_client import BetfairClient

# Initialize clients
betfair = BetfairClient()
scanner = ArbitrageScanner()

# Scan for opportunities
opportunities = scanner.scan_all_markets()

# Place bets manually
for opp in opportunities:
    if opp.profit_percentage > 1.0:
        scanner.execute_arbitrage(opp)
```

## Dashboard Overview

### Main Dashboard
- **Performance Overview**: Real-time balance, P/L, ROI, and win rate
- **Active Bets**: Monitor all currently active bets
- **Bet Queue**: View pending bets awaiting execution
- **Live Opportunities**: Real-time feed of profitable opportunities
- **Activity Feed**: Chronological log of all betting activity

### Charts & Analytics
- **Profit/Loss Chart**: Visualize cumulative profit over time
- **Bookmaker Distribution**: See bet distribution across bookmakers
- **Performance Metrics**: Detailed analytics and KPIs

### Settings
- Configure automation parameters
- Set risk management limits
- Adjust betting strategies

## Safety Features

1. **Maximum Exposure Limits**: Prevents excessive risk exposure
2. **Bet Delay**: Configurable delay between bets to avoid detection
3. **Odds Validation**: Ensures odds haven't changed before placing bets
4. **Emergency Stop**: Instantly disable all automation
5. **Duplicate Detection**: Prevents placing duplicate bets

## API Endpoints

### Dashboard Stats
- `GET /api/dashboard/stats` - Get current dashboard statistics

### Bets
- `GET /api/bets/active` - List active bets
- `GET /api/bets/queue` - View bet queue

### Opportunities
- `GET /api/opportunities/current` - Get current opportunities

### Automation
- `POST /api/automation/toggle` - Enable/disable automation
- `GET/POST /api/settings` - Get/update settings

## WebSocket Events

- `new_bet` - Emitted when a new bet is placed
- `bet_settled` - Emitted when a bet is settled
- `new_opportunity` - Emitted when a new opportunity is found
- `performance_update` - Regular performance metric updates

## Troubleshooting

### Common Issues

1. **Connection errors**: Ensure all API credentials are correct
2. **No opportunities found**: Check market filters and minimum profit settings
3. **Bets not placing**: Verify account balance and betting limits

### Logs

Check logs in the `logs/` directory for detailed error information.

## Disclaimer

**IMPORTANT**: This tool is for educational purposes only. Online betting involves financial risk. Users are responsible for:
- Complying with local gambling laws
- Understanding the risks involved
- Using the tool responsibly
- Verifying all bets before placement

The authors are not responsible for any financial losses incurred through the use of this tool.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue on GitHub or contact support@example.com