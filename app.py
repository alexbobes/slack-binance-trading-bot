import os
from dotenv import load_dotenv
import json
from flask import Flask, render_template, request, jsonify
from binance.client import Client
import websocket
import threading
from datetime import datetime
from binance.exceptions import BinanceAPIException
import hmac
import hashlib
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import time
import threading
from threading import Thread

load_dotenv()

app = Flask(__name__)

listen_key = None

api_key = os.environ.get('BINANCE_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET')
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
SLACK_APP_TOKEN = os.environ.get('SLACK_APP_TOKEN')
SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL')

client = Client(api_key, api_secret)

latest_price = {}
user_open_orders = {}

tracked_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT']

@app.route('/')
def index():
    return render_template('index.html')

slack_app = App()
slack_client = WebClient(token=SLACK_BOT_TOKEN)

def send_slack_notification(channel, message):
    print(f"Sending notification to {channel}: {message}")  # Debugging
    try:
        response = slack_client.chat_postMessage(channel=channel, text=message)
        print(f"Notification sent successfully. Response: {response}")  # Debugging
    except SlackApiError as e:
        print(f"Error sending notification: {e}")
        
def send_price_updates():
    while True:
        for symbol in tracked_symbols:
            try:
                ticker_price = client.get_symbol_ticker(symbol=symbol)
                price = float(ticker_price['price'])
                print(f"Fetched price for {symbol}: {price}")  # Debugging
                send_slack_notification(SLACK_CHANNEL, f"{symbol}: {price}")
            except BinanceAPIException as e:
                print(f"Error fetching price for {symbol}: {str(e)}")
            except SlackApiError as e:
                print(f"Error sending notification for {symbol}: {e}")
        time.sleep(3600)  # Wait for an hour (3600 seconds)     

@app.route('/price', methods=['GET'])
def get_current_price():
    symbol = request.args.get('symbol')
    if not symbol:
        return {"error": "No symbol provided"}, 400

    try:
        ticker_price = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker_price['price'])
    except BinanceAPIException as e:
        return {"error": str(e)}, 400

    return {"price": price}

@app.route('/order', methods=['POST'])
def submit_order(symbol=None, side=None, price=None, quantity=None, command=None):
    if command:
        try:
            command_parts = command.split()
            if len(command_parts) != 4:
                raise ValueError("Invalid command format")
            side, symbol, price, quantity = command_parts
        except ValueError as e:
            return {"error": str(e)}, 400

    if not symbol or not side or not price or not quantity:
        return {"error": "Missing required fields"}, 400

    print(f"Submitting order: {side} {symbol} {price} {quantity}")  # Debugging

    try:
        order = client.create_order(
            symbol=symbol.upper(),
            side=side.upper(),
            type=Client.ORDER_TYPE_LIMIT,
            timeInForce=Client.TIME_IN_FORCE_GTC,
            quantity=quantity,
            price=price
        )
        print(f"Order submitted: {order}")  # Debugging
    except Exception as e:
        print(f"Error submitting order: {str(e)}")  # Debugging
        return {"error": str(e)}, 400

    if "error" not in order:
        send_slack_notification(SLACK_CHANNEL, f"Order submitted successfully: {side} {symbol} {price} {quantity}")

    return order

@app.route('/balances', methods=['GET'])
def get_balances():
    account_info = client.get_account()
    balances = account_info['balances']

    # Filter coins with a balance greater than 0
    coins_with_balance = [coin for coin in balances if float(coin['free']) > 0 or float(coin['locked']) > 0]

    return {"balances": coins_with_balance}

@app.route('/open_orders', methods=['GET'])
def get_open_orders():
    open_orders_list = [{"symbol": symbol, "orderId": order_id} for symbol, order_id in user_open_orders.items()]
    return {"open_orders": open_orders_list}


@app.route('/cancel_order', methods=['POST'])
def cancel_order():
    symbol = request.args.get('symbol')
    order_id = request.args.get('orderId')

    if not symbol or not order_id:
        return {"error": "Missing required fields"}, 400

    try:
        client.cancel_order(symbol=symbol, orderId=order_id)
    except Exception as e:
        return {"error": str(e)}, 400

    return {"result": "Order canceled successfully"}


def get_trades_for_symbol(symbol, start_time, end_time):
    trades = []
    time_step = 24 * 60 * 60 * 1000  # 24 hours in milliseconds

    for t in range(start_time, end_time, time_step):
        try:
            symbol_trades = client.get_my_trades(symbol=symbol, startTime=t, endTime=min(t + time_step, end_time))
            trades.extend(symbol_trades)
        except BinanceAPIException as e:
            if e.code == -2013:  # No trading history for the symbol
                break
            else:
                raise

    return trades

@app.route('/trade_command', methods=['POST'])
def trade_command():
    # e.g.: buy BTCUSDT 50000 0.1
    command = request.form.get('text')
    response_url = request.form.get('response_url')

    if not command:
        return {"error": "No command provided"}, 400

    order_result = submit_order(command=command)

    if "error" in order_result:
        payload = {
            "text": f"Error executing trade command: {order_result['error']}",
            "response_type": "ephemeral",
        }
    else:
        payload = {
            "text": f"Trade command executed: {command}",
            "response_type": "in_channel",
        }
    requests.post(response_url, json=payload)

    return jsonify({"response": "Trade command processed"}), 200

@slack_app.command("/crypto_trade")
def handle_trade(ack, respond, command):
    ack()
    try:
        order_result = submit_order(command=command['text'])
        if "error" in order_result:
            response_text = f"Error executing trade command: {order_result['error']}"
            response_type = "ephemeral"
        else:
            response_text = f"Trade command executed: {command['text']}"
            response_type = "in_channel"
    except Exception as e:
        response_text = f"Error: {str(e)}"
        response_type = "ephemeral"
    respond({"text": response_text, "response_type": response_type})


@slack_app.command("/crypto_price")
def handle_crypto_price(ack, respond, command):
    ack()
    symbol = command['text'].upper()
    
    if symbol not in tracked_symbols:
        response_text = f"Invalid symbol. Supported symbols are: {', '.join(tracked_symbols)}"
        response_type = "ephemeral"
    else:
        try:
            ticker_price = client.get_symbol_ticker(symbol=symbol)
            price = float(ticker_price['price'])
            response_text = f"Current price for {symbol}: {price}"
            response_type = "in_channel" 
        except BinanceAPIException as e:
            response_text = f"Error fetching price for {symbol}: {str(e)}"
            response_type = "ephemeral"

    respond({"text": response_text, "response_type": response_type})

@slack_app.command("/crypto_balance")
def handle_balances(ack, respond):
    ack()
    try:
        balances = get_balances()
        response_text = "Balances:\n" + "\n".join([f"{b['asset']}: {b['free']} (Free) | {b['locked']} (Locked)" for b in balances["balances"]])
        response_type = "in_channel" 
    except Exception as e:
        response_text = f"Error: {str(e)}"
        response_type = "ephemeral"
    respond({"text": response_text, "response_type": response_type})
    
@slack_app.command("/crypto_open_orders")
def handle_open_orders(ack, respond):
    ack()
    try:
        open_orders = get_open_orders()
        if open_orders["open_orders"]:
            response_text = "Open Orders:\n" + "\n".join([f"{o['symbol']}: Order ID {o['orderId']}" for o in open_orders["open_orders"]])
        else:
            response_text = "No open orders."
        response_type = "in_channel"  # Visible to everyone in the channel
    except Exception as e:
        response_text = f"Error: {str(e)}"
        response_type = "ephemeral"
    respond({"text": response_text, "response_type": response_type})

def start_user_data_stream():
    global listen_key
    listen_key = client.stream_get_listen_key()

def start_open_orders_websocket():
    def on_open(ws):
        timestamp = int(datetime.now().timestamp() * 1000)
        signature_payload = f"timestamp={timestamp}"
        signature = hmac.new(api_secret.encode(), signature_payload.encode(), hashlib.sha256).hexdigest()
        ws.send(json.dumps({"method": "SUBSCRIBE", "params": [listen_key["listenKey"]], "id": 1}))
        ws.send(json.dumps({"method": "SET_PROPERTY", "params": ["spot", "USER_API-KEY", api_key], "id": 2}))
        ws.send(json.dumps({"method": "SET_PROPERTY", "params": ["spot", "USER_API-SIGNATURE", signature], "id": 3}))

    def on_message(ws, message):
        global user_open_orders
        msg_json = json.loads(message)
        event_type = msg_json.get("e")

        if event_type == "executionReport":
            symbol = msg_json["s"]
            order_id = msg_json["i"]
            order_status = msg_json["X"]

            if order_status == "NEW" or order_status == "PARTIALLY_FILLED":
                user_open_orders[symbol] = order_id
            elif order_status == "CANCELED" or order_status == "FILLED":
                user_open_orders.pop(symbol, None)

    ws = websocket.WebSocketApp(
        "wss://stream.binance.com:9443/ws",
        on_open=on_open,
        on_message=on_message,
    )
    ws.run_forever()

start_user_data_stream()
t2 = threading.Thread(target=start_open_orders_websocket)
t2.start()

def run_app():
    app.run(debug=True)
    
if __name__ == '__main__':
    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    handler.start()  # Start the Socket Mode handler in a separate thread

    # Send a notification when the bot starts
    print("Bot starting")  # Debugging
    send_slack_notification(SLACK_CHANNEL, "Bot has started")

    # Start the price updates thread
    print("Starting price updates thread")  # Debugging
    price_updates_thread = threading.Thread(target=send_price_updates)
    price_updates_thread.start()

    # Start the Flask app in a separate thread
    print("Starting Flask app thread")  # Debugging
    app_thread = Thread(target=run_app)
    app_thread.start()
