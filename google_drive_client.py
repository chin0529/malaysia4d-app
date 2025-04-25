from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io
import os
import json

class GoogleDriveClient:
    def __init__(self, credentials_json, parent_folder_id):
        scopes = ['https://www.googleapis.com/auth/drive']
        # 从环境变量加载凭证
        if isinstance(credentials_json, str):
            with open('/tmp/credentials.json', 'w') as f:
                f.write(credentials_json)
            credentials = service_account.Credentials.from_service_account_file(
                '/tmp/credentials.json', scopes=scopes)
        else:
            credentials = service_account.Credentials.from_service_account_info(
                credentials_json, scopes=scopes)
        self.service = build('drive', 'v3', credentials=credentials)
        self.parent_folder_id = parent_folder_id

    def upload_file(self, file_name, file_content, folder_path):
        """上传文件到指定文件夹"""
        folder_id = self.ensure_folder(folder_path)
        file_metadata = {
            'name': file_name,
            'parents': [folder_id],
            'mimeType': 'text/plain'
        }
        # 创建临时文件
        temp_path = '/tmp/temp_file'
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        media = MediaFileUpload(temp_path, mimetype='text/plain')
        self.service.files().create(body=file_metadata, media_body=media).execute()
        os.remove(temp_path)

    def download_file(self, file_name, folder_path):
        """下载文件内容"""
        folder_id = self.get_folder_id(folder_path)
        if not folder_id:
            return None
        file_id = self.get_file_id(file_name, folder_id)
        if not file_id:
            return None
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return fh.read().decode('utf-8')

    def list_files(self, folder_path):
        """列出文件夹中的文件"""
        folder_id = self.get_folder_id(folder_path)
        if not folder_id:
            return []
        query = f"'{folder_id}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        return [(item['name'], item['id']) for item in results.get('files', [])]

    def ensure_folder(self, folder_path):
        """确保文件夹存在，返回文件夹 ID"""
        parts = folder_path.strip('/').split('/')
        current_folder_id = self.parent_folder_id
        for part in parts:
            folder_id = self.get_folder_id(part, current_folder_id)
            if not folder_id:
                file_metadata = {
                    'name': part,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [current_folder_id]
                }
                folder = self.service.files().create(body=file_metadata, fields='id').execute()
                folder_id = folder.get('id')
            current_folder_id = folder_id
        return current_folder_id

    def get_folder_id(self, folder_name, parent_id=None):
        """获取文件夹 ID"""
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        folders = results.get('files', [])
        return folders[0]['id'] if folders else None

    def get_file_id(self, file_name, folder_id):
        """获取文件 ID"""
        query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None