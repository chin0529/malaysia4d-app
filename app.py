import streamlit as st
import os
from google_drive_client import GoogleDriveClient
from storage_manager import StorageManager
from lottery_data_manager import LotteryDataManager
from malaysia_4d import Malaysia4D
from datetime import datetime, timedelta
import pytz
import re
import itertools
from collections import defaultdict

MYT = pytz.timezone('Asia/Kuala_Lumpur')

st.set_page_config(page_title="马来西亚 4D 彩票应用", layout="wide")

# 初始化
drive_client = GoogleDriveClient(
    credentials_json=os.getenv('GOOGLE_CREDENTIALS'),
    parent_folder_id=os.getenv('GOOGLE_DRIVE_FOLDER_ID')
)
storage_manager = StorageManager(drive_client)
data_manager = LotteryDataManager(drive_client)
malaysia_4d = Malaysia4D(storage_manager)

# 辅助函数
def parse_bets(bet_input):
    lines = bet_input.split("\n")
    bets_with_operators = []
    current_ops = None
    current_bets = []
    last_bet_info = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("@"):
            if current_ops and current_bets:
                bets_with_operators.append((current_ops, current_bets))
            op_str = line[1:]
            current_ops = malaysia_4d.parse_operators(op_str)
            current_bets = []
            if not current_ops:
                st.error(f"错误: 无效的运营商选择 ({line})")
                return []
        else:
            valid, error, bet_num, big_bet, small_bet, straight_bet, perm_bet, box_bet = malaysia_4d.validate_bet(line, last_bet_info)
            if not valid:
                st.error(f"错误: {error}")
                return []
            last_bet_info = (big_bet, small_bet, straight_bet, perm_bet, box_bet)
            current_bets.append((bet_num, big_bet, small_bet, straight_bet, perm_bet, box_bet))
    if current_ops and current_bets:
        bets_with_operators.append((current_ops, current_bets))
    return bets_with_operators

# 选项卡
tabs = st.tabs(["购买彩票", "开奖结果", "中奖计算器", "月结单"])

# 购买彩票
with tabs[0]:
    st.header("购买彩票")
    st.write(f"用户名: C23GO3F3 ({malaysia_4d.ticket_count})")
    bet_input = st.text_area("输入投注", height=200, placeholder="@123\n2277#1\n3322\n&8877#1#1\n&&9090#1##1")
    if st.button("购买"):
        if not bet_input.strip():
            st.error("错误: 请输入至少一组投注!")
        else:
            bets_with_operators = parse_bets(bet_input)
            if bets_with_operators:
                malaysia_4d.buy_lottery(bets_with_operators, st)
                st.text_area("收条", malaysia_4d.latest_receipt, height=200)

# 开奖结果
with tabs[1]:
    st.header("开奖结果")
    if st.button("刷新结果"):
        html_content = data_manager.fetch_and_save_data()
        if html_content:
            data_manager.parse_data(html_content)
            results = data_manager.get_results()
            for operator, data in results.items():
                st.subheader(operator)
                st.write(f"日期: {data['date']} (当前: {datetime.now(MYT).strftime('%Y-%m-%d %H:%M')})")
                for prize, numbers in data['results'].items():
                    st.write(f"{prize}: {', '.join(numbers) if isinstance(numbers, list) else numbers}")

# 中奖计算器
with tabs[2]:
    st.header("中奖计算器")
    dates = [(datetime.now(MYT) - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    selected_date = st.selectbox("选择日期", dates)
    if st.button("计算中奖"):
        date_str = selected_date
        all_results = data_manager.load_results_by_date(date_str)
        if not all_results:
            st.error(f"错误: 未找到 {date_str} 的开奖结果")
        else:
            receipts = storage_manager.load_receipts(date_str)
            if not receipts:
                st.error(f"错误: 未找到 {date_str} 的收条")
            else:
                output_text = f"日期: {date_str}\n\n"
                total_winnings = 0.0
                op_code_map = {
                    "M": "magnum 4d", "P": "da ma cai 1+3d", "T": "sports toto 4d",
                    "S": "singapore 4d", "H": "grand dragon 4d", "E": "9 lotto 4d"
                }
                prize_payouts = {
                    "首奖": {"big": 2500, "small": 3500},
                    "二奖": {"big": 1000, "small": 2000},
                    "三奖": {"big": 500, "small": 1000},
                    "特别奖": {"big": 180, "small": 0},
                    "安慰奖": {"big": 60, "small": 0}
                }
                for filename, receipt in receipts:
                    receipt_date = filename.split('_')[0]
                    if receipt_date != datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d"):
                        continue
                    lines = receipt.split("\n")
                    ticket_id = lines[0] if lines else "未知票号"
                    bets = []
                    current_ops = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("*"):
                            op_codes = line[1:]
                            current_ops = [op_code_map[code] for code in op_codes if code in op_code_map]
                        elif "=" in line and not line.startswith("T :") and not line.startswith("P :") and not line.startswith("=="):
                            bet_str = line
                            perm_bet = bet_str.startswith("iB(")
                            box_bet = bet_str.startswith("Box(")
                            if perm_bet:
                                number_match = re.match(r"iB\((\d{4})\)", bet_str)
                                number = number_match.group(1) if number_match else "0000"
                            elif box_bet:
                                number_match = re.match(r"Box\((\d{4})\)", bet_str)
                                number = number_match.group(1) if number_match else "0000"
                            else:
                                number_match = re.match(r"(\d{4})=", bet_str)
                                number = number_match.group(1) if number_match else "0000"
                            amounts = re.findall(r"(\d+\.\d)B|(\d+\.\d)S|(\d+\.\d)A1", bet_str)
                            big = 0.0
                            small = 0.0
                            straight = 0.0
                            for amount in amounts:
                                if amount[0]:
                                    big = float(amount[0])
                                elif amount[1]:
                                    small = float(amount[1])
                                elif amount[2]:
                                    straight = float(amount[2])
                            bets.append((number, big, small, straight, perm_bet, box_bet, current_ops))
                    output_text += f"收条: {filename} ({ticket_id})\n"
                    ticket_winnings = 0.0
                    for number, big, small, straight, perm_bet, box_bet, operators in bets:
                        numbers_to_check = []
                        if perm_bet:
                            digits = list(number)
                            perms = set(''.join(p) for p in itertools.permutations(digits))
                            numbers_to_check.extend(perms)
                        elif box_bet:
                            digits = list(number)
                            perms = set(''.join(sorted(p)) for p in itertools.permutations(digits))
                            numbers_to_check.extend(perms)
                            numbers_to_check = list(set(numbers_to_check))
                        else:
                            numbers_to_check.append(number)
                        box_count = malaysia_4d.calculate_box_combinations(number) if box_bet else 1
                        for op in operators:
                            if op not in all_results:
                                continue
                            op_results = all_results[op]
                            results = op_results["results"]
                            for bet_number in numbers_to_check:
                                for prize, winning_numbers in results.items():
                                    if isinstance(winning_numbers, str):
                                        winning_numbers = [winning_numbers]
                                    if bet_number in winning_numbers:
                                        if perm_bet:
                                            if big > 0 and prize in prize_payouts and prize_payouts[prize]["big"] > 0:
                                                win_amount = big * prize_payouts[prize]["big"]
                                                ticket_winnings += win_amount
                                                output_text += f"  {op} - {bet_number} 中 {prize} (大万: {big:.2f}) 奖金: {win_amount:.2f}\n"
                                            if small > 0 and prize in ["首奖", "二奖", "三奖"] and prize_payouts[prize]["small"] > 0:
                                                win_amount = small * prize_payouts[prize]["small"]
                                                ticket_winnings += win_amount
                                                output_text += f"  {op} - {bet_number} 中 {prize} (小万: {small:.2f}) 奖金: {win_amount:.2f}\n"
                                        elif box_bet:
                                            if big > 0 and prize in prize_payouts and prize_payouts[prize]["big"] > 0:
                                                win_amount = (big * prize_payouts[prize]["big"]) / box_count
                                                ticket_winnings += win_amount
                                                output_text += f"  {op} - {bet_number} 中 {prize} (大万: {big:.2f}) 奖金: {win_amount:.2f}\n"
                                        else:
                                            if big > 0 and prize in prize_payouts and prize_payouts[prize]["big"] > 0:
                                                win_amount = big * prize_payouts[prize]["big"]
                                                ticket_winnings += win_amount
                                                output_text += f"  {op} - {bet_number} 中 {prize} (大万: {big:.2f}) 奖金: {win_amount:.2f}\n"
                                            if small > 0 and prize in ["首奖", "二奖", "三奖"] and prize_payouts[prize]["small"] > 0:
                                                win_amount = small * prize_payouts[prize]["small"]
                                                ticket_winnings += win_amount
                                                output_text += f"  {op} - {bet_number} 中 {prize} (小万: {small:.2f}) 奖金: {win_amount:.2f}\n"
                                            if straight > 0 and prize == "首奖":
                                                win_amount = straight * prize_payouts[prize]["big"]
                                                ticket_winnings += win_amount
                                                output_text += f"  {op} - {bet_number} 中 {prize} (直选: {straight:.2f}) 奖金: {win_amount:.2f}\n"
                    output_text += f"  收条总奖金: {ticket_winnings:.2f}\n\n"
                    total_winnings += ticket_winnings
                output_text += f"总中奖金额: {total_winnings:.2f} MYR"
                st.text_area("中奖结果", output_text, height=400)

# 月结单
with tabs[3]:
    st.header("月结单")
    start_date = st.text_input("起始日期 (YYYY-MM-DD)", (datetime.now(MYT) - timedelta(days=7)).strftime("%Y-%m-%d"))
    end_date = st.text_input("结束日期 (YYYY-MM-DD)", datetime.now(MYT).strftime("%Y-%m-%d"))
    if st.button("生成结单"):
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=MYT)
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=MYT)
            current_date = datetime.now(MYT)
            min_date = current_date - timedelta(days=30)
            if start_date_obj > end_date_obj:
                st.error("错误: 起始日期不能晚于结束日期")
            elif start_date_obj > current_date or end_date_obj > current_date:
                st.error("错误: 日期不能晚于当前日期")
            elif start_date_obj < min_date or end_date_obj < min_date:
                st.error("错误: 日期不能早于30天前")
            else:
                receipts = storage_manager.load_all_receipts()
                filtered_receipts = []
                for filename, receipt in receipts:
                    receipt_date_str = filename.split('_')[0]
                    try:
                        receipt_date = datetime.strptime(receipt_date_str, "%Y%m%d").replace(tzinfo=MYT)
                        if start_date_obj <= receipt_date <= end_date_obj:
                            filtered_receipts.append((filename, receipt))
                    except ValueError:
                        continue
                if not filtered_receipts:
                    st.error(f"错误: 未找到 {start_date} 至 {end_date} 的收条")
                else:
                    monthly_bets = defaultdict(float)
                    monthly_wins = defaultdict(float)
                    weekly_bets = defaultdict(float)
                    weekly_wins = defaultdict(float)
                    op_code_map = {
                        "M": "magnum 4d", "P": "da ma cai 1+3d", "T": "sports toto 4d",
                        "S": "singapore 4d", "H": "grand dragon 4d", "E": "9 lotto 4d"
                    }
                    prize_payouts = {
                        "首奖": {"big": 2500, "small": 3500},
                        "二奖": {"big": 1000, "small": 2000},
                        "三奖": {"big": 500, "small": 1000},
                        "特别奖": {"big": 180, "small": 0},
                        "安慰奖": {"big": 60, "small": 0}
                    }
                    output_text = f"=== 月结单 ({start_date} 至 {end_date}) ===\n\n"
                    for filename, receipt in filtered_receipts:
                        receipt_date = datetime.strptime(filename.split('_')[0], "%Y%m%d").replace(tzinfo=MYT)
                        month_key = receipt_date.strftime("%Y-%m")
                        year, week_num, _ = receipt_date.isocalendar()
                        week_key = f"{year}-W{week_num:02d}"
                        lines = receipt.split("\n")
                        bet_amount = 0.0
                        for line in lines:
                            if line.startswith("P :"):
                                try:
                                    bet_amount = float(line.split(":")[1].strip())
                                    monthly_bets[month_key] += bet_amount
                                    weekly_bets[week_key] += bet_amount
                                except (IndexError, ValueError):
                                    continue
                                break
                        date_str = receipt_date.strftime("%Y-%m-%d")
                        all_results = data_manager.load_results_by_date(date_str)
                        if not all_results:
                            continue
                        bets = []
                        current_ops = []
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("*"):
                                op_codes = line[1:]
                                current_ops = [op_code_map[code] for code in op_codes if code in op_code_map]
                            elif "=" in line and not line.startswith("T :") and not line.startswith("P :") and not line.startswith("=="):
                                bet_str = line
                                perm_bet = bet_str.startswith("iB(")
                                box_bet = bet_str.startswith("Box(")
                                if perm_bet:
                                    number_match = re.match(r"iB\((\d{4})\)", bet_str)
                                    number = number_match.group(1) if number_match else "0000"
                                elif box_bet:
                                    number_match = re.match(r"Box\((\d{4})\)", bet_str)
                                    number = number_match.group(1) if number_match else "0000"
                                else:
                                    number_match = re.match(r"(\d{4})=", bet_str)
                                    number = number_match.group(1) if number_match else "0000"
                                amounts = re.findall(r"(\d+\.\d)B|(\d+\.\d)S|(\d+\.\d)A1", bet_str)
                                big = 0.0
                                small = 0.0
                                straight = 0.0
                                for amount in amounts:
                                    if amount[0]:
                                        big = float(amount[0])
                                    elif amount[1]:
                                        small = float(amount[1])
                                    elif amount[2]:
                                        straight = float(amount[2])
                                bets.append((number, big, small, straight, perm_bet, box_bet, current_ops))
                        ticket_winnings = 0.0
                        for number, big, small, straight, perm_bet, box_bet, operators in bets:
                            numbers_to_check = []
                            if perm_bet:
                                digits = list(number)
                                perms = set(''.join(p) for p in itertools.permutations(digits))
                                numbers_to_check.extend(perms)
                            elif box_bet:
                                digits = list(number)
                                perms = set(''.join(sorted(p)) for p in itertools.permutations(digits))
                                numbers_to_check.extend(perms)
                                numbers_to_check = list(set(numbers_to_check))
                            else:
                                numbers_to_check.append(number)
                            box_count = malaysia_4d.calculate_box_combinations(number) if box_bet else 1
                            for op in operators:
                                if op not in all_results:
                                    continue
                                op_results = all_results[op]
                                results = op_results["results"]
                                for bet_number in numbers_to_check:
                                    for prize, winning_numbers in results.items():
                                        if isinstance(winning_numbers, str):
                                            winning_numbers = [winning_numbers]
                                        if bet_number in winning_numbers:
                                            if perm_bet:
                                                if big > 0 and prize in prize_payouts and prize_payouts[prize]["big"] > 0:
                                                    win_amount = big * prize_payouts[prize]["big"]
                                                    ticket_winnings += win_amount
                                                if small > 0 and prize in ["首奖", "二奖", "三奖"] and prize_payouts[prize]["small"] > 0:
                                                    win_amount = small * prize_payouts[prize]["small"]
                                                    ticket_winnings += win_amount
                                            elif box_bet:
                                                if big > 0 and prize in prize_payouts and prize_payouts[prize]["big"] > 0:
                                                    win_amount = (big * prize_payouts[prize]["big"]) / box_count
                                                    ticket_winnings += win_amount
                                            else:
                                                if big > 0 and prize in prize_payouts and prize_payouts[prize]["big"] > 0:
                                                    win_amount = big * prize_payouts[prize]["big"]
                                                    ticket_winnings += win_amount
                                                if small > 0 and prize in ["首奖", "二奖", "三奖"] and prize_payouts[prize]["small"] > 0:
                                                    win_amount = small * prize_payouts[prize]["small"]
                                                    ticket_winnings += win_amount
                                                if straight > 0 and prize == "首奖":
                                                    win_amount = straight * prize_payouts[prize]["big"]
                                                    ticket_winnings += win_amount
                        monthly_wins[month_key] += ticket_winnings
                        weekly_wins[week_key] += ticket_winnings
                    for month in sorted(monthly_bets.keys()):
                        bets = monthly_bets[month]
                        wins = monthly_wins[month]
                        profit = wins - bets
                        output_text += f"{month}\n"
                        output_text += f"  下注总额: {bets:.2f} MYR\n"
                        output_text += f"  中奖总额: {wins:.2f} MYR\n"
                        output_text += f"  盈利: {profit:.2f} MYR\n\n"
                    output_text += f"=== 周结单 ({start_date} 至 {end_date}) ===\n\n"
                    for week in sorted(weekly_bets.keys()):
                        bets = weekly_bets[week]
                        wins = weekly_wins[week]
                        profit = wins - bets
                        output_text += f"{week}\n"
                        output_text += f"  下注总额: {bets:.2f} MYR\n"
                        output_text += f"  中奖总额: {wins:.2f} MYR\n"
                        output_text += f"  盈利: {profit:.2f} MYR\n\n"
                    st.text_area("结单结果", output_text, height=400)
        except ValueError:
            st.error("错误: 请输入有效日期 (格式: YYYY-MM-DD)")