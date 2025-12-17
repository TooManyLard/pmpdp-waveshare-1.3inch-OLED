# -*- coding:utf-8 -*-

from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import sh1106
from gpiozero import Button
from mpd import MPDClient

import time
import subprocess
import os
import threading

from PIL import Image, ImageDraw, ImageFont

# GPIO定義
RST_PIN = 25  # Reset
CS_PIN = 8
DC_PIN = 24
JS_U_PIN = 6   # Joystick Up
JS_D_PIN = 19  # Joystick Down
JS_L_PIN = 5   # Joystick Left
JS_R_PIN = 26  # Joystick Right
JS_P_PIN = 13  # Joystick Pressed
BTN1_PIN = 21
BTN2_PIN = 20
BTN3_PIN = 16

# 定数
SCREEN_SAVER = 300.0  # 5分でスクリーンセーバー
width = 128
height = 64

# 画面状態
STATE_OFF = 0
STATE_PLAYING = 1
STATE_QUEUE = 2
STATE_MAIN_MENU = 3
STATE_LIBRARY = 4
STATE_SYSTEM = 5
STATE_QUEUE_MENU = 6

# MPDクライアント初期化
mpd_client = MPDClient()
mpd_connected = False

def connect_mpd():
    global mpd_client, mpd_connected
    try:
        if not mpd_connected:
            mpd_client.connect("localhost", 6600)
            mpd_connected = True
    except:
        mpd_connected = False

def disconnect_mpd():
    global mpd_client, mpd_connected
    try:
        if mpd_connected:
            mpd_client.close()
            mpd_client.disconnect()
            mpd_connected = False
    except:
        pass

# フォント読み込み
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/misaki/misaki_gothic.ttf", 8)
    font_16 = ImageFont.truetype("/usr/share/fonts/truetype/misaki/misaki_gothic.ttf", 16)
except:
    font = ImageFont.load_default()
    font_16 = ImageFont.load_default()

# ディスプレイ初期化
serial = spi(device=0, port=0, bus_speed_hz=8000000, transfer_size=4096, gpio_DC=DC_PIN, gpio_RST=RST_PIN)
device = sh1106(serial, rotate=2)

# グローバル変数
state = STATE_OFF
start = time.time()
last_press_time = {}
DEBOUNCE_TIME = 0.2

# 再生画面用変数
scroll_offset = 0
scroll_direction = 1
last_song = None

# メニュー用変数
menu_cursor = 0
menu_items = []
menu_scroll = 0

# ライブラリ用変数
library_path = []
library_items = []
library_cursor = 0
library_scroll = 0

# 再生キュー用変数
queue_items = []
queue_cursor = -2  # -2: リピート行, -1: シャッフル行, 0~: キュー項目
queue_scroll = 0
queue_menu_cursor = 0

def debounce(pin):
    """デバウンス処理"""
    current_time = time.time()
    if pin in last_press_time:
        if current_time - last_press_time[pin] < DEBOUNCE_TIME:
            return False
    last_press_time[pin] = current_time
    return True

def format_time(seconds):
    """秒をMM:SS形式に変換"""
    try:
        seconds = int(float(seconds))
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"
    except:
        return "00:00"

def calc_text_width(text):
    """テキストの幅をピクセル単位で計算（全角8px、半角4px）"""
    width = 0
    for char in text:
        # ASCII文字（半角）は4px、それ以外（全角）は8px
        if ord(char) < 128:
            width += 4
        else:
            width += 8
    return width

def draw_playing_screen(draw):
    """再生中画面を描画"""
    global scroll_offset, scroll_direction, last_song

    try:
        connect_mpd()
        status = mpd_client.status()
        current = mpd_client.currentsong()

        # 曲情報取得
        title = current.get('title', 'Unknown')
        artist = current.get('artist', 'Unknown Artist')
        album = current.get('album', 'Unknown Album')
        track = current.get('track', '')

        # 曲が変わったらスクロールリセット
        if current != last_song:
            scroll_offset = 0
            scroll_direction = 1
            last_song = current.copy()

        # タイトル行（16pxフォント）
        y_pos = 0
        # 実際のフォント幅を取得
        bbox = font_16.getbbox(title)
        title_width = bbox[2] - bbox[0]

        if title_width > 128 and status['state'] == 'play':
            # バウンススクロール（実際の文字幅ベース）
            max_scroll = title_width - 128
            if scroll_offset >= max_scroll:
                scroll_direction = -1
            elif scroll_offset <= 0:
                scroll_direction = 1
            scroll_offset += scroll_direction * 2

            # スクロール表示
            img = Image.new('1', (title_width, 16))
            draw_temp = ImageDraw.Draw(img)
            draw_temp.text((0, 0), title, font=font_16, fill=255)
            draw.bitmap((0 - scroll_offset, y_pos), img)
        else:
            draw.text((0, y_pos), title, font=font_16, fill=255)

        # アルバム名 - トラック番号（8px下にシフト）
        y_pos = 16
        album_track = album
        if track:
            album_track += f" - {track}"
        draw.text((0, y_pos), album_track, font=font, fill=255)

        # アーティスト名（更に8px下にシフト）
        y_pos = 24
        draw.text((0, y_pos), artist, font=font, fill=255)

        # 16px空ける
        y_pos += 16

        # 再生進捗とトラックの長さ（4px空けて）
        elapsed = float(status.get('elapsed', 0))
        duration = float(current.get('duration', 0))

        elapsed_str = format_time(elapsed)
        duration_str = format_time(duration)

        # 左端に再生進捗
        draw.text((0, y_pos), elapsed_str, font=font, fill=255)
        # 右端にトラックの長さ（108pxから開始、5文字 = 40px）
        draw.text((108, y_pos), duration_str, font=font, fill=255)

        # 4px空けて進捗バー
        y_pos += 12
        bar_width = 128
        bar_height = 3

        if duration > 0:
            progress = int((elapsed / duration) * bar_width)
            draw.rectangle((0, y_pos, bar_width - 1, y_pos + bar_height - 1), outline=255, fill=0)
            draw.rectangle((0, y_pos, progress, y_pos + bar_height - 1), outline=255, fill=255)

        # ボリュームとローカルタイム
        y_pos += 4
        volume = status.get('volume', '0')
        vol_text = f"Vol:{volume}%"

        # 現在時刻取得
        import datetime
        local_time = datetime.datetime.now().strftime("%H:%M:%S")

        # 左にボリューム
        draw.text((0, y_pos), vol_text, font=font, fill=255)
        # 右に時刻（右寄せ：128 - 32 = 96pxから開始）
        draw.text((96, y_pos), local_time, font=font, fill=255)

    except Exception as e:
        draw.text((0, 0), "MPD接続エラー", font=font, fill=255)
        draw.text((0, 8), str(e), font=font, fill=255)

def draw_queue_screen(draw):
    """再生キュー画面を描画"""
    global queue_items, queue_cursor, queue_scroll
    
    try:
        connect_mpd()
        status = mpd_client.status()
        playlist = mpd_client.playlistinfo()
        
        queue_items = playlist
        
        # ヘッダー行1: リピート設定
        y_pos = 0
        repeat_mode = "オフ"
        if status.get('repeat', '0') == '1':
            if status.get('single', '0') == '1':
                repeat_mode = "トラック"
            else:
                repeat_mode = "全体"
        repeat_text = f"リピート[{repeat_mode}]"
        
        # カーソルが-2の場合（リピート行）
        if queue_cursor == -2:
            draw.rectangle((0, y_pos, 127, y_pos + 7), outline=255, fill=255)
            draw.text((0, y_pos), repeat_text, font=font, fill=0)
        else:
            draw.text((0, y_pos), repeat_text, font=font, fill=255)
        y_pos += 8
        
        # ヘッダー行2: シャッフル設定
        shuffle_text = "シャッフル[ON]" if status.get('random', '0') == '1' else "シャッフル[OFF]"
        
        # カーソルが-1の場合（シャッフル行）
        if queue_cursor == -1:
            draw.rectangle((0, y_pos, 127, y_pos + 7), outline=255, fill=255)
            draw.text((0, y_pos), shuffle_text, font=font, fill=0)
        else:
            draw.text((0, y_pos), shuffle_text, font=font, fill=255)
        y_pos += 8
        
        # キュー表示
        current_song_id = status.get('songid', '')
        visible_lines = 5  # ヘッダー2行分減らす
        
        if len(queue_items) > 0:
            # スクロール調整（カーソルが0以上の場合のみ）
            if queue_cursor >= 0:
                if queue_cursor < queue_scroll:
                    queue_scroll = queue_cursor
                if queue_cursor >= queue_scroll + visible_lines:
                    queue_scroll = queue_cursor - visible_lines + 1
            
            for i in range(visible_lines):
                idx = queue_scroll + i
                if idx >= len(queue_items):
                    break
                
                item = queue_items[idx]
                title = item.get('title', 'Unknown')
                
                # 再生中のトラックに"> "を追加
                prefix = "> " if item.get('id') == current_song_id else "  "
                line_text = prefix + title
                
                # カーソル位置は反転表示
                if idx == queue_cursor:
                    draw.rectangle((0, y_pos, 124, y_pos + 7), outline=255, fill=255)
                    draw.text((0, y_pos), line_text, font=font, fill=0)
                else:
                    draw.text((0, y_pos), line_text, font=font, fill=255)
                
                y_pos += 8
            
            # スクロールバー
            if len(queue_items) > visible_lines:
                bar_height = 40  # ヘッダー2行分減らす
                thumb_height = max(3, int((visible_lines / len(queue_items)) * bar_height))
                thumb_pos = int((queue_scroll / (len(queue_items) - visible_lines)) * (bar_height - thumb_height))
                
                draw.rectangle((125, 16, 127, 56), outline=255, fill=0)
                draw.rectangle((125, 16 + thumb_pos, 127, 16 + thumb_pos + thumb_height), outline=255, fill=255)
        else:
            draw.text((0, y_pos), "キューは空です", font=font, fill=255)
    
    except Exception as e:
        draw.text((0, 0), "MPD接続エラー", font=font, fill=255)

def draw_main_menu(draw):
    """メインメニューを描画"""
    global menu_cursor, menu_items
    
    menu_items = ["再生中", "再生キュー", "ライブラリ", "システム"]
    
    y_pos = 8
    for i, item in enumerate(menu_items):
        if i == menu_cursor:
            draw.rectangle((0, y_pos, 127, y_pos + 7), outline=255, fill=255)
            draw.text((0, y_pos), item, font=font, fill=0)
        else:
            draw.text((0, y_pos), item, font=font, fill=255)
        y_pos += 8

def draw_library_screen(draw):
    """ライブラリ画面を描画"""
    global library_items, library_cursor, library_scroll
    
    try:
        connect_mpd()
        
        # パス表示
        y_pos = 0
        path_text = "[ライブラリ]/" + "/".join(library_path) if library_path else "[ライブラリ]/"
        draw.text((0, y_pos), path_text, font=font, fill=255)
        y_pos += 8
        
        # アイテム取得
        current_path = "/".join(library_path) if library_path else ""
        items = mpd_client.lsinfo(current_path)
        
        library_items = []
        
        # 親ディレクトリへ戻る項目
        if library_path:
            library_items.append({"type": "parent", "name": ".."})
        
        # ディレクトリ
        for item in items:
            if 'directory' in item:
                library_items.append({"type": "directory", "name": os.path.basename(item['directory']), "path": item['directory']})
        
        # プレイリスト
        for item in items:
            if 'playlist' in item:
                library_items.append({"type": "playlist", "name": item['playlist'], "path": item['playlist']})
        
        # ファイル
        for item in items:
            if 'file' in item:
                title = item.get('title', os.path.basename(item['file']))
                library_items.append({"type": "file", "name": title, "path": item['file']})
        
        # リスト表示
        visible_lines = 6
        
        if len(library_items) > 0:
            # スクロール調整
            if library_cursor < library_scroll:
                library_scroll = library_cursor
            if library_cursor >= library_scroll + visible_lines:
                library_scroll = library_cursor - visible_lines + 1
            
            for i in range(visible_lines):
                idx = library_scroll + i
                if idx >= len(library_items):
                    break
                
                item = library_items[idx]
                
                # アイコン
                icon = ""
                if item['type'] == 'directory' or item['type'] == 'parent':
                    icon = "> "
                elif item['type'] == 'playlist':
                    icon = "# "
                elif item['type'] == 'file':
                    icon = "@ "
                
                line_text = icon + item['name']
                
                # カーソル位置は反転表示
                if idx == library_cursor:
                    draw.rectangle((0, y_pos, 124, y_pos + 7), outline=255, fill=255)
                    draw.text((0, y_pos), line_text, font=font, fill=0)
                else:
                    draw.text((0, y_pos), line_text, font=font, fill=255)
                
                y_pos += 8
            
            # スクロールバー
            if len(library_items) > visible_lines:
                bar_height = 48
                thumb_height = max(3, int((visible_lines / len(library_items)) * bar_height))
                thumb_pos = int((library_scroll / (len(library_items) - visible_lines)) * (bar_height - thumb_height))
                
                draw.rectangle((125, 8, 127, 56), outline=255, fill=0)
                draw.rectangle((125, 8 + thumb_pos, 127, 8 + thumb_pos + thumb_height), outline=255, fill=255)
        else:
            draw.text((0, y_pos), "項目がありません", font=font, fill=255)
    
    except Exception as e:
        draw.text((0, 0), "MPD接続エラー", font=font, fill=255)
        draw.text((0, 8), str(e), font=font, fill=255)

def draw_system_menu(draw):
    """システムメニューを描画"""
    global menu_cursor
    
    menu_items = ["シャットダウン", "再起動"]
    
    y_pos = 8
    for i, item in enumerate(menu_items):
        if i == menu_cursor:
            draw.rectangle((0, y_pos, 127, y_pos + 7), outline=255, fill=255)
            draw.text((0, y_pos), item, font=font, fill=0)
        else:
            draw.text((0, y_pos), item, font=font, fill=255)
        y_pos += 8

def draw_queue_menu(draw):
    """再生キューメニューを描画（オーバーレイ）"""
    global queue_menu_cursor
    
    menu_items = ["移動", "今すぐ再生", "削除"]
    
    # 中央にメニューを表示
    menu_width = 80
    menu_height = len(menu_items) * 8 + 8
    menu_x = (128 - menu_width) // 2
    menu_y = (64 - menu_height) // 2
    
    # 背景
    draw.rectangle((menu_x, menu_y, menu_x + menu_width, menu_y + menu_height), outline=255, fill=0)
    draw.rectangle((menu_x + 1, menu_y + 1, menu_x + menu_width - 1, menu_y + menu_height - 1), outline=255, fill=0)
    
    # メニュー項目
    y_pos = menu_y + 4
    for i, item in enumerate(menu_items):
        if i == queue_menu_cursor:
            draw.rectangle((menu_x + 4, y_pos, menu_x + menu_width - 4, y_pos + 7), outline=255, fill=255)
            draw.text((menu_x + 6, y_pos), item, font=font, fill=0)
        else:
            draw.text((menu_x + 6, y_pos), item, font=font, fill=255)
        y_pos += 8

def draw_screen():
    """画面を描画"""
    global state, start

    with canvas(device) as draw:
        if state == STATE_OFF:
            # 空白画面を描画（OLED保護のため完全に消さない）
            pass
        elif state == STATE_PLAYING:
            draw_playing_screen(draw)
        elif state == STATE_QUEUE:
            draw_queue_screen(draw)
        elif state == STATE_MAIN_MENU:
            draw.text((0, 0), "[メインメニュー]", font=font, fill=255)
            draw_main_menu(draw)
        elif state == STATE_LIBRARY:
            draw_library_screen(draw)
        elif state == STATE_SYSTEM:
            draw.text((0, 0), "[システム]", font=font, fill=255)
            draw_system_menu(draw)
        elif state == STATE_QUEUE_MENU:
            draw_queue_screen(draw)
            draw_queue_menu(draw)

# ボタンハンドラ
def btn1_pressed():
    """BTN1: 再生中画面・再生キュー切り替え"""
    global state, menu_cursor, queue_cursor, start
    
    if not debounce(BTN1_PIN):
        return
    
    start = time.time()
    
    # スクリーンセーバーから復帰
    if state == STATE_OFF:
        state = STATE_PLAYING
        return
    
    if state == STATE_PLAYING:
        state = STATE_QUEUE
        queue_cursor = -2  # カーソルをリピート行に初期化
    elif state == STATE_QUEUE:
        state = STATE_PLAYING
    else:
        state = STATE_PLAYING
        menu_cursor = 0

def btn2_pressed():
    """BTN2: 戻る"""
    global state, library_path, library_cursor, library_scroll, queue_cursor, queue_scroll, start
    
    if not debounce(BTN2_PIN):
        return
    
    start = time.time()
    
    # スクリーンセーバーから復帰
    if state == STATE_OFF:
        state = STATE_PLAYING
        return
    
    if state == STATE_QUEUE_MENU:
        state = STATE_QUEUE
    elif state == STATE_LIBRARY:
        if library_path:
            library_path.pop()
            library_cursor = 0
            library_scroll = 0
        else:
            state = STATE_MAIN_MENU
    elif state == STATE_SYSTEM:
        state = STATE_MAIN_MENU
    else:
        pass

def btn3_pressed():
    """BTN3: メインメニュー"""
    global state, menu_cursor, start
    
    if not debounce(BTN3_PIN):
        return
    
    start = time.time()
    
    # スクリーンセーバーから復帰
    if state == STATE_OFF:
        state = STATE_PLAYING
        return
    
    state = STATE_MAIN_MENU
    menu_cursor = 0

def joystick_up():
    """ジョイスティック上"""
    global state, menu_cursor, library_cursor, queue_cursor, queue_menu_cursor, start

    if not debounce(JS_U_PIN):
        return

    start = time.time()

    # スクリーンセーバーから復帰（ボリューム上げ）
    if state == STATE_OFF:
        state = STATE_PLAYING
        try:
            connect_mpd()
            status = mpd_client.status()
            volume = int(status.get('volume', 50))
            mpd_client.setvol(min(100, volume + 5))
        except:
            pass
        return

    if state == STATE_PLAYING:
        # ボリューム上げ
        try:
            connect_mpd()
            status = mpd_client.status()
            volume = int(status.get('volume', 50))
            mpd_client.setvol(min(100, volume + 5))
        except:
            pass
    elif state == STATE_MAIN_MENU or state == STATE_SYSTEM:
        if menu_cursor > 0:
            menu_cursor -= 1
    elif state == STATE_LIBRARY:
        if library_cursor > 0:
            library_cursor -= 1
    elif state == STATE_QUEUE:
        if queue_cursor > -2:
            queue_cursor -= 1
    elif state == STATE_QUEUE_MENU:
        if queue_menu_cursor > 0:
            queue_menu_cursor -= 1

def joystick_down():
    """ジョイスティック下"""
    global state, menu_cursor, library_cursor, queue_cursor, queue_menu_cursor, start

    if not debounce(JS_D_PIN):
        return

    start = time.time()

    # スクリーンセーバーから復帰（ボリューム下げ）
    if state == STATE_OFF:
        state = STATE_PLAYING
        try:
            connect_mpd()
            status = mpd_client.status()
            volume = int(status.get('volume', 50))
            mpd_client.setvol(max(0, volume - 5))
        except:
            pass
        return

    if state == STATE_PLAYING:
        # ボリューム下げ
        try:
            connect_mpd()
            status = mpd_client.status()
            volume = int(status.get('volume', 50))
            mpd_client.setvol(max(0, volume - 5))
        except:
            pass
    elif state == STATE_MAIN_MENU or state == STATE_SYSTEM:
        # メニュー項目数を動的に取得
        max_items = 4 if state == STATE_MAIN_MENU else 2
        if menu_cursor < max_items - 1:
            menu_cursor += 1
    elif state == STATE_LIBRARY:
        if library_cursor < len(library_items) - 1:
            library_cursor += 1
    elif state == STATE_QUEUE:
        max_cursor = len(queue_items) - 1
        if queue_cursor < max_cursor:
            queue_cursor += 1
    elif state == STATE_QUEUE_MENU:
        if queue_menu_cursor < 2:
            queue_menu_cursor += 1

def joystick_left():
    """ジョイスティック左"""
    global state, start

    if not debounce(JS_L_PIN):
        return

    start = time.time()

    # スクリーンセーバーから復帰（前の曲）
    if state == STATE_OFF:
        state = STATE_PLAYING
        try:
            connect_mpd()
            mpd_client.previous()
        except:
            pass
        return

    if state == STATE_PLAYING:
        # 前の曲
        try:
            connect_mpd()
            mpd_client.previous()
        except:
            pass

def joystick_right():
    """ジョイスティック右"""
    global state, start

    if not debounce(JS_R_PIN):
        return

    start = time.time()

    # スクリーンセーバーから復帰（次の曲）
    if state == STATE_OFF:
        state = STATE_PLAYING
        try:
            connect_mpd()
            mpd_client.next()
        except:
            pass
        return

    if state == STATE_PLAYING:
        # 次の曲
        try:
            connect_mpd()
            mpd_client.next()
        except:
            pass

def joystick_pressed():
    """ジョイスティック押し込み（決定）"""
    global state, menu_cursor, library_cursor, library_path, library_scroll, queue_cursor, queue_menu_cursor, start

    if not debounce(JS_P_PIN):
        return

    start = time.time()

    # スクリーンセーバーから復帰（再生/一時停止）
    if state == STATE_OFF:
        state = STATE_PLAYING
        try:
            connect_mpd()
            status = mpd_client.status()
            if status['state'] == 'play':
                mpd_client.pause(1)
            else:
                mpd_client.play()
        except:
            pass
        return

    if state == STATE_PLAYING:
        # 再生/一時停止
        try:
            connect_mpd()
            status = mpd_client.status()
            if status['state'] == 'play':
                mpd_client.pause(1)
            else:
                mpd_client.play()
        except:
            pass
    elif state == STATE_MAIN_MENU:
        if menu_cursor == 0:
            state = STATE_PLAYING
        elif menu_cursor == 1:
            state = STATE_QUEUE
            queue_cursor = -2  # リピート行から開始
        elif menu_cursor == 2:
            state = STATE_LIBRARY
            library_path = []
            library_cursor = 0
        elif menu_cursor == 3:
            state = STATE_SYSTEM
            menu_cursor = 0
    elif state == STATE_LIBRARY:
        if library_cursor < len(library_items):
            item = library_items[library_cursor]
            if item['type'] == 'parent':
                library_path.pop()
                library_cursor = 0
                library_scroll = 0
            elif item['type'] == 'directory':
                library_path.append(os.path.basename(item['path']))
                library_cursor = 0
                library_scroll = 0
            elif item['type'] == 'file':
                try:
                    connect_mpd()
                    mpd_client.clear()
                    mpd_client.add(item['path'])
                    mpd_client.play()
                    state = STATE_PLAYING
                except:
                    pass
            elif item['type'] == 'playlist':
                try:
                    connect_mpd()
                    mpd_client.clear()
                    mpd_client.load(item['path'])
                    mpd_client.play()
                    state = STATE_PLAYING
                except:
                    pass
    elif state == STATE_QUEUE:
        # リピート/シャッフル切り替え
        if queue_cursor == -2:
            # リピート切り替え
            try:
                connect_mpd()
                status = mpd_client.status()
                current_repeat = status.get('repeat', '0')
                current_single = status.get('single', '0')
                
                # オフ → 全体 → トラック → オフ
                if current_repeat == '0':
                    # オフ → 全体
                    mpd_client.repeat(1)
                    mpd_client.single(0)
                elif current_single == '0':
                    # 全体 → トラック
                    mpd_client.single(1)
                else:
                    # トラック → オフ
                    mpd_client.repeat(0)
                    mpd_client.single(0)
            except:
                pass
        elif queue_cursor == -1:
            # シャッフル切り替え
            try:
                connect_mpd()
                status = mpd_client.status()
                current_random = status.get('random', '0')
                mpd_client.random(0 if current_random == '1' else 1)
            except:
                pass
        else:
            # 通常のキュー項目
            state = STATE_QUEUE_MENU
            queue_menu_cursor = 0
    elif state == STATE_QUEUE_MENU:
        if queue_menu_cursor == 0:
            # 移動（実装は複雑なので省略）
            state = STATE_QUEUE
        elif queue_menu_cursor == 1:
            # 今すぐ再生
            try:
                connect_mpd()
                mpd_client.play(queue_cursor)
                state = STATE_PLAYING
            except:
                pass
        elif queue_menu_cursor == 2:
            # 削除
            try:
                connect_mpd()
                mpd_client.delete(queue_cursor)
                if queue_cursor >= len(queue_items) - 1:
                    queue_cursor = max(0, len(queue_items) - 2)
                state = STATE_QUEUE
            except:
                pass
    elif state == STATE_SYSTEM:
        if menu_cursor == 0:
            os.system("sudo shutdown -h now")
        elif menu_cursor == 1:
            os.system("sudo reboot")

# GPIO設定
btn1 = Button(BTN1_PIN, pull_up=True, bounce_time=0.01)
btn2 = Button(BTN2_PIN, pull_up=True, bounce_time=0.01)
btn3 = Button(BTN3_PIN, pull_up=True, bounce_time=0.01)
js_left = Button(JS_L_PIN, pull_up=True, bounce_time=0.01)
js_right = Button(JS_R_PIN, pull_up=True, bounce_time=0.01)
js_up = Button(JS_U_PIN, pull_up=True, bounce_time=0.01)
js_down = Button(JS_D_PIN, pull_up=True, bounce_time=0.01)
js_press = Button(JS_P_PIN, pull_up=True, bounce_time=0.01)

# イベントハンドラ設定
btn1.when_pressed = btn1_pressed
btn2.when_pressed = btn2_pressed
btn3.when_pressed = btn3_pressed
js_left.when_pressed = joystick_left
js_right.when_pressed = joystick_right
js_up.when_pressed = joystick_up
js_down.when_pressed = joystick_down
js_press.when_pressed = joystick_pressed

# メインループ
try:
    connect_mpd()
    state = STATE_PLAYING
    
    while True:
        current_time = time.time()
        
        # スクリーンセーバー
        if state != STATE_OFF and (current_time - start) > SCREEN_SAVER:
            state = STATE_OFF
        
        draw_screen()
        time.sleep(0.1)  # 10FPSで更新

except KeyboardInterrupt:
    print("\nStopped by user")
    disconnect_mpd()
except Exception as e:
    print("Error:", e)
    disconnect_mpd()
    raise
