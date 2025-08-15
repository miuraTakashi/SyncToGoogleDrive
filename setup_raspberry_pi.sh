#!/bin/bash

# Raspberry Pi用のGoogle Drive共有自動化セットアップスクリプト

set -e

# 色付きの出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 設定確認
check_config() {
    log_info "設定を確認中..."
    
    if [ ! -f "share_folder_to_google_drive.py" ]; then
        log_error "share_folder_to_google_drive.py が見つかりません"
        exit 1
    fi
    
    if [ ! -f "setup_cron.py" ]; then
        log_error "setup_cron.py が見つかりません"
        exit 1
    fi
    
    log_info "必要なファイルが確認されました"
}

# 依存関係のインストール
install_dependencies() {
    log_info "依存関係をインストール中..."
    
    # Python3とpip3の確認
    if ! command -v python3 &> /dev/null; then
        log_error "Python3がインストールされていません"
        exit 1
    fi
    
    if ! command -v pip3 &> /dev/null; then
        log_info "pip3をインストール中..."
        sudo apt-get update
        sudo apt-get install -y python3-pip
    fi
    
    # 必要なPythonパッケージをインストール
    log_info "Pythonパッケージをインストール中..."
    pip3 install -r requirements.txt
    
    log_info "依存関係のインストールが完了しました"
}

# cronの設定
setup_cron() {
    log_info "cronの設定中..."
    
    echo "cronの設定を行います。"
    echo "監視するフォルダのパスを入力してください:"
    read -r folder_path
    
    echo "共有先のメールアドレスを入力してください:"
    read -r email
    
    echo "共有権限を選択してください (reader/writer/commenter/owner) [writer]:"
    read -r role
    role=${role:-writer}
    
    echo "実行間隔（分）を入力してください [2]:"
    read -r interval
    interval=${interval:-2}
    
    # Pythonスクリプトを実行
    python3 setup_cron.py --folder "$folder_path" --email "$email" --role "$role" --interval "$interval"
    
    log_info "cronの設定が完了しました"
}

# systemdの設定
setup_systemd() {
    log_info "systemdの設定中..."
    
    # サービスファイルとタイマーファイルをコピー
    sudo cp synctogoogledrive.service /etc/systemd/system/
    sudo cp synctogoogledrive.timer /etc/systemd/system/
    
    # 設定を再読み込み
    sudo systemctl daemon-reload
    
    # タイマーを有効化して開始
    sudo systemctl enable synctogoogledrive.timer
    sudo systemctl start synctogoogledrive.timer
    
    log_info "systemdの設定が完了しました"
}

# ログローテーションの設定
setup_logrotate() {
    log_info "ログローテーションの設定中..."
    
    cat > /tmp/synctogoogledrive.logrotate << EOF
/home/pi/SyncToGoogleDrive/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 pi pi
}
EOF
    
    sudo cp /tmp/synctogoogledrive.logrotate /etc/logrotate.d/synctogoogledrive
    rm /tmp/synctogoogledrive.logrotate
    
    log_info "ログローテーションの設定が完了しました"
}

# 状態確認
check_status() {
    log_info "設定状態を確認中..."
    
    echo ""
    echo "=== cronジョブの確認 ==="
    crontab -l 2>/dev/null || echo "cronジョブが設定されていません"
    
    echo ""
    echo "=== systemdタイマーの状態 ==="
    if systemctl is-enabled synctogoogledrive.timer &>/dev/null; then
        systemctl status synctogoogledrive.timer --no-pager -l
    else
        echo "systemdタイマーが設定されていません"
    fi
    
    echo ""
    echo "=== ログファイルの確認 ==="
    ls -la *.log 2>/dev/null || echo "ログファイルが見つかりません"
}

# メイン処理
main() {
    echo "=========================================="
    echo "Raspberry Pi用 Google Drive共有自動化セットアップ"
    echo "=========================================="
    
    # 現在のディレクトリを確認
    if [ ! -f "setup_raspberry_pi.sh" ]; then
        log_error "このスクリプトはプロジェクトのルートディレクトリで実行してください"
        exit 1
    fi
    
    check_config
    install_dependencies
    
    echo ""
    echo "自動化の方法を選択してください:"
    echo "1) cronを使用（推奨）"
    echo "2) systemdを使用"
    echo "3) 両方を設定"
    echo "4) 状態確認のみ"
    
    read -p "選択してください (1-4): " choice
    
    case $choice in
        1)
            setup_cron
            ;;
        2)
            setup_systemd
            ;;
        3)
            setup_cron
            setup_systemd
            setup_logrotate
            ;;
        4)
            check_status
            ;;
        *)
            log_error "無効な選択です"
            exit 1
            ;;
    esac
    
    check_status
    
    echo ""
    log_info "セットアップが完了しました！"
    echo ""
    echo "使用方法:"
    echo "- cronの場合: 設定した間隔で自動実行されます"
    echo "- systemdの場合: sudo systemctl status synctogoogledrive.timer で状態確認"
    echo "- ログの確認: tail -f *.log"
}

# スクリプトの実行
main "$@"
