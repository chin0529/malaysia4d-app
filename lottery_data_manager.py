import json
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import pytz
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

MYT = pytz.timezone('Asia/Kuala_Lumpur')

class LotteryDataManager:
    def __init__(self, drive_client):
        self.drive_client = drive_client
        self.all_results = {}
        self.allowed_operators = [
            "magnum 4d", "da ma cai 1+3d", "sports toto 4d",
            "singapore 4d", "grand dragon 4d", "9 lotto 4d"
        ]
        self.excluded_operators = [
            "9 lotto 6d", "9 lotto 6+1d", "9 lotto super jackpot pool"
        ]

    def normalize_operator_name(self, name):
        name = name.lower().strip()
        name = name.replace("sportstoto", "sports toto").replace("  ", " ")
        if "9 lotto" in name and "4d" not in name and "6d" not in name and "6+1d" not in name and "super jackpot pool" not in name:
            name = "9 lotto 4d"
        return name

    def fetch_and_save_data(self):
        """从 4dnow.net 抓取数据"""
        url = "https://4dnow.net/"
        try:
            print("正在抓取数据...")
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            }
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
            session.mount('https://', HTTPAdapter(max_retries=retries))
            time.sleep(random.uniform(1, 3))  # 随机延迟
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"抓取数据失败: {str(e)}")
            return None

    def parse_data(self, html_content):
        """解析抓取的 HTML 并存储到 Google Drive"""
        self.all_results.clear()
        try:
            print("\n开始分析数据...")
            if not html_content:
                raise ValueError("HTML 内容为空")
            soup = BeautifulSoup(html_content, 'html.parser')
            lottery_boxes = soup.find_all('div', class_=['lottery-box', 'result-box'])
            for box in lottery_boxes:
                operator_name = "Unknown Operator"
                operator_info = box.find('div', class_=['info', 'text-info', 'operator-info'])
                if operator_info:
                    operator_b = operator_info.find('b')
                    operator_span = operator_info.find('span')
                    if operator_b and operator_b.text.strip():
                        operator_name = operator_b.text.strip()
                    elif operator_span and operator_span.text.strip():
                        operator_name = operator_span.text.strip()
                normalized_name = self.normalize_operator_name(operator_name)
                if normalized_name in self.excluded_operators or normalized_name not in self.allowed_operators:
                    continue
                draw_date = "N/A"
                date_elem = box.find('div', class_=['date', 'draw-date']) or box.find('span', class_=['date', 'draw-date'])
                if date_elem and date_elem.text.strip():
                    draw_date = date_elem.text.strip()
                    try:
                        parsed_date = datetime.strptime(draw_date, "%d/%m/%y").replace(tzinfo=MYT)
                        draw_date = parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        try:
                            parsed_date = datetime.strptime(draw_date, "%d/%m/%y %I:%M%p").replace(tzinfo=MYT)
                            draw_date = parsed_date.strftime("%Y-%m-%d")
                        except ValueError:
                            print(f"日期格式不标准: {draw_date}")
                            draw_date = datetime.now(MYT).strftime("%Y-%m-%d")
                date_yyyymmdd = datetime.strptime(draw_date, "%Y-%m-%d").strftime("%Y%m%d")
                results = {}
                main_row = box.find('div', class_=['main', 'el-row'])
                if main_row:
                    prize_cols = main_row.find_all('div', class_=['el-col', 'el-col-8', 'el-col-12'])
                    for col in prize_cols:
                        prize_span = col.find('span', class_=['prize', 'prize-type'])
                        if prize_span:
                            prize_type_elem = prize_span.find('span', class_=['first', 'second', 'third'])
                            prize_type = (prize_type_elem.text.strip() + " Prize") if prize_type_elem else prize_span.text.strip()
                            number_elem = col.find('b', class_=['number']) or col.find('span', class_=['number'])
                            number = number_elem.text.strip() if number_elem else "N/A"
                            if "1st" in prize_type.lower() or prize_type == "1 Prize":
                                prize_type = "首奖"
                            elif "2nd" in prize_type.lower() or prize_type == "2 Prize":
                                prize_type = "二奖"
                            elif "3rd" in prize_type.lower() or prize_type == "3 Prize":
                                prize_type = "三奖"
                            results[prize_type] = number
                sub_rows = box.find_all('div', class_=['sub-result', 'el-row'])
                for sub_row in sub_rows:
                    result_info = sub_row.find('div', class_=['result-info', 'el-col-24'])
                    if result_info:
                        prize_type_elem = result_info.find('span', class_=['text-info', 'prize-type'])
                        prize_type = prize_type_elem.text.strip() if prize_type_elem else "Unknown Prize"
                        if normalized_name == "sports toto 4d" and prize_type == "Unknown Prize":
                            continue
                        if "Special" in prize_type:
                            prize_type = "特别奖"
                        elif "Consolation" in prize_type:
                            prize_type = "安慰奖"
                        numbers = []
                        number_elems = sub_row.find_all('b', class_=['number']) or sub_row.find_all('span', class_=['number'])
                        for num_elem in number_elems:
                            num_text = num_elem.text.strip()
                            if num_text and num_text != '-':
                                numbers.append(num_text)
                        if numbers:
                            results[prize_type] = numbers
                results = {k: v for k, v in results.items() if "Jackpot" not in k}
                if results:
                    base_path = f"lottery_result/4dnow.net/draw_date/{draw_date}"
                    filename = f"{normalized_name}.json"
                    result_data = {
                        "date": draw_date,
                        "date_yyyymmdd": date_yyyymmdd,
                        "results": results
                    }
                    self.drive_client.upload_file(filename, json.dumps(result_data, ensure_ascii=False, indent=4), base_path)
                    self.all_results[normalized_name] = result_data
            return True
        except Exception as e:
            print(f"解析数据错误: {str(e)}")
            return False

    def load_results_by_date(self, date_str):
        """加载指定日期的结果"""
        results = {}
        date_yyyymmdd = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d")
        base_path = f"lottery_result/4dnow.net/draw_date/{date_str}"
        try:
            files = self.drive_client.list_files(base_path)
            for filename, _ in files:
                if filename.endswith(".json"):
                    operator = filename.replace(".json", "")
                    content = self.drive_client.download_file(filename, base_path)
                    if content:
                        data = json.loads(content)
                        if data.get("date_yyyymmdd") == date_yyyymmdd:
                            results[operator] = data
                        else:
                            print(f"存档日期不匹配: 存档 {data.get('date_yyyymmdd')} != 目标 {date_yyyymmdd}")
        except Exception as e:
            print(f"加载 Google Drive 存档失败: {e}")
        print(f"加载存档完成: {results.keys()}")
        return results

    def get_results(self):
        """获取当前缓存的结果"""
        return self.all_results