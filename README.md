# MPD クライアント for Raspberry Pi Zero OLED HAT

Raspberry Pi Zero用OLEDディスプレイHATを使用したMPD（Music Player Daemon）クライアントです。

## 必要なパッケージ

```bash
# システムパッケージ
sudo apt-get update
sudo apt-get install -y python3-pip mpd mpc fonts-misaki

# Pythonパッケージ
pip3 install --break-system-packages luma.oled luma.core gpiozero pillow python-mpd2
```

## MPDの設定

1. MPDの設定ファイルを編集:
```bash
sudo nano /etc/mpd.conf
```

2. 以下の設定を確認/変更:
```
music_directory     "/home/pi/Music"
bind_to_address     "localhost"
port                "6600"
```

3. MPDを再起動:
```bash
sudo systemctl restart mpd
```

## インストール

1. スクリプトを配置:
```bash
sudo cp mpd_client.py /usr/local/bin/
sudo chmod +x /usr/local/bin/mpd_client.py
```

2. systemdサービスを設定:
```bash
sudo cp mpd-client.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mpd-client
sudo systemctl start mpd-client
```

## 使い方

### 基本操作
- **ジョイスティック**: カーソル移動、選択
- **ジョイスティック押し込み**: 決定
- **BTN1**: 再生中画面・再生キュー切り替え（他の画面では再生中画面へ移動）
- **BTN2**: 戻る
- **BTN3**: メインメニュー

### 再生中画面
- **上下**: ボリューム調整
- **左右**: 前の曲/次の曲
- **決定**: 再生/一時停止

### 再生キュー
- 先頭にシャッフル/リピート設定表示
- 再生中のトラックには「> 」が表示されます
- 決定でメニュー表示（移動、今すぐ再生、削除）

### ライブラリ
- ディレクトリ: `> `
- プレイリスト: `# `
- 音楽ファイル: `@ `

選択して決定すると、キューに追加して再生されます。

### メインメニュー
- 再生中
- 再生キュー
- ライブラリ
- システム

### システム
- シャットダウン
- 再起動

## トラブルシューティング

### ディスプレイが表示されない
```bash
# SPIが有効か確認
ls /dev/spidev*

# 有効化されていない場合
sudo raspi-config
# Interface Options > SPI > Enable
```

### MPDに接続できない
```bash
# MPDの状態確認
sudo systemctl status mpd

# MPDを再起動
sudo systemctl restart mpd

# 手動で接続テスト
mpc status
```

### フォントが正しく表示されない
```bash
# 美咲フォントがインストールされているか確認
ls /usr/share/fonts/truetype/misaki/

# インストールされていない場合
sudo apt-get install fonts-misaki
```

## ライセンス

このプロジェクトは元のOLED HATテストコードを基に作成されています。
