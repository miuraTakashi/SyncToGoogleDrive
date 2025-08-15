#!/usr/bin/env python3
"""
Google Driveとフォルダを共有するPythonスクリプト

このスクリプトは、指定したローカルフォルダをGoogle Driveにアップロードし、
指定したユーザーと共有します。

使用方法:
    python share_folder_to_google_drive.py --folder /path/to/folder --email user@example.com

必要な設定:
    1. Google Cloud Consoleでプロジェクトを作成
    2. Google Drive APIを有効化
    3. 認証情報（OAuth 2.0クライアントID）をダウンロード
    4. credentials.jsonファイルをスクリプトと同じディレクトリに配置
"""

import os
import argparse
import mimetypes
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


# Google Drive APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/drive.file']

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


def create_folder_in_drive(service, folder_name: str, parent_id: str = None) -> str:
    """
    Google Driveにフォルダを作成します。
    
    Args:
        service: Google Drive APIサービス
        folder_name: 作成するフォルダ名
        parent_id: 親フォルダのID（Noneの場合はルート）
    
    Returns:
        str: 作成されたフォルダのID
    """
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    if parent_id:
        folder_metadata['parents'] = [parent_id]
    
    try:
        folder = service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        
        folder_id = folder.get('id')
        print(f"フォルダ '{folder_name}' を作成しました (ID: {folder_id})")
        return folder_id
    
    except HttpError as error:
        print(f"フォルダの作成に失敗しました: {error}")
        return None


def upload_file_to_drive(service, file_path: str, parent_id: str) -> str:
    """
    ファイルをGoogle Driveにアップロードします。
    
    Args:
        service: Google Drive APIサービス
        file_path: アップロードするファイルのパス
        parent_id: アップロード先のフォルダID
    
    Returns:
        str: アップロードされたファイルのID
    """
    file_name = os.path.basename(file_path)
    
    # MIMEタイプを推測
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'
    
    try:
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        
        file_metadata = {
            'name': file_name,
            'parents': [parent_id]
        }
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = file.get('id')
        print(f"ファイル '{file_name}' をアップロードしました (ID: {file_id})")
        return file_id
    
    except HttpError as error:
        print(f"ファイル '{file_name}' のアップロードに失敗しました: {error}")
        return None


def upload_folder_recursively(service, local_folder_path: str, drive_parent_id: str) -> bool:
    """
    フォルダを再帰的にGoogle Driveにアップロードします。
    
    Args:
        service: Google Drive APIサービス
        local_folder_path: アップロードするローカルフォルダのパス
        drive_parent_id: アップロード先のGoogle DriveフォルダID
    
    Returns:
        bool: 成功時はTrue、失敗時はFalse
    """
    try:
        local_path = Path(local_folder_path)
        folder_name = local_path.name
        
        # Google Driveにフォルダを作成
        drive_folder_id = create_folder_in_drive(service, folder_name, drive_parent_id)
        if not drive_folder_id:
            return False
        
        # フォルダ内のファイルとサブフォルダを処理
        for item in local_path.iterdir():
            if item.is_file():
                upload_file_to_drive(service, str(item), drive_folder_id)
            elif item.is_dir():
                upload_folder_recursively(service, str(item), drive_folder_id)
        
        return True
    
    except Exception as e:
        print(f"フォルダ '{local_folder_path}' のアップロードに失敗しました: {e}")
        return False


def share_folder_with_user(service, folder_id: str, user_email: str, role: str = 'writer') -> bool:
    """
    フォルダを特定のユーザーと共有します。
    
    Args:
        service: Google Drive APIサービス
        folder_id: 共有するフォルダのID
        user_email: 共有先のユーザーのメールアドレス
        role: 共有権限（'reader', 'writer', 'commenter', 'owner'）
    
    Returns:
        bool: 成功時はTrue、失敗時はFalse
    """
    try:
        permission = {
            'type': 'user',
            'role': role,
            'emailAddress': user_email
        }
        
        service.permissions().create(
            fileId=folder_id,
            body=permission,
            fields='id'
        ).execute()
        
        print(f"フォルダを '{user_email}' と共有しました (権限: {role})")
        return True
    
    except HttpError as error:
        print(f"フォルダの共有に失敗しました: {error}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='ローカルフォルダをGoogle Driveにアップロードして共有します'
    )
    parser.add_argument(
        '--folder', '-f',
        required=True,
        help='アップロードするローカルフォルダのパス'
    )
    parser.add_argument(
        '--email', '-e',
        required=True,
        help='共有先のユーザーのメールアドレス'
    )
    parser.add_argument(
        '--role', '-r',
        default='writer',
        choices=['reader', 'writer', 'commenter', 'owner'],
        help='共有権限 (デフォルト: writer)'
    )
    parser.add_argument(
        '--parent-folder', '-p',
        help='Google Drive上の親フォルダID（指定しない場合はルート）'
    )
    
    args = parser.parse_args()
    
    # フォルダの存在確認
    if not os.path.exists(args.folder):
        print(f"エラー: フォルダ '{args.folder}' が存在しません。")
        return
    
    if not os.path.isdir(args.folder):
        print(f"エラー: '{args.folder}' はフォルダではありません。")
        return
    
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
        
        # フォルダをアップロード
        print(f"フォルダ '{args.folder}' をアップロード中...")
        success = upload_folder_recursively(service, args.folder, args.parent_folder or 'root')
        
        if success:
            # アップロードされたフォルダのIDを取得
            folder_name = os.path.basename(args.folder)
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
            if args.parent_folder:
                query += f" and '{args.parent_folder}' in parents"
            
            results = service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            
            if files:
                folder_id = files[0]['id']
                print(f"アップロード完了: フォルダID = {folder_id}")
                
                # ユーザーと共有
                print(f"ユーザー '{args.email}' と共有中...")
                share_folder_with_user(service, folder_id, args.email, args.role)
                
                # 共有リンクを生成
                share_link = f"https://drive.google.com/drive/folders/{folder_id}"
                print(f"共有リンク: {share_link}")
            else:
                print("アップロードされたフォルダのIDを取得できませんでした。")
        else:
            print("フォルダのアップロードに失敗しました。")
    
    except HttpError as error:
        print(f"Google Drive APIエラー: {error}")
    except Exception as e:
        print(f"予期しないエラー: {e}")


if __name__ == '__main__':
    main()
