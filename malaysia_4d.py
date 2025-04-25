import re
import itertools
from datetime import datetime
import pytz
import random
import string

MYT = pytz.timezone('Asia/Kuala_Lumpur')

class Malaysia4D:
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        self.ticket_count = 0
        self.latest_receipt = ""

    def parse_operators(self, op_str):
        op_map = {
            "1": "Magnum 4D", "2": "Da Ma Cai 1+3D", "3": "SportsToto 4D",
            "4": "Singapore 4D", "8": "Grand Dragon 4D", "9": "9 Lotto"
        }
        return [op_map[num] for num in op_str if num in op_map]

    def validate_bet(self, bet, last_bet_info=None):
        try:
            perm_bet = False
            box_bet = False
            if bet.startswith("&&"):
                box_bet = True
                bet = bet[2:]
            elif bet.startswith("&"):
                perm_bet = True
                bet = bet[1:]
            if "#" in bet:
                parts = bet.split("#")
                num_str = parts[0]
                amounts = parts[1:]
            else:
                num_str = bet
                amounts = []
            num = int(num_str)
            if num < 0 or num > 9999:
                return False, f"号码必须在 0000-9999 之间 (投注: {bet})", None, None, None, None, None, None
            bet_num = f"{num:04d}"
            if not amounts:
                if last_bet_info is None:
                    return False, f"第一组投注必须指定金额 (例如: 2277#1) (投注: {bet})", None, None, None, None, None, None
                big = last_bet_info[0]
                small = last_bet_info[1]
                straight = last_bet_info[2]
                perm_bet = perm_bet or last_bet_info[3]
                box_bet = box_bet or last_bet_info[4]
            else:
                big = 0.0
                small = 0.0
                straight = 0.0
                if len(amounts) >= 1 and amounts[0]:
                    big = float(amounts[0])
                if len(amounts) >= 2 and amounts[1]:
                    small = float(amounts[1])
                if len(amounts) >= 3 and amounts[2]:
                    straight = float(amounts[2])
                if big < 0 or small < 0 or straight < 0:
                    return False, f"大万、小万和直选必须大于等于 0 (投注: {bet})", None, None, None, None, None, None
                if big > 999 or small > 999 or straight > 999:
                    return False, f"大万、小万和直选不能超过 999 (投注: {bet})", None, None, None, None, None, None
                if big == 0 and small == 0 and straight == 0:
                    return False, f"大万、小万和直选不能同时为 0 (投注: {bet})", None, None, None, None, None, None
            return True, "", bet_num, big, small, straight, perm_bet, box_bet
        except ValueError as e:
            return False, f"格式错误: 请输入有效的数字 (例如: 2277#1) (投注: {bet}, 错误: {str(e)})", None, None, None, None, None, None

    def calculate_box_combinations(self, number):
        """计算 Box 投注的组合数"""
        digits = list(number)
        return len(set(''.join(sorted(p)) for p in itertools.permutations(digits)))

    def buy_lottery(self, bets_with_operators, ui):
        """处理购票逻辑"""
        receipt_lines = []
        total_bet = 0.0
        op_code_map = {
            "Magnum 4D": "M", "Da Ma Cai 1+3D": "P", "SportsToto 4D": "T",
            "Singapore 4D": "S", "Grand Dragon 4D": "H", "9 Lotto": "E"
        }
        self.ticket_count += 1
        ticket_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        receipt_lines.append(f"Ticket ID: {ticket_id}")
        receipt_lines.append(f"Date: {datetime.now(MYT).strftime('%Y-%m-%d %H:%M:%S')}")
        receipt_lines.append("=" * 30)

        for operators, bets in bets_with_operators:
            op_codes = ''.join(op_code_map[op] for op in operators)
            receipt_lines.append(f"*{op_codes}")
            last_bet_info = None
            for bet_num, big_bet, small_bet, straight_bet, perm_bet, box_bet in bets:
                bet_str = bet_num
                if perm_bet:
                    bet_str = f"iB({bet_num})"
                elif box_bet:
                    bet_str = f"Box({bet_num})"
                amounts = []
                if big_bet > 0:
                    amounts.append(f"{big_bet:.1f}B")
                if small_bet > 0:
                    amounts.append(f"{small_bet:.1f}S")
                if straight_bet > 0:
                    amounts.append(f"{straight_bet:.1f}A1")
                bet_line = f"{bet_str}={'|'.join(amounts)}"
                receipt_lines.append(bet_line)
                last_bet_info = (big_bet, small_bet, straight_bet, perm_bet, box_bet)
                total_bet += (big_bet + small_bet + straight_bet)
            receipt_lines.append("")
        receipt_lines.append("=" * 30)
        receipt_lines.append(f"P: {total_bet:.2f}")
        receipt_lines.append(f"T: {datetime.now(MYT).strftime('%Y-%m-%d %H:%M:%S')}")
        self.latest_receipt = "\n".join(receipt_lines)
        try:
            self.storage_manager.save_receipt(self.latest_receipt, self.ticket_count)
            if ui:
                ui.success("购票成功！收条已保存。")
        except Exception as e:
            if ui:
                ui.error(f"错误: 无法保存收条 ({str(e)})")