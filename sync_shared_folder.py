#!/usr/bin/env python3
"""
Google Drive共有フォルダの自動同期スクリプト

このスクリプトは、Google Driveの共有フォルダを監視し、
変更があった場合に自動的にローカルフォルダと同期します。
"""

import os
import time
import hashlib
import argparse
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Google Drive APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# 認証情報ファイル
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

# 同期状態ファイル
SYNC_STATE_FILE = 'sync_state.json'


def authenticate_google_drive() -> Optional[Credentials]:
    """
    Google Drive APIの認証を行います。
    
    Returns:
        Credentials: 認証済みのクレデンシャル、失敗時はNone
    """
    creds = None
    
    # 既存のトークンファイルがある場合は読み込み
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # 有効なクレデンシャルがない場合、または期限切れの場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"トークンの更新に失敗しました: {e}")
                creds = None
        
        # 新しい認証フローを開始
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"エラー: {CREDENTIALS_FILE} ファイルが見つかりません。")
                print("Google Cloud ConsoleからOAuth 2.0クライアントIDをダウンロードしてください。")
                return None
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"認証に失敗しました: {e}")
                return None
        
        # トークンをファイルに保存
        try:
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"トークンの保存に失敗しました: {e}")
    
    return creds


def load_sync_state() -> Dict:
    """
    同期状態を読み込みます。
    
    Returns:
        Dict: 同期状態
    """
    if os.path.exists(SYNC_STATE_FILE):
        try:
            with open(SYNC_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"同期状態の読み込みに失敗しました: {e}")
    
    return {}


def save_sync_state(state: Dict):
    """
    同期状態を保存します。
    
    Args:
        state: 保存する同期状態
    """
    try:
        with open(SYNC_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"同期状態の保存に失敗しました: {e}")


def get_file_hash(file_path: str) -> str:
    """
    ファイルのハッシュ値を計算します。
    
    Args:
        file_path: ファイルパス
    
    Returns:
        str: ファイルのハッシュ値
    """
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def get_folder_contents(service, folder_id: str) -> List[Dict]:
    """
    フォルダ内のファイルとサブフォルダを取得します。
    
    Args:
        service: Google Drive APIサービス
        folder_id: フォルダID
    
    Returns:
        List[Dict]: ファイルとフォルダのリスト
    """
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            pageSize=1000,
            fields="files(id, name, mimeType, size, modifiedTime, md5Checksum)",
            orderBy="modifiedTime desc"
        ).execute()
        
        return results.get('files', [])
    
    except HttpError as error:
        print(f"フォルダ内容の取得に失敗しました: {error}")
        return []


def check_for_changes(service, folder_id: str, local_path: str, sync_state: Dict) -> bool:
    """
    変更があるかチェックします。
    
    Args:
        service: Google Drive APIサービス
        folder_id: フォルダID
        local_path: ローカルパス
        sync_state: 同期状態
    
    Returns:
        bool: 変更がある場合はTrue
    """
    try:
        # Google Driveの内容を取得
        drive_items = get_folder_contents(service, folder_id)
        
        # ローカルファイルの状態を確認
        local_items = {}
        if os.path.exists(local_path):
            for item in Path(local_path).rglob('*'):
                if item.is_file():
                    rel_path = str(item.relative_to(local_path))
                    local_items[rel_path] = {
                        'size': item.stat().st_size,
                        'modified': item.stat().st_mtime,
                        'hash': get_file_hash(str(item))
                    }
        
        # 変更をチェック
        for item in drive_items:
            item_name = item['name']
            item_id = item['id']
            item_type = item['mimeType']
            
            if item_type == 'application/vnd.google-apps.folder':
                # サブフォルダの場合は再帰的にチェック
                sub_local_path = os.path.join(local_path, item_name)
                sub_folder_id = item_id
                
                if check_for_changes(service, sub_folder_id, sub_local_path, sync_state):
                    return True
            else:
                # ファイルの変更をチェック
                local_file_path = os.path.join(local_path, item_name)
                
                # ファイルが存在しない、または変更されている場合
                if not os.path.exists(local_file_path):
                    print(f"新しいファイルを検出: {item_name}")
                    return True
                
                # サイズや変更日時をチェック
                local_stat = os.stat(local_file_path)
                drive_modified = item.get('modifiedTime')
                
                if drive_modified:
                    # ISO形式の日時をパース
                    drive_time = datetime.fromisoformat(drive_modified.replace('Z', '+00:00'))
                    local_time = datetime.fromtimestamp(local_stat.st_mtime)
                    
                    # 1分以上の差がある場合は変更とみなす
                    if abs((drive_time - local_time).total_seconds()) > 60:
                        print(f"ファイルの変更を検出: {item_name}")
                        return True
                
                # サイズの変更をチェック
                if local_stat.st_size != int(item.get('size', 0)):
                    print(f"ファイルサイズの変更を検出: {item_name}")
                    return True
        
        return False
    
    except Exception as e:
        print(f"変更チェック中にエラーが発生しました: {e}")
        return True


def sync_folder(service, folder_id: str, local_path: str, sync_state: Dict):
    """
    フォルダを同期します。
    
    Args:
        service: Google Drive APIサービス
        folder_id: フォルダID
        local_path: ローカルパス
        sync_state: 同期状態
    """
    try:
        # ローカルフォルダを作成
        os.makedirs(local_path, exist_ok=True)
        
        # Google Driveの内容を取得
        drive_items = get_folder_contents(service, folder_id)
        
        # 各アイテムを処理
        for item in drive_items:
            item_name = item['name']
            item_id = item['id']
            item_type = item['mimeType']
            
            if item_type == 'application/vnd.google-apps.folder':
                # サブフォルダの場合は再帰的に同期
                sub_local_path = os.path.join(local_path, item_name)
                sub_folder_id = item_id
                
                sync_folder(service, sub_folder_id, sub_local_path, sync_state)
            else:
                # ファイルの同期
                local_file_path = os.path.join(local_path, item_name)
                
                # ファイルが存在しない、または変更されている場合のみダウンロード
                if not os.path.exists(local_file_path) or is_file_modified(item, local_file_path):
                    print(f"ファイルを同期中: {item_name}")
                    
                    # ファイルをダウンロード
                    if download_file(service, item_id, item_name, local_file_path):
                        # 同期状態を更新
                        sync_state[item_id] = {
                            'name': item_name,
                            'modified': item.get('modifiedTime'),
                            'size': item.get('size'),
                            'local_path': local_file_path,
                            'synced_at': datetime.now().isoformat()
                        }
        
        # 同期状態を保存
        save_sync_state(sync_state)
        
    except Exception as e:
        print(f"フォルダの同期中にエラーが発生しました: {e}")


def is_file_modified(drive_item: Dict, local_file_path: str) -> bool:
    """
    ファイルが変更されているかチェックします。
    
    Args:
        drive_item: Google Driveのアイテム情報
        local_file_path: ローカルファイルパス
    
    Returns:
        bool: 変更されている場合はTrue
    """
    try:
        if not os.path.exists(local_file_path):
            return True
        
        local_stat = os.stat(local_file_path)
        drive_modified = drive_item.get('modifiedTime')
        
        if drive_modified:
            drive_time = datetime.fromisoformat(drive_modified.replace('Z', '+00:00'))
            local_time = datetime.fromtimestamp(local_stat.st_mtime)
            
            # 1分以上の差がある場合は変更とみなす
            if abs((drive_time - local_time).total_seconds()) > 60:
                return True
        
        # サイズの変更をチェック
        if local_stat.st_size != int(drive_item.get('size', 0)):
            return True
        
        return False
    
    except Exception:
        return True


def download_file(service, file_id: str, file_name: str, local_path: str) -> bool:
    """
    ファイルをダウンロードします。
    
    Args:
        service: Google Drive APIサービス
        file_id: ファイルID
        file_name: ファイル名
        local_path: ローカル保存先パス
    
    Returns:
        bool: 成功時はTrue、失敗時はFalse
    """
    try:
        # ファイルのメタデータを取得
        file_metadata = service.files().get(fileId=file_id).execute()
        
        # Google Workspaceファイルの場合はPDFでエクスポート
        if 'google-apps' in file_metadata.get('mimeType', ''):
            print(f"Google Workspaceファイル '{file_name}' をエクスポート中...")
            
            request = service.files().export_media(
                fileId=file_id,
                mimeType='application/pdf'
            )
        else:
            # 通常のファイルの場合は直接ダウンロード
            request = service.files().get_media(fileId=file_id)
        
        # ファイルをダウンロード
        import io
        from googleapiclient.http import MediaIoBaseDownload
        
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            if status:
                print(f"ダウンロード進捗: {int(status.progress() * 100)}%")
        
        # ファイルを保存
        with open(local_path, 'wb') as f:
            f.write(fh.getvalue())
        
        print(f"ファイル '{file_name}' を同期しました")
        return True
    
    except HttpError as error:
        print(f"ファイル '{file_name}' のダウンロードに失敗しました: {error}")
        return False
    except Exception as e:
        print(f"ファイル '{file_name}' のダウンロード中にエラーが発生しました: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='Google Drive共有フォルダを自動同期します'
    )
    parser.add_argument(
        '--folder-id', '-f',
        required=True,
        help='同期するGoogle DriveフォルダのID'
    )
    parser.add_argument(
        '--local-path', '-l',
        required=True,
        help='同期先のローカルパス'
    )
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=300,
        help='同期間隔（秒、デフォルト: 300秒 = 5分）'
    )
    parser.add_argument(
        '--once', '-o',
        action='store_true',
        help='一度だけ同期を実行（監視は行わない）'
    )
    
    args = parser.parse_args()
    
    # Google Drive APIの認証
    print("Google Drive APIの認証中...")
    creds = authenticate_google_drive()
    if not creds:
        print("認証に失敗しました。")
        return
    
    try:
        # Google Drive APIサービスを構築
        service = build('drive', 'v3', credentials=creds)
        print("Google Drive APIに接続しました。")
        
        # 同期状態を読み込み
        sync_state = load_sync_state()
        
        if args.once:
            # 一度だけ同期
            print(f"フォルダを同期中...")
            sync_folder(service, args.folder_id, args.local_path, sync_state)
            print("同期完了")
        else:
            # 継続的に監視
            print(f"フォルダの監視を開始します（間隔: {args.interval}秒）")
            print(f"ローカルパス: {args.local_path}")
            print("Ctrl+Cで停止")
            
            try:
                while True:
                    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 変更をチェック中...")
                    
                    if check_for_changes(service, args.folder_id, args.local_path, sync_state):
                        print("変更を検出しました。同期を開始...")
                        sync_folder(service, args.folder_id, args.local_path, sync_state)
                        print("同期完了")
                    else:
                        print("変更はありません")
                    
                    time.sleep(args.interval)
                    
            except KeyboardInterrupt:
                print("\n監視を停止しました")
    
    except HttpError as error:
        print(f"Google Drive APIエラー: {error}")
    except Exception as e:
        print(f"予期しないエラー: {e}")


if __name__ == '__main__':
    main()
