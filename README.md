# Binance Algo Trading System

### Start Application
SSH Remote to VM
```shell script
cd ~/Downloads
sudo ssh -i ssh-key-2020-11-21.key opc@168.138.201.53
```
Start the application
```shell script
git clone https://github.com/elvisleung222/CryptoAlgoTrading.git
cd CryptoAlgoTrading

sudo pip install -r requirements.txt
# OR
sudo pip3 install -r requirements.txt

sudo nohup python3 algo.py --data-stream=false --stream-print=false --schedule-task=false &
tail -f nohup.txt
```

### Reference
- Paper Trading System: https://testnet.binance.vision/
- Setup Guide: https://algotrading101.com/learn/binance-python-api-guide/
- API Docs: https://python-binance.readthedocs.io/