# Binance Trading Bot for Slack

This repository contains a Binance trading bot integrated with Slack, allowing users to execute trades and retrieve information about their Binance 
account directly through Slack commands.

## Features

- Get real-time cryptocurrency price updates in Slack
- Execute trade commands (buy/sell) directly from Slack
- Check account balances
- View open orders
- Cancel orders
- Integration with Binance API

## Installation

1. Clone this repository: git clone https://github.com/yourusername/binance-trading-bot-for-slack.git
2. Install the required packages: pip install -r requirements.txt
3. Set up environment variables in a `.env` file in the project's root directory with the following keys:

- BINANCE_API_KEY
- BINANCE_API_SECRET
- SLACK_WEBHOOK_URL
- SLACK_BOT_TOKEN
- SLACK_APP_TOKEN
- SLACK_CHANNEL

4. Configure your Slack app with the following settings:

- Enable Socket Mode
- Add the following Slash Commands:
  - /crypto_trade
  - /crypto_price
- Add necessary OAuth Scopes (e.g., chat:write, commands)

5. Run the app: python app.py

## Usage

- Use the `/crypto_trade` command in Slack to execute trades, for example: /crypto_trade buy BTCUSDT 50000 0.1
- Use the `/crypto_price` command in Slack to check prices, for example: /crypto_price BNBUSDT
- Use the `/crypto_open_orders` command in Slack to check open orders
- Use the `/crypto_balance` command in Slack to check account balance
- The bot will also periodically send real-time price updates for tracked cryptocurrencies to the specified Slack channel.

## Contributing

If you'd like to contribute to this project, feel free to submit a pull request or open an issue to discuss your ideas.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Disclaimer

This project is for educational purposes only. Trading cryptocurrencies carries a risk of financial loss. Use this bot at your own risk, and always do your own research before executing trades. The authors of this project are not responsible for any financial losses incurred while using this bot.