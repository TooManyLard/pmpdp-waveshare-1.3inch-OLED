#!/bin/bash

echo "MPD Client for OLED HAT - Installation Script"
echo "=============================================="
echo ""

# 必要なパッケージのインストール
echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y python3-pip mpd mpc fonts-misaki

echo ""
echo "Installing Python packages..."
pip3 install --break-system-packages luma.oled luma.core gpiozero pillow python-mpd2

# スクリプトの配置
echo ""
echo "Installing MPD client script..."
sudo cp mpd_client.py /usr/local/bin/
sudo chmod +x /usr/local/bin/mpd_client.py

# systemdサービスの設定
echo ""
echo "Setting up systemd service..."
sudo cp mpd-client.service /etc/systemd/system/
sudo systemctl daemon-reload

# SPIの有効化確認
if [ ! -e /dev/spidev0.0 ]; then
    echo ""
    echo "WARNING: SPI is not enabled!"
    echo "Please enable SPI using: sudo raspi-config"
    echo "Interface Options > SPI > Enable"
    echo "Then reboot your Raspberry Pi."
fi

# MPDの状態確認
echo ""
echo "Checking MPD status..."
if systemctl is-active --quiet mpd; then
    echo "MPD is running."
else
    echo "MPD is not running. Starting MPD..."
    sudo systemctl start mpd
    sudo systemctl enable mpd
fi

# サービスの有効化
echo ""
read -p "Do you want to enable and start the MPD client service now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl enable mpd-client
    sudo systemctl start mpd-client
    echo "Service enabled and started."
    echo ""
    echo "You can check the status with: sudo systemctl status mpd-client"
else
    echo "Service not started. You can start it later with:"
    echo "  sudo systemctl enable mpd-client"
    echo "  sudo systemctl start mpd-client"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status mpd-client  - Check service status"
echo "  sudo systemctl restart mpd-client - Restart service"
echo "  sudo journalctl -u mpd-client -f  - View logs"
