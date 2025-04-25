from datetime import datetime, timedelta
import pytz
import os

MYT = pytz.timezone('Asia/Kuala_Lumpur')

class StorageManager:
    def __init__(self, drive_client):
        self.drive_client = drive_client
        self.base_dir = "4D_purchase_history"
        self.cleanup_old_receipts()

    def get_myt_now(self):
        return datetime.now(MYT)

    def save_receipt(self, receipt, ticket_count):
        """保存收条到 Google Drive"""
        now = self.get_myt_now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")
        folder_path = f"{self.base_dir}/{year}/{month}/{day}"
        filename = f"{timestamp}_C23GO3F3_{ticket_count}.txt"
        try:
            self.drive_client.upload_file(filename, receipt, folder_path)
            return f"{folder_path}/{filename}"
        except Exception as e:
            raise Exception(f"无法保存收条到 Google Drive: {e}")

    def load_receipts(self, date_str):
        """加载指定日期的收条"""
        receipts = []
        year, month, day = date_str.split('-')
        folder_path = f"{self.base_dir}/{year}/{month}/{day}"
        try:
            files = self.drive_client.list_files(folder_path)
            for filename, _ in files:
                if filename.endswith('.txt'):
                    content = self.drive_client.download_file(filename, folder_path)
                    if content:
                        receipts.append((filename, content))
        except Exception as e:
            print(f"读取 Google Drive 收条失败: {e}")
        return receipts

    def load_all_receipts(self):
        """加载所有收条"""
        receipts = []
        try:
            years = self.drive_client.list_files(self.base_dir)
            for year_name, _ in years:
                if not year_name.isdigit():
                    continue
                months = self.drive_client.list_files(f"{self.base_dir}/{year_name}")
                for month_name, _ in months:
                    if not month_name.isdigit():
                        continue
                    days = self.drive_client.list_files(f"{self.base_dir}/{year_name}/{month_name}")
                    for day_name, _ in days:
                        if not day_name.isdigit():
                            continue
                        date_str = f"{year_name}-{month_name.zfill(2)}-{day_name.zfill(2)}"
                        receipts.extend(self.load_receipts(date_str))
        except Exception as e:
            print(f"加载所有 Google Drive 收条失败: {e}")
        return receipts

    def cleanup_old_receipts(self):
        """清理30天前的收条"""
        cutoff_date = self.get_myt_now() - timedelta(days=30)
        try:
            years = self.drive_client.list_files(self.base_dir)
            for year_name, _ in years:
                if not year_name.isdigit():
                    continue
                months = self.drive_client.list_files(f"{self.base_dir}/{year_name}")
                for month_name, _ in months:
                    if not month_name.isdigit():
                        continue
                    days = self.drive_client.list_files(f"{self.base_dir}/{year_name}/{month_name}")
                    for day_name, _ in days:
                        if not day_name.isdigit():
                            continue
                        date_str = f"{year_name}-{month_name.zfill(2)}-{day_name.zfill(2)}"
                        try:
                            dir_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=MYT)
                            if dir_date < cutoff_date:
                                folder_path = f"{self.base_dir}/{year_name}/{month_name}/{day_name}"
                                folder_id = self.drive_client.get_folder_id(day_name, 
                                    self.drive_client.get_folder_id(month_name, 
                                    self.drive_client.get_folder_id(year_name, self.base_dir)))
                                if folder_id:
                                    self.drive_client.service.files().delete(fileId=folder_id).execute()
                                    print(f"已删除 Google Drive 过期文件夹: {folder_path}")
                        except ValueError:
                            continue
        except Exception as e:
            print(f"清理 Google Drive 存档时出错: {e}")