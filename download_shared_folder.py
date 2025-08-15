#!/usr/bin/env python3
"""
Google Drive共有フォルダからファイルをダウンロードするスクリプト

このスクリプトは、既存のGoogle Drive共有フォルダから
ファイルをローカルにダウンロードします。
"""

import os
import argparse
import mimetypes
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io


# Google Drive APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# 認証情報ファイル
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'


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


def get_folder_info(service, folder_id: str) -> Optional[dict]:
    """
    フォルダの情報を取得します。
    
    Args:
        service: Google Drive APIサービス
        folder_id: フォルダID
    
    Returns:
        dict: フォルダ情報、失敗時はNone
    """
    try:
        folder = service.files().get(
            fileId=folder_id,
            fields='id,name,mimeType,parents'
        ).execute()
        
        if folder.get('mimeType') != 'application/vnd.google-apps.folder':
            print(f"エラー: 指定されたIDはフォルダではありません: {folder.get('name')}")
            return None
        
        return folder
    
    except HttpError as error:
        print(f"フォルダ情報の取得に失敗しました: {error}")
        return None


def list_folder_contents(service, folder_id: str, page_token=None) -> list:
    """
    フォルダ内のファイルとサブフォルダを一覧表示します。
    
    Args:
        service: Google Drive APIサービス
        folder_id: フォルダID
        page_token: ページネーション用トークン
    
    Returns:
        list: ファイルとフォルダのリスト
    """
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            pageSize=1000,
            fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
            pageToken=page_token
        ).execute()
        
        items = results.get('files', [])
        
        # 次のページがある場合は再帰的に取得
        if results.get('nextPageToken'):
            items.extend(list_folder_contents(service, folder_id, results.get('nextPageToken')))
        
        return items
    
    except HttpError as error:
        print(f"フォルダ内容の取得に失敗しました: {error}")
        return []


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
        
        # Google Workspaceファイル（ドキュメント、スプレッドシート等）の場合は
        # 適切な形式でエクスポート
        if 'google-apps' in file_metadata.get('mimeType', ''):
            print(f"Google Workspaceファイル '{file_name}' をエクスポート中...")
            
            # 適切なMIMEタイプを決定
            export_mime_type = 'application/pdf'
            if 'document' in file_metadata.get('mimeType', ''):
                export_mime_type = 'application/pdf'
            elif 'spreadsheet' in file_metadata.get('mimeType', ''):
                export_mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif 'presentation' in file_metadata.get('mimeType', ''):
                export_mime_type = 'application/pdf'
            
            request = service.files().export_media(
                fileId=file_id,
                mimeType=export_mime_type
            )
        else:
            # 通常のファイルの場合は直接ダウンロード
            request = service.files().get_media(fileId=file_id)
        
        # ファイルをダウンロード
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
        
        print(f"ファイル '{file_name}' をダウンロードしました: {local_path}")
        return True
    
    except HttpError as error:
        print(f"ファイル '{file_name}' のダウンロードに失敗しました: {error}")
        return False
    except Exception as e:
        print(f"ファイル '{file_name}' のダウンロード中にエラーが発生しました: {e}")
        return False


def download_folder_recursively(service, folder_id: str, folder_name: str, local_base_path: str) -> bool:
    """
    フォルダを再帰的にダウンロードします。
    
    Args:
        service: Google Drive APIサービス
        folder_id: フォルダID
        folder_name: フォルダ名
        local_base_path: ローカル保存先のベースパス
    
    Returns:
        bool: 成功時はTrue、失敗時はFalse
    """
    try:
        # ローカルフォルダを作成
        local_folder_path = os.path.join(local_base_path, folder_name)
        os.makedirs(local_folder_path, exist_ok=True)
        
        print(f"フォルダ '{folder_name}' を作成しました: {local_folder_path}")
        
        # フォルダ内のアイテムを取得
        items = list_folder_contents(service, folder_id)
        
        success_count = 0
        total_count = len(items)
        
        for item in items:
            item_name = item['name']
            item_id = item['id']
            item_type = item['mimeType']
            
            if item_type == 'application/vnd.google-apps.folder':
                # サブフォルダの場合は再帰的に処理
                success = download_folder_recursively(
                    service, item_id, item_name, local_folder_path
                )
                if success:
                    success_count += 1
            else:
                # ファイルの場合はダウンロード
                local_file_path = os.path.join(local_folder_path, item_name)
                success = download_file(service, item_id, item_name, local_file_path)
                if success:
                    success_count += 1
        
        print(f"フォルダ '{folder_name}' の処理完了: {success_count}/{total_count} 成功")
        return success_count > 0
    
    except Exception as e:
        print(f"フォルダ '{folder_name}' のダウンロード中にエラーが発生しました: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='Google Drive共有フォルダからファイルをダウンロードします'
    )
    parser.add_argument(
        '--folder-id', '-f',
        required=True,
        help='ダウンロードするGoogle DriveフォルダのID'
    )
    parser.add_argument(
        '--output', '-o',
        default='./downloaded_folder',
        help='ダウンロード先のローカルパス (デフォルト: ./downloaded_folder)'
    )
    parser.add_argument(
        '--list-only', '-l',
        action='store_true',
        help='ファイル一覧のみ表示（ダウンロードは行わない）'
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
        
        # フォルダ情報を取得
        folder_info = get_folder_info(service, args.folder_id)
        if not folder_info:
            return
        
        folder_name = folder_info['name']
        print(f"対象フォルダ: {folder_name}")
        
        if args.list_only:
            # ファイル一覧のみ表示
            print(f"\nフォルダ '{folder_name}' の内容:")
            items = list_folder_contents(service, args.folder_id)
            
            for item in items:
                item_type = "📁" if item['mimeType'] == 'application/vnd.google-apps.folder' else "📄"
                size_info = f" ({item['size']} bytes)" if 'size' in item else ""
                print(f"  {item_type} {item['name']}{size_info}")
        else:
            # フォルダをダウンロード
            print(f"フォルダ '{folder_name}' をダウンロード中...")
            
            # 出力ディレクトリを作成
            os.makedirs(args.output, exist_ok=True)
            
            success = download_folder_recursively(
                service, args.folder_id, folder_name, args.output
            )
            
            if success:
                print(f"\nダウンロード完了: {os.path.join(args.output, folder_name)}")
            else:
                print("ダウンロードに失敗しました。")
    
    except HttpError as error:
        print(f"Google Drive APIエラー: {error}")
    except Exception as e:
        print(f"予期しないエラー: {e}")


if __name__ == '__main__':
    main()
