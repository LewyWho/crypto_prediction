import sys
import json
import time
import hashlib
import requests
import numpy as np
import lightgbm as lgb
import threading
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QTextEdit, QSpinBox
)
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, QThread
from pybit.unified_trading import HTTP

model = lgb.Booster(model_file="best_btc_model (2).txt")

SIMULATION_BALANCE = 100000
STOP_LOSS_PERCENTAGE = 5
simulation_active = False
simulation_trades = []
simulation_balance = SIMULATION_BALANCE

def load_settings():
    try:
        with open("settings.json", "r") as f:
            settings = json.load(f)
        return settings
    except FileNotFoundError:
        return None

def save_settings(api_key, api_secret):
    settings = {
        "api_key": api_key,
        "api_secret": api_secret
    }
    with open("settings.json", "w") as f:
        json.dump(settings, f)

def get_current_btc_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data["bitcoin"]["usd"]

def get_prediction_from_model():
    try:
        import get_string_prediction
        features_string = get_string_prediction.collect_features_string_from_json()
        print(features_string)
        features = [float(x.strip()) for x in features_string.split(',')]
        input_array = np.array(features, dtype=np.float32).reshape(1, -1)
        prediction = model.predict(input_array)[0]
        return prediction
    except Exception as e:
        print(f"Ошибка при получении предсказания: {e}")
        return None

def calc_signal_strength(current_price, prediction):
    return (prediction - current_price) / current_price

def get_best_trades(current_price, prediction, model_confidence):
    trades = []
    signal_strength = calc_signal_strength(current_price, prediction)
    direction = "Long" if signal_strength > 0 else "Short"
    signal_strength = abs(signal_strength) * model_confidence

    trade_levels = [
        {"threshold": 0.01, "returns": [2, 4], "multipliers": [1.02, 1.04], "timeframes": ["15m", "30m"]},
        {"threshold": 0.005, "returns": [1, 2], "multipliers": [1.01, 1.02], "timeframes": ["5m", "15m"]},
        {"threshold": 0.002, "returns": [0.5, 1], "multipliers": [1.005, 1.01], "timeframes": ["1m", "5m"]},
    ]

    for level in trade_levels:
        if signal_strength >= level["threshold"]:
            for i in range(2):
                multiplier = level["multipliers"][i]
                if direction == "Short":
                    multiplier = 1 - (multiplier - 1)
                trade = {
                    "side": direction,
                    "target_price": current_price * multiplier,
                    "expected_return": level["returns"][i],
                    "timeframe": level["timeframes"][i]
                }
                trades.append(trade)
            

    return sorted(trades, key=lambda x: x["expected_return"], reverse=True)

def authorize_bybit(api_key, api_secret):
    try:
        session = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)
        response = session.get_wallet_balance(accountType="UNIFIED")
        return response["retCode"] == 0
    except Exception as e:
        print("Ошибка авторизации:", e)
        return False

def get_balance(session):
    try:
        response = session.get_wallet_balance(accountType="UNIFIED")
        print("Ответ от API:", response)
        if response["retCode"] == 0:
            result = response["result"]["list"][0]
            
            coins = result.get("coin", [])
            if not coins:
                print("Баланс монет не найден в ответе.")
                return 0.0, 0.0
            
            usdt_balance = 0.0
            btc_balance = 0.0

            for coin in coins:
                if coin["coin"] == "USDT":
                    usdt_balance = float(coin.get("available", 0.0))
                elif coin["coin"] == "BTC":
                    btc_balance = float(coin.get("available", 0.0))

            return btc_balance, usdt_balance
        else:
            print(f"Ошибка получения баланса: {response['retMsg']}")
            return 0.0, 0.0
    except Exception as e:
        print(f"Ошибка получения баланса: {e}")
        return 0.0, 0.0

def place_order(session, side, qty, symbol="BTCUSDT"):
    try:
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=qty,
            timeInForce="GTC"
        )
        print(f"{side} ордер размещён: {order}")
        return order
    except Exception as e:
        print(f"Ошибка размещения {side} ордера:", e)
        return None

def log_trade(text):
    with open("trading_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {text}\n")

def log_simulation(text):
    with open("simulation_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {text}\n")

class SimulationWorker(QObject):
    update_text = pyqtSignal(str)
    update_balance = pyqtSignal(float)
    
    def __init__(self, leverage, current_price):
        super().__init__()
        self.leverage = leverage
        self.current_price = current_price
        self.simulation_active = True
        
    def run(self):
        global simulation_balance
        simulation_balance = SIMULATION_BALANCE

        while self.simulation_active:
            try:
                self.current_price = get_current_btc_price()
                prediction = get_prediction_from_model()
                if prediction is None:
                    time.sleep(5)
                    continue
                    
                model_confidence = 0.5
                best_trades = get_best_trades(self.current_price, prediction, model_confidence)
                
                if not best_trades:
                    time.sleep(5)
                    continue

                trade = best_trades[0]
                trade_amount = simulation_balance * 0.1
                qty = round((trade_amount * self.leverage) / self.current_price, 4)
                
                entry_price = self.current_price
                side = trade["side"]
                target_price = trade["target_price"]
                timeframe = trade["timeframe"]

                stop_loss_price = entry_price * (1 + STOP_LOSS_PERCENTAGE/100) if side == "Short" else entry_price * (1 - STOP_LOSS_PERCENTAGE/100)

                timeframe_minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}[timeframe]
                close_time = datetime.now() + timedelta(minutes=timeframe_minutes)
                
                entry_msg = (
                    f"[СИМУЛЯЦИЯ] Открыта позиция: {side} {qty} BTC по ${entry_price:.2f}\n"
                    f"Время закрытия: {close_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Целевая цена: ${target_price:.2f}\n"
                    f"Stop Loss: ${stop_loss_price:.2f}"
                )
                self.update_text.emit(entry_msg)
                log_simulation(entry_msg)

                start_time = datetime.now()
                while datetime.now() < close_time and self.simulation_active:
                    current_price = get_current_btc_price()
                    
                    if (side == "Long" and current_price <= stop_loss_price) or \
                       (side == "Short" and current_price >= stop_loss_price):
                        close_price = current_price
                        close_reason = "Stop Loss"
                        break
                    
                    if (side == "Long" and current_price >= target_price) or \
                       (side == "Short" and current_price <= target_price):
                        close_price = current_price
                        close_reason = "Целевая цена достигнута"
                        break
                    
                    time.sleep(3)
                else:
                    close_price = get_current_btc_price()
                    close_reason = "Время истекло"
                
                if side == "Long":
                    pnl = (close_price - entry_price) / entry_price * 100 * self.leverage
                else:
                    pnl = (entry_price - close_price) / entry_price * 100 * self.leverage

                pnl_amount = trade_amount * (pnl / 100)
                simulation_balance += pnl_amount

                result_msg = (
                    f"[СИМУЛЯЦИЯ] Закрыта позиция ({close_reason}): {side}\n"
                    f"Цена входа: ${entry_price:.2f}\n"
                    f"Цена выхода: ${close_price:.2f}\n"
                    f"PnL: {pnl:.2f}%\n"
                    f"Баланс: ${simulation_balance:.2f}"
                )
                self.update_text.emit(result_msg)
                self.update_balance.emit(simulation_balance)
                log_simulation(result_msg)

            except Exception as e:
                error_msg = f"[СИМУЛЯЦИЯ] Ошибка: {e}"
                self.update_text.emit(error_msg)
                log_simulation(error_msg)
                time.sleep(5)

    def stop(self):
        self.simulation_active = False

class TradingWorker(QObject):
    update_text = pyqtSignal(str)
    
    def __init__(self, api_key, api_secret, leverage, current_price):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.leverage = leverage
        self.current_price = current_price
        self.trading_active = True
        
    def run(self):
        session = HTTP(testnet=True, api_key=self.api_key, api_secret=self.api_secret)

        while self.trading_active:
            try:
                self.current_price = get_current_btc_price()
                prediction = get_prediction_from_model()
                if prediction is None:
                    time.sleep(5)
                    continue
                    
                model_confidence = 0.5
                best_trades = get_best_trades(self.current_price, prediction, model_confidence)
                if not best_trades:
                    time.sleep(5)
                    continue

                btc_balance, usdt_balance = get_balance(session)
                trade_amount = usdt_balance * 0.1
                qty = round((trade_amount * self.leverage) / self.current_price, 4)

                trade = best_trades[0]
                side = "Buy" if trade["side"] == "Long" else "Sell"
                target_price = trade["target_price"]
                timeframe = trade["timeframe"]
                
                stop_loss_price = self.current_price * (1 + STOP_LOSS_PERCENTAGE/100) if side == "Sell" else self.current_price * (1 - STOP_LOSS_PERCENTAGE/100)

                timeframe_minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}[timeframe]
                close_time = datetime.now() + timedelta(minutes=timeframe_minutes)

                session.set_leverage(
                    category="linear",
                    symbol="BTCUSDT",
                    buyLeverage=self.leverage,
                    sellLeverage=self.leverage
                )
                order = place_order(session, side, qty)

                msg = (
                    f"{side} на {qty} BTC с плечом {self.leverage} по ${self.current_price:.2f}\n"
                    f"Время закрытия: {close_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Целевая цена: ${target_price:.2f}\n"
                    f"Stop Loss: ${stop_loss_price:.2f}"
                )
                self.update_text.emit(msg)
                log_trade(msg)

                time.sleep(60)
            except Exception as e:
                error_msg = f"Ошибка в трейдинге: {e}"
                self.update_text.emit(error_msg)
                log_trade(error_msg)
                time.sleep(5)

    def stop(self):
        self.trading_active = False

class TradingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Trader")
        self.setFixedSize(600, 600)
        self.settings = load_settings()
        self.simulation_thread = None
        self.trading_thread = None
        self.simulation_worker = None
        self.trading_worker = None
        self.session = None
        self.btc_balance_label = QLabel("Баланс BTC: 0")
        self.usdt_balance_label = QLabel("Баланс USDT: 0")
        self.simulation_balance_label = QLabel(f"Баланс симуляции: ${SIMULATION_BALANCE:,.2f}")
        try:
            self.current_price = get_current_btc_price()
        except Exception as e:
            self.current_price = 0.0
            print(f"Ошибка при получении текущей цены BTC: {e}")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        price_layout = QHBoxLayout()
        self.price_label = QLabel(f"Текущая цена BTC: ${self.current_price:.2f}")
        self.price_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.refresh_price_btn = QPushButton("Обновить цену")
        self.refresh_price_btn.clicked.connect(self.update_price)
        price_layout.addWidget(self.price_label)
        price_layout.addWidget(self.refresh_price_btn)
        layout.addLayout(price_layout)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Введите API Key")
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setPlaceholderText("Введите API Secret")
        self.api_secret_input.setEchoMode(QLineEdit.EchoMode.Password)

        if self.settings:
            self.api_key_input.setText(self.settings.get("api_key", ""))
            self.api_secret_input.setText(self.settings.get("api_secret", ""))

        layout.addWidget(QLabel("API Key:"))
        layout.addWidget(self.api_key_input)
        layout.addWidget(QLabel("API Secret:"))
        layout.addWidget(self.api_secret_input)

        btn_layout = QHBoxLayout()
        self.save_button = QPushButton("Сохранить настройки")
        self.save_button.clicked.connect(self.save_settings)
        self.auth_button = QPushButton("Авторизоваться")
        self.auth_button.clicked.connect(self.authorize)
        btn_layout.addWidget(self.save_button)
        btn_layout.addWidget(self.auth_button)
        layout.addLayout(btn_layout)

        self.auth_status_label = QLabel("")
        layout.addWidget(self.auth_status_label)

        self.predict_button = QPushButton("Сделать прогноз")
        self.predict_button.clicked.connect(self.make_prediction)
        layout.addWidget(self.predict_button)

        layout.addWidget(QLabel("Плечо (Leverage):"))
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 125)
        self.leverage_spin.setValue(10)
        layout.addWidget(self.leverage_spin)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(QLabel("Лучшие сделки / Лог:"))
        layout.addWidget(self.results_text)

        sim_btn_layout = QHBoxLayout()
        self.start_sim_btn = QPushButton("Запустить симуляцию")
        self.start_sim_btn.clicked.connect(self.start_simulation)
        self.stop_sim_btn = QPushButton("Остановить симуляцию")
        self.stop_sim_btn.clicked.connect(self.stop_simulation)
        self.stop_sim_btn.setEnabled(False)
        sim_btn_layout.addWidget(self.start_sim_btn)
        sim_btn_layout.addWidget(self.stop_sim_btn)
        layout.addLayout(sim_btn_layout)

        self.simulation_balance_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.simulation_balance_label)

        trade_btn_layout = QHBoxLayout()
        self.start_trade_btn = QPushButton("Начать торговлю")
        self.start_trade_btn.clicked.connect(self.start_trading)
        self.stop_trade_btn = QPushButton("Остановить торговлю")
        self.stop_trade_btn.clicked.connect(self.stop_trading)
        self.stop_trade_btn.setEnabled(False)
        trade_btn_layout.addWidget(self.start_trade_btn)
        trade_btn_layout.addWidget(self.stop_trade_btn)
        layout.addLayout(trade_btn_layout)

        layout.addWidget(self.btc_balance_label)
        layout.addWidget(self.usdt_balance_label)

        self.setLayout(layout)

    def update_price(self):
        try:
            self.current_price = get_current_btc_price()
            self.price_label.setText(f"Текущая цена BTC: ${self.current_price:.2f}")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось обновить цену: {e}")

    def save_settings(self):
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        if not api_key or not api_secret:
            QMessageBox.warning(self, "Ошибка", "API Key и Secret не могут быть пустыми")
            return
        save_settings(api_key, api_secret)
        QMessageBox.information(self, "Успех", "Настройки сохранены")

    def authorize(self):
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        if authorize_bybit(api_key, api_secret):
            self.auth_status_label.setText("Авторизация успешна")
        else:
            self.auth_status_label.setText("Ошибка авторизации")

    def make_prediction(self):
        prediction = get_prediction_from_model()
        if prediction is not None:
            self.results_text.append(f"Прогноз цены BTC: ${prediction:.2f}")
            best_trades = get_best_trades(self.current_price, prediction, 0.5)
            if best_trades:
                self.results_text.append("Лучшие сделки:")
                for trade in best_trades:
                    self.results_text.append(f"{trade['side']} до ${trade['target_price']:.2f} за {trade['timeframe']}")
            else:
                self.results_text.append("Нет подходящих сделок.")
        else:
            self.results_text.append("Не удалось получить прогноз.")

    def start_simulation(self):
        if self.simulation_worker is not None:
            return
        leverage = self.leverage_spin.value()
        self.simulation_worker = SimulationWorker(leverage, self.current_price)
        self.simulation_thread = QThread()
        self.simulation_worker.moveToThread(self.simulation_thread)
        self.simulation_thread.started.connect(self.simulation_worker.run)
        self.simulation_worker.update_text.connect(self.append_text)
        self.simulation_worker.update_balance.connect(self.update_simulation_balance)
        self.simulation_thread.start()
        self.start_sim_btn.setEnabled(False)
        self.stop_sim_btn.setEnabled(True)

    def stop_simulation(self):
        if self.simulation_worker:
            self.simulation_worker.stop()
            self.simulation_thread.quit()
            self.simulation_thread.wait()
            self.simulation_worker = None
            self.simulation_thread = None
        self.start_sim_btn.setEnabled(True)
        self.stop_sim_btn.setEnabled(False)

    def start_trading(self):
        if self.trading_worker is not None:
            return
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        if not api_key or not api_secret:
            QMessageBox.warning(self, "Ошибка", "Введите API ключ и секрет для торговли")
            return
        leverage = self.leverage_spin.value()
        self.trading_worker = TradingWorker(api_key, api_secret, leverage, self.current_price)
        self.trading_thread = QThread()
        self.trading_worker.moveToThread(self.trading_thread)
        self.trading_thread.started.connect(self.trading_worker.run)
        self.trading_worker.update_text.connect(self.append_text)
        self.trading_thread.start()
        self.start_trade_btn.setEnabled(False)
        self.stop_trade_btn.setEnabled(True)

    def stop_trading(self):
        if self.trading_worker:
            self.trading_worker.stop()
            self.trading_thread.quit()
            self.trading_thread.wait()
            self.trading_worker = None
            self.trading_thread = None
        self.start_trade_btn.setEnabled(True)
        self.stop_trade_btn.setEnabled(False)

    def append_text(self, text):
        self.results_text.append(text)

    def update_simulation_balance(self, balance):
        self.simulation_balance_label.setText(f"Баланс симуляции: ${balance:,.2f}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingApp()
    window.show()
    sys.exit(app.exec())