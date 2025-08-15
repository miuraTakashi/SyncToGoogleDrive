#!/usr/bin/env python3
"""
Raspberry Pi用のcron設定スクリプト

このスクリプトは、Google Drive共有スクリプトを2分ごとに実行するように
cronを設定します。
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def get_script_path():
    """スクリプトの絶対パスを取得"""
    return os.path.abspath(__file__)


def get_project_root():
    """プロジェクトのルートディレクトリを取得"""
    script_path = get_script_path()
    return os.path.dirname(script_path)


def create_cron_entry(folder_path, email, role="writer", interval_minutes=2):
    """
    cronエントリを作成
    
    Args:
        folder_path: 監視するフォルダのパス
        email: 共有先のメールアドレス
        role: 共有権限
        interval_minutes: 実行間隔（分）
    
    Returns:
        str: cronエントリ
    """
    project_root = get_project_root()
    python_path = "/usr/bin/python3"
    script_path = os.path.join(project_root, "share_folder_to_google_drive.py")
    log_path = os.path.join(project_root, "cron.log")
    
    # 2分ごとの場合: */2 * * * *
    if interval_minutes == 2:
        cron_time = "*/2 * * * *"
    elif interval_minutes == 1:
        cron_time = "* * * * *"
    elif interval_minutes == 5:
        cron_time = "*/5 * * * *"
    elif interval_minutes == 10:
        cron_time = "*/10 * * * *"
    elif interval_minutes == 15:
        cron_time = "*/15 * * * *"
    elif interval_minutes == 30:
        cron_time = "*/30 * * * *"
    else:
        # カスタム間隔の場合は分単位で計算
        cron_time = f"*/{interval_minutes} * * * *"
    
    cron_entry = (
        f"{cron_time} cd {project_root} && "
        f"{python_path} {script_path} "
        f"--folder {folder_path} "
        f"--email {email} "
        f"--role {role} "
        f">> {log_path} 2>&1"
    )
    
    return cron_entry


def add_cron_job(cron_entry):
    """
    cronジョブを追加
    
    Args:
        cron_entry: 追加するcronエントリ
    
    Returns:
        bool: 成功時はTrue、失敗時はFalse
    """
    try:
        # 現在のcronジョブを取得
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False
        )
        
        current_crons = result.stdout.strip()
        
        # 既存のエントリがあるかチェック
        if cron_entry in current_crons:
            print("このcronジョブは既に存在します。")
            return True
        
        # 新しいcronエントリを追加
        new_crons = current_crons + "\n" + cron_entry if current_crons else cron_entry
        
        # 一時ファイルに書き込み
        temp_file = "/tmp/new_crontab"
        with open(temp_file, "w") as f:
            f.write(new_crons + "\n")
        
        # crontabを更新
        subprocess.run(["crontab", temp_file], check=True)
        
        # 一時ファイルを削除
        os.remove(temp_file)
        
        print("cronジョブが正常に追加されました。")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"cronジョブの追加に失敗しました: {e}")
        return False
    except Exception as e:
        print(f"予期しないエラー: {e}")
        return False


def remove_cron_job(folder_path, email):
    """
    特定のcronジョブを削除
    
    Args:
        folder_path: 監視するフォルダのパス
        email: 共有先のメールアドレス
    
    Returns:
        bool: 成功時はTrue、失敗時はFalse
    """
    try:
        # 現在のcronジョブを取得
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False
        )
        
        current_crons = result.stdout.strip()
        if not current_crons:
            print("cronジョブが存在しません。")
            return True
        
        # 該当するエントリを除外
        lines = current_crons.split('\n')
        filtered_lines = []
        
        for line in lines:
            if (folder_path in line and email in line and 
                "share_folder_to_google_drive.py" in line):
                print(f"削除するcronジョブ: {line}")
            else:
                filtered_lines.append(line)
        
        if len(filtered_lines) == len(lines):
            print("該当するcronジョブが見つかりませんでした。")
            return True
        
        # 新しいcrontabを設定
        new_crons = '\n'.join(filtered_lines)
        if new_crons.strip():
            temp_file = "/tmp/new_crontab"
            with open(temp_file, "w") as f:
                f.write(new_crons + "\n")
            
            subprocess.run(["crontab", temp_file], check=True)
            os.remove(temp_file)
        else:
            # すべてのジョブを削除
            subprocess.run(["crontab", "-r"], check=True)
        
        print("cronジョブが正常に削除されました。")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"cronジョブの削除に失敗しました: {e}")
        return False
    except Exception as e:
        print(f"予期しないエラー: {e}")
        return False


def list_cron_jobs():
    """現在のcronジョブを一覧表示"""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.stdout.strip():
            print("現在のcronジョブ:")
            print(result.stdout)
        else:
            print("cronジョブが設定されていません。")
            
    except subprocess.CalledProcessError as e:
        print(f"cronジョブの取得に失敗しました: {e}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='Raspberry Pi用のcron設定スクリプト'
    )
    parser.add_argument(
        '--folder', '-f',
        required=True,
        help='監視するフォルダのパス'
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
        '--interval', '-i',
        type=int,
        default=2,
        help='実行間隔（分、デフォルト: 2）'
    )
    parser.add_argument(
        '--remove', '-rm',
        action='store_true',
        help='指定した条件のcronジョブを削除'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='現在のcronジョブを一覧表示'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_cron_jobs()
        return
    
    if args.remove:
        remove_cron_job(args.folder, args.email)
        return
    
    # cronエントリを作成
    cron_entry = create_cron_entry(
        args.folder, 
        args.email, 
        args.role, 
        args.interval
    )
    
    print("作成されるcronエントリ:")
    print(cron_entry)
    print()
    
    # 確認
    response = input("このcronジョブを追加しますか？ (y/N): ")
    if response.lower() in ['y', 'yes']:
        add_cron_job(cron_entry)
    else:
        print("cronジョブの追加をキャンセルしました。")


if __name__ == '__main__':
    main()
