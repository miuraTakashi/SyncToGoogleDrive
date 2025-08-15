# Google Drive フォルダ共有スクリプト

このPythonスクリプトは、指定したローカルフォルダをGoogle Driveにアップロードし、特定のユーザーと共有するためのツールです。

## 機能

- ローカルフォルダをGoogle Driveに再帰的にアップロード
- 指定したユーザーとのフォルダ共有
- 共有権限の設定（読み取り専用、編集可能、コメント可能、所有者）
- 既存のGoogle Driveフォルダ内へのアップロード

## 必要な環境

- Python 3.7以上
- Google Cloud Platform アカウント
- Google Drive API の有効化

## セットアップ手順

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. Google Cloud Console での設定

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成（または既存のプロジェクトを選択）
3. Google Drive API を有効化
4. OAuth 2.0 クライアントIDを作成
   - アプリケーションの種類: デスクトップアプリケーション
   - 名前: 任意の名前（例: "Drive Folder Share"）
5. 認証情報をダウンロード（JSONファイル）
6. ダウンロードしたファイルを `credentials.json` という名前でスクリプトと同じディレクトリに配置

### 3. 初回実行時の認証

初回実行時は、ブラウザが開いてGoogleアカウントでの認証が求められます。認証が完了すると、`token.json` ファイルが作成され、以降の実行時は自動的に認証されます。

## 使用方法

### 基本的な使用方法

```bash
python share_folder_to_google_drive.py --folder /path/to/folder --email user@example.com
```

### オプション

- `--folder, -f`: アップロードするローカルフォルダのパス（必須）
- `--email, -e`: 共有先のユーザーのメールアドレス（必須）
- `--role, -r`: 共有権限（オプション、デフォルト: writer）
  - `reader`: 読み取り専用
  - `writer`: 編集可能
  - `commenter`: コメント可能
  - `owner`: 所有者
- `--parent-folder, -p`: Google Drive上の親フォルダID（オプション、指定しない場合はルート）

### 使用例

#### 例1: 基本的な共有
```bash
python share_folder_to_google_drive.py --folder ~/Documents/Project --email colleague@company.com
```

#### 例2: 読み取り専用で共有
```bash
python share_folder_to_google_drive.py --folder ~/Documents/Project --email client@company.com --role reader
```

#### 例3: 特定のGoogle Driveフォルダ内にアップロード
```bash
python share_folder_to_google_drive.py --folder ~/Documents/Project --email team@company.com --parent-folder 1ABC123DEF456
```

## ファイル構成

- `share_folder_to_google_drive.py`: メインスクリプト
- `requirements.txt`: 必要なPythonパッケージ
- `credentials.json`: Google Cloud Consoleからダウンロードした認証情報（手動配置）
- `token.json`: 認証トークン（自動生成）

## 注意事項

- 初回実行時は、ブラウザでの認証が必要です
- 大きなフォルダのアップロードには時間がかかる場合があります
- Google Driveの容量制限に注意してください
- 共有先のユーザーは、共有されたフォルダへのアクセス権限が付与されます

## トラブルシューティング

### 認証エラー
- `credentials.json` ファイルが正しく配置されているか確認
- Google Cloud ConsoleでGoogle Drive APIが有効化されているか確認

### アップロードエラー
- フォルダパスが正しいか確認
- ファイルの権限を確認
- Google Driveの容量制限を確認

### 共有エラー
- 共有先のメールアドレスが正しいか確認
- 共有先のユーザーがGoogleアカウントを持っているか確認

## Raspberry Piでの自動実行設定

### 方法1: cronを使用（推奨）

最も簡単で確実な方法です。

```bash
# セットアップスクリプトを実行
./setup_raspberry_pi.sh

# または、手動でcronを設定
python3 setup_cron.py --folder /path/to/folder --email user@example.com --interval 2
```

### 方法2: systemdを使用

より高度な制御が必要な場合。

```bash
# セットアップスクリプトを実行
./setup_raspberry_pi.sh

# 手動で設定する場合
sudo cp synctogoogledrive.service /etc/systemd/system/
sudo cp synctogoogledrive.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable synctogoogledrive.timer
sudo systemctl start synctogoogledrive.timer
```

### 設定の確認

```bash
# cronジョブの確認
crontab -l

# systemdタイマーの状態確認
sudo systemctl status synctogoogledrive.timer

# ログの確認
tail -f *.log
```

### 注意事項

- Raspberry Pi OS（Raspbian）での動作を確認済み
- 初回実行時はGoogle Drive APIの認証が必要
- ログファイルは自動的にローテーションされます
- ネットワーク接続が必要です

## ライセンス

このスクリプトはMITライセンスの下で提供されています。
