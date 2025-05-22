# tarot.py - 塔罗牌工具，支持作为AutoGen工具使用

import json
import os
import random
import readline # For better input experience (optional)
import re
from typing_extensions import Annotated

# --- 牌意提取器 ---
class TarotMeaningExtractor:
    """从 tarot_guide_english.md 文件中提取牌意的工具类"""

    def __init__(self, guide_file="tarot_guide_english.md"):
        self.guide_file = guide_file
        self._meanings_cache = {}
        self._load_meanings()

    def _load_meanings(self):
        """加载并缓存所有牌的含义"""
        if not os.path.exists(self.guide_file):
            print(f"Warning: Tarot guide file '{self.guide_file}' not found. Card meanings will not be available.")
            return

        try:
            with open(self.guide_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析Major Arcana
            self._parse_major_arcana(content)
            # 解析Minor Arcana
            self._parse_minor_arcana(content)

            print(f"Loaded meanings for {len(self._meanings_cache)} cards from {self.guide_file}")

            # 检查是否有缺失的牌
            self._check_missing_cards()
        except Exception as e:
            print(f"Error loading tarot guide: {e}")

    def _check_missing_cards(self):
        """检查哪些牌缺失了含义"""
        # 创建所有可能的牌ID列表
        all_possible_ids = []

        # 大阿尔卡纳 (MA00-MA21)
        for i in range(22):
            all_possible_ids.append(f"MA{i:02d}")

        # 小阿尔卡纳
        suits = ['W', 'C', 'S', 'P']  # 权杖、圣杯、宝剑、星币

        # 数字牌 (01-10)
        for suit in suits:
            for i in range(1, 11):
                all_possible_ids.append(f"{suit}{i:02d}")

        # 宫廷牌 (P, N, Q, K)
        court_ranks = ['P', 'N', 'Q', 'K']  # 侍从、骑士、王后、国王
        for suit in suits:
            for rank in court_ranks:
                all_possible_ids.append(f"{suit}{rank}")

        # 检查哪些ID缺失
        missing_ids = [card_id for card_id in all_possible_ids if card_id not in self._meanings_cache]
        if missing_ids:
            print(f"Warning: Missing meanings for {len(missing_ids)} cards: {', '.join(missing_ids)}")

    def _parse_major_arcana(self, content):
        """解析大阿尔卡纳牌意"""
        # 匹配大阿尔卡纳卡片的模式
        major_pattern = r'### (\d+) - (.+?)\n\n#### Visual Description\n(.+?)\n\n#### Upright Meaning\n\*\*Keywords\*\*: (.+?)\n\n(.+?)\n\n#### Reversed Meaning\n\*\*Keywords\*\*: (.+?)\n\n(.+?)(?=\n\n###|\n\n## |$)'

        matches = re.findall(major_pattern, content, re.DOTALL)

        for match in matches:
            number, name, _, up_keywords, up_meaning, rev_keywords, rev_meaning = match

            # 清理文本
            name = name.strip()
            up_keywords = up_keywords.strip()
            up_meaning = up_meaning.strip()
            rev_keywords = rev_keywords.strip()
            rev_meaning = rev_meaning.strip()

            # 生成对应的ID
            card_id = f"MA{number.zfill(2)}"

            self._meanings_cache[card_id] = {
                'name': name,
                'upright': {
                    'keywords': up_keywords,
                    'meaning': up_meaning
                },
                'reversed': {
                    'keywords': rev_keywords,
                    'meaning': rev_meaning
                }
            }

    def _parse_minor_arcana(self, content):
        """解析小阿尔卡纳牌意"""
        # 匹配小阿尔卡纳卡片的模式
        minor_pattern = r'#### (.+?)\n\n##### Visual Description\n(.+?)\n\n##### Upright Meaning\n\*\*Keywords\*\*: (.+?)\n\n(.+?)\n\n##### Reversed Meaning\n\*\*Keywords\*\*: (.+?)\n\n(.+?)(?=\n\n####|\n\n### |$)'

        matches = re.findall(minor_pattern, content, re.DOTALL)

        # 特殊处理 Ace of Wands
        ace_of_wands_pattern = r'#### Ace of Wands\n\n##### Visual Description\n(.+?)\n\n##### Upright Meaning\n\*\*Keywords\*\*: (.+?)\n\n(.+?)\n\n##### Reversed Meaning\n\*\*Keywords\*\*: (.+?)\n\n(.+?)(?=\n\n####|\n\n### |$)'
        ace_match = re.search(ace_of_wands_pattern, content, re.DOTALL)
        if ace_match:
            # 忽略 visual 描述，只使用关键词和含义
            _, up_keywords, up_meaning, rev_keywords, rev_meaning = ace_match.groups()
            self._meanings_cache['W01'] = {
                'name': 'Ace of Wands',
                'upright': {
                    'keywords': up_keywords.strip(),
                    'meaning': up_meaning.strip()
                },
                'reversed': {
                    'keywords': rev_keywords.strip(),
                    'meaning': rev_meaning.strip()
                }
            }
            print("Successfully parsed Ace of Wands")

        for match in matches:
            card_name, _, up_keywords, up_meaning, rev_keywords, rev_meaning = match

            # 清理文本
            card_name = card_name.strip()
            up_keywords = up_keywords.strip()
            up_meaning = up_meaning.strip()
            rev_keywords = rev_keywords.strip()
            rev_meaning = rev_meaning.strip()

            # 跳过已处理的 Ace of Wands
            if "Ace of Wands" in card_name:
                continue

            # 将卡片名称转换为ID
            card_id = self._name_to_id(card_name)

            if card_id:
                self._meanings_cache[card_id] = {
                    'name': card_name,
                    'upright': {
                        'keywords': up_keywords,
                        'meaning': up_meaning
                    },
                    'reversed': {
                        'keywords': rev_keywords,
                        'meaning': rev_meaning
                    }
                }

    def _name_to_id(self, card_name):
        """将卡片名称转换为对应的ID"""
        # 小阿尔卡纳名称到ID的映射
        name_mappings = {
            # Wands
            'Ace of Wands': 'W01', 'Two of Wands': 'W02', 'Three of Wands': 'W03', 'Four of Wands': 'W04',
            'Five of Wands': 'W05', 'Six of Wands': 'W06', 'Seven of Wands': 'W07', 'Eight of Wands': 'W08',
            'Nine of Wands': 'W09', 'Ten of Wands': 'W10', 'Page of Wands': 'WP', 'Knight of Wands': 'WN',
            'Queen of Wands': 'WQ', 'King of Wands': 'WK',

            # Cups
            'Ace of Cups': 'C01', 'Two of Cups': 'C02', 'Three of Cups': 'C03', 'Four of Cups': 'C04',
            'Five of Cups': 'C05', 'Six of Cups': 'C06', 'Seven of Cups': 'C07', 'Eight of Cups': 'C08',
            'Nine of Cups': 'C09', 'Ten of Cups': 'C10', 'Page of Cups': 'CP', 'Knight of Cups': 'CN',
            'Queen of Cups': 'CQ', 'King of Cups': 'CK',

            # Swords
            'Ace of Swords': 'S01', 'Two of Swords': 'S02', 'Three of Swords': 'S03', 'Four of Swords': 'S04',
            'Five of Swords': 'S05', 'Six of Swords': 'S06', 'Seven of Swords': 'S07', 'Eight of Swords': 'S08',
            'Nine of Swords': 'S09', 'Ten of Swords': 'S10', 'Page of Swords': 'SP', 'Knight of Swords': 'SN',
            'Queen of Swords': 'SQ', 'King of Swords': 'SK',

            # Pentacles
            'Ace of Pentacles': 'P01', 'Two of Pentacles': 'P02', 'Three of Pentacles': 'P03', 'Four of Pentacles': 'P04',
            'Five of Pentacles': 'P05', 'Six of Pentacles': 'P06', 'Seven of Pentacles': 'P07', 'Eight of Pentacles': 'P08',
            'Nine of Pentacles': 'P09', 'Ten of Pentacles': 'P10', 'Page of Pentacles': 'PP', 'Knight of Pentacles': 'PN',
            'Queen of Pentacles': 'PQ', 'King of Pentacles': 'PK'
        }

        # 处理特殊情况和部分匹配
        if "Ace of Wands" in card_name:
            return 'W01'

        # 尝试从映射中获取
        result = name_mappings.get(card_name)
        if result:
            return result

        # 如果没有精确匹配，尝试部分匹配
        for key, value in name_mappings.items():
            if key in card_name or card_name in key:
                print(f"Partial match: '{card_name}' -> '{key}' (ID: {value})")
                return value

        # 如果仍然找不到，打印出来以便调试
        print(f"Warning: Could not map card name '{card_name}' to an ID")
        return None

    def get_card_meaning(self, card_id, is_reversed=False):
        """获取指定卡片的含义"""
        if card_id not in self._meanings_cache:
            return None

        card_data = self._meanings_cache[card_id]
        orientation = 'reversed' if is_reversed else 'upright'

        return {
            'name': card_data['name'],
            'keywords': card_data[orientation]['keywords'],
            'meaning': card_data[orientation]['meaning']
        }

# --- 1. 塔罗牌阵定义 ---
# 定义常见的塔罗牌阵及其位置含义
TAROT_SPREADS = {
    "three_card": {
        "name": "三张牌阵 (Three Card Spread)",
        "description": "简单而强大的牌阵，可用于过去-现在-未来，或问题-行动-结果等解读。",
        "positions": [
            {"index": 0, "name": "第一张牌", "meaning": "过去 / 问题 / 原因"},
            {"index": 1, "name": "第二张牌", "meaning": "现在 / 行动 / 过程"},
            {"index": 2, "name": "第三张牌", "meaning": "未来 / 结果 / 建议"}
        ]
    },
    "celtic_cross": {
        "name": "凯尔特十字牌阵 (Celtic Cross)",
        "description": "最经典的塔罗牌阵之一，提供全面的问题分析。",
        "positions": [
            {"index": 0, "name": "中心牌", "meaning": "当前情况 / 问题核心"},
            {"index": 1, "name": "交叉牌", "meaning": "挑战 / 阻碍"},
            {"index": 2, "name": "基础牌", "meaning": "过去基础 / 根源"},
            {"index": 3, "name": "过去牌", "meaning": "正在消退的影响"},
            {"index": 4, "name": "王冠牌", "meaning": "可能的结果 / 目标"},
            {"index": 5, "name": "未来牌", "meaning": "即将到来的影响"},
            {"index": 6, "name": "自我牌", "meaning": "你自己 / 你的态度"},
            {"index": 7, "name": "环境牌", "meaning": "他人影响 / 环境因素"},
            {"index": 8, "name": "希望/恐惧牌", "meaning": "你的希望或恐惧"},
            {"index": 9, "name": "结果牌", "meaning": "最终结果"}
        ]
    },
    "horseshoe": {
        "name": "马蹄牌阵 (Horseshoe Spread)",
        "description": "七张牌阵，适合解决具体问题和寻找解决方案。",
        "positions": [
            {"index": 0, "name": "过去牌", "meaning": "问题的过去 / 起源"},
            {"index": 1, "name": "现在牌", "meaning": "当前情况"},
            {"index": 2, "name": "隐藏影响牌", "meaning": "隐藏的影响 / 未察觉的因素"},
            {"index": 3, "name": "障碍牌", "meaning": "障碍 / 挑战"},
            {"index": 4, "name": "环境牌", "meaning": "周围环境 / 他人影响"},
            {"index": 5, "name": "建议牌", "meaning": "应该采取的行动 / 建议"},
            {"index": 6, "name": "结果牌", "meaning": "最终结果 / 可能的未来"}
        ]
    },
    "relationship": {
        "name": "关系牌阵 (Relationship Spread)",
        "description": "五张牌阵，专注于分析两人关系。",
        "positions": [
            {"index": 0, "name": "自我牌", "meaning": "你在关系中的位置 / 态度"},
            {"index": 1, "name": "伴侣牌", "meaning": "对方在关系中的位置 / 态度"},
            {"index": 2, "name": "关系基础牌", "meaning": "关系的基础 / 纽带"},
            {"index": 3, "name": "挑战牌", "meaning": "关系中的挑战 / 问题"},
            {"index": 4, "name": "结果牌", "meaning": "关系的潜在发展 / 结果"}
        ]
    },
    "career_path": {
        "name": "职业道路牌阵 (Career Path Spread)",
        "description": "六张牌阵，帮助分析职业发展和决策。",
        "positions": [
            {"index": 0, "name": "当前位置牌", "meaning": "你目前的职业状况"},
            {"index": 1, "name": "挑战牌", "meaning": "当前面临的职业挑战"},
            {"index": 2, "name": "机会牌", "meaning": "可能的机会 / 优势"},
            {"index": 3, "name": "行动牌", "meaning": "应该采取的行动"},
            {"index": 4, "name": "长期结果牌", "meaning": "长期职业发展"},
            {"index": 5, "name": "内在态度牌", "meaning": "你对职业的内在态度 / 感受"}
        ]
    }
}

# --- 2. 源牌库定义 (完整版) ---
# 只包含 ID 和 Name。ID用于唯一标识，Name用于显示。
# 正逆位信息将在牌堆操作和缓存中动态产生和存储。
SOURCE_TAROT_CARDS = [
    # --- 大阿尔卡纳 (Major Arcana) - 22张 ---
    {"id": "MA00", "name": "愚者 (The Fool)"},
    {"id": "MA01", "name": "魔术师 (The Magician)"},
    {"id": "MA02", "name": "女祭司 (The High Priestess)"},
    {"id": "MA03", "name": "皇后 (The Empress)"},
    {"id": "MA04", "name": "皇帝 (The Emperor)"},
    {"id": "MA05", "name": "教皇 (The Hierophant)"},
    {"id": "MA06", "name": "恋人 (The Lovers)"},
    {"id": "MA07", "name": "战车 (The Chariot)"},
    {"id": "MA08", "name": "力量 (Strength)"},  # MA08或MA11 根据不同体系
    {"id": "MA09", "name": "隐士 (The Hermit)"},
    {"id": "MA10", "name": "命运之轮 (Wheel of Fortune)"},
    {"id": "MA11", "name": "正义 (Justice)"}, # MA11或MA08
    {"id": "MA12", "name": "倒吊人 (The Hanged Man)"},
    {"id": "MA13", "name": "死神 (Death)"},
    {"id": "MA14", "name": "节制 (Temperance)"},
    {"id": "MA15", "name": "恶魔 (The Devil)"},
    {"id": "MA16", "name": "塔 (The Tower)"},
    {"id": "MA17", "name": "星星 (The Star)"},
    {"id": "MA18", "name": "月亮 (The Moon)"},
    {"id": "MA19", "name": "太阳 (The Sun)"},
    {"id": "MA20", "name": "审判 (Judgement)"},
    {"id": "MA21", "name": "世界 (The World)"},

    # --- 小阿尔卡纳 - 权杖 (Wands) - 14张 ---
    {"id": "W01", "name": "权杖ACE (Ace of Wands)"}, # 修正ID为W01
    {"id": "W02", "name": "权杖二 (Two of Wands)"},
    {"id": "W03", "name": "权杖三 (Three of Wands)"},
    {"id": "W04", "name": "权杖四 (Four of Wands)"},
    {"id": "W05", "name": "权杖五 (Five of Wands)"},
    {"id": "W06", "name": "权杖六 (Six of Wands)"},
    {"id": "W07", "name": "权杖七 (Seven of Wands)"},
    {"id": "W08", "name": "权杖八 (Eight of Wands)"},
    {"id": "W09", "name": "权杖九 (Nine of Wands)"},
    {"id": "W10", "name": "权杖十 (Ten of Wands)"},
    {"id": "WP", "name": "权杖侍从 (Page of Wands)"},
    {"id": "WN", "name": "权杖骑士 (Knight of Wands)"}, # N for kNight
    {"id": "WQ", "name": "权杖王后 (Queen of Wands)"},
    {"id": "WK", "name": "权杖国王 (King of Wands)"},

    # --- 小阿尔卡纳 - 圣杯 (Cups) - 14张 ---
    {"id": "C01", "name": "圣杯ACE (Ace of Cups)"}, # 修正ID为C01
    {"id": "C02", "name": "圣杯二 (Two of Cups)"},
    {"id": "C03", "name": "圣杯三 (Three of Cups)"},
    {"id": "C04", "name": "圣杯四 (Four of Cups)"},
    {"id": "C05", "name": "圣杯五 (Five of Cups)"},
    {"id": "C06", "name": "圣杯六 (Six of Cups)"},
    {"id": "C07", "name": "圣杯七 (Seven of Cups)"},
    {"id": "C08", "name": "圣杯八 (Eight of Cups)"},
    {"id": "C09", "name": "圣杯九 (Nine of Cups)"},
    {"id": "C10", "name": "圣杯十 (Ten of Cups)"},
    {"id": "CP", "name": "圣杯侍从 (Page of Cups)"},
    {"id": "CN", "name": "圣杯骑士 (Knight of Cups)"},
    {"id": "CQ", "name": "圣杯王后 (Queen of Cups)"},
    {"id": "CK", "name": "圣杯国王 (King of Cups)"},

    # --- 小阿尔卡纳 - 宝剑 (Swords) - 14张 ---
    {"id": "S01", "name": "宝剑ACE (Ace of Swords)"}, # 修正ID为S01
    {"id": "S02", "name": "宝剑二 (Two of Swords)"},
    {"id": "S03", "name": "宝剑三 (Three of Swords)"},
    {"id": "S04", "name": "宝剑四 (Four of Swords)"},
    {"id": "S05", "name": "宝剑五 (Five of Swords)"},
    {"id": "S06", "name": "宝剑六 (Six of Swords)"},
    {"id": "S07", "name": "宝剑七 (Seven of Swords)"},
    {"id": "S08", "name": "宝剑八 (Eight of Swords)"},
    {"id": "S09", "name": "宝剑九 (Nine of Swords)"},
    {"id": "S10", "name": "宝剑十 (Ten of Swords)"},
    {"id": "SP", "name": "宝剑侍从 (Page of Swords)"},
    {"id": "SN", "name": "宝剑骑士 (Knight of Swords)"},
    {"id": "SQ", "name": "宝剑王后 (Queen of Swords)"},
    {"id": "SK", "name": "宝剑国王 (King of Swords)"},

    # --- 小阿尔卡纳 - 星币 (Pentacles) - 14张 ---
    {"id": "P01", "name": "星币ACE (Ace of Pentacles)"}, # 修正ID为P01
    {"id": "P02", "name": "星币二 (Two of Pentacles)"},
    {"id": "P03", "name": "星币三 (Three of Pentacles)"},
    {"id": "P04", "name": "星币四 (Four of Pentacles)"},
    {"id": "P05", "name": "星币五 (Five of Pentacles)"},
    {"id": "P06", "name": "星币六 (Six of Pentacles)"},
    {"id": "P07", "name": "星币七 (Seven of Pentacles)"},
    {"id": "P08", "name": "星币八 (Eight of Pentacles)"},
    {"id": "P09", "name": "星币九 (Nine of Pentacles)"},
    {"id": "P10", "name": "星币十 (Ten of Pentacles)"},
    {"id": "PP", "name": "星币侍从 (Page of Pentacles)"},
    {"id": "PN", "name": "星币骑士 (Knight of Pentacles)"},
    {"id": "PQ", "name": "星币王后 (Queen of Pentacles)"},
    {"id": "PK", "name": "星币国王 (King of Pentacles)"},
]

# --- 2. 牌堆中的牌对象 (DeckCard) ---
class DeckCard:
    """代表牌堆中的一张牌及其操作状态。"""
    def __init__(self, card_id: str, is_operationally_reversed: bool = False, is_drawn_in_session: bool = False):
        self.card_id = card_id  # 对应 SOURCE_TAROT_CARDS 中的 id
        self.is_operationally_reversed = is_operationally_reversed # 洗牌操作导致的翻转
        self.is_drawn_in_session = is_drawn_in_session # 本次解读会话中是否被查看过

    def __repr__(self): # 便于调试时查看
        # 在实际显示给用户时，我们会查找name
        return f"DeckCard(id='{self.card_id}', op_rev={self.is_operationally_reversed}, drawn={self.is_drawn_in_session})"

    def to_dict(self): # 用于保存到缓存
        return {
            "card_id": self.card_id,
            "is_operationally_reversed": self.is_operationally_reversed,
            "is_drawn_in_session": self.is_drawn_in_session
        }

    @classmethod
    def from_dict(cls, data: dict): # 用于从缓存加载
        return cls(
            data["card_id"],
            data.get("is_operationally_reversed", False), # 兼容旧格式
            data.get("is_drawn_in_session", False)       # 兼容旧格式
        )

# --- 3. 牌堆操作器 (DeckManipulator) ---
class DeckManipulator:
    def __init__(self, state_file="tarot_deck_state.json"):
        self.source_cards_map = {card["id"]: card for card in SOURCE_TAROT_CARDS}
        if len(self.source_cards_map) != 78:
            # Basic check, can be more robust
            print(f"Warning: Source tarot cards definition count is {len(self.source_cards_map)}, expected 78.")

        self.deck: list[DeckCard] = [] # 当前牌堆，包含 DeckCard 对象
        self.state_file = state_file
        self.next_sequential_draw_index = 0 # 用于顺序查看下一张未被is_drawn_in_session的牌

        # 初始化牌意提取器
        self.meaning_extractor = TarotMeaningExtractor()

        self._load_state()

    def _initialize_fresh_deck(self):
        """用源牌库初始化一个新的、顺序的、所有牌正位的牌堆。"""
        self.deck = []
        for card_def in SOURCE_TAROT_CARDS:
            self.deck.append(DeckCard(card_id=card_def["id"], is_operationally_reversed=False, is_drawn_in_session=False))
        self.next_sequential_draw_index = 0
        print("Initialized a fresh deck.")

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                self.deck = [DeckCard.from_dict(card_data) for card_data in state_data.get("deck_state", [])]
                self.next_sequential_draw_index = state_data.get("next_sequential_draw_index", 0)
                if not self.deck or len(self.deck) != 78: # 如果加载状态不完整，则重新初始化
                    print(f"Warning: Loaded deck state from '{self.state_file}' is incomplete or invalid. Re-initializing.")
                    self._initialize_fresh_deck()
                    self.save_state() # 保存新的初始状态
                else:
                    print(f"Loaded deck state from '{self.state_file}'.")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading state file '{self.state_file}': {e}. Initializing a fresh deck.")
                self._initialize_fresh_deck()
                self.save_state()
        else:
            print(f"No state file found at '{self.state_file}'. Initializing a fresh deck.")
            self._initialize_fresh_deck()
            self.save_state()

    def save_state(self):
        state_data = {
            "deck_state": [card.to_dict() for card in self.deck],
            "next_sequential_draw_index": self.next_sequential_draw_index
        }
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2)
            # print(f"Deck state saved to '{self.state_file}'.")
        except IOError as e:
            print(f"Error saving state to '{self.state_file}': {e}")

    # --- 预定义的牌堆操作指令 ---
    def op_cut_deck_at_index(self, index: int):
        """将牌堆在指定索引处切开，并将两部分交换位置。"""
        if not 0 <= index < len(self.deck):
            print(f"Error: Cut index {index} is out of bounds (0-{len(self.deck)-1}).")
            return False
        part1 = self.deck[:index]
        part2 = self.deck[index:]
        self.deck = part2 + part1
        print(f"Deck cut at index {index}.")
        return True

    def op_invert_segment(self, start_index: int, end_index: int):
        """颠倒指定段牌的顺序，并翻转这些牌的 is_operationally_reversed 状态。"""
        if not (0 <= start_index <= end_index < len(self.deck)):
            print(f"Error: Invalid segment indices [{start_index}-{end_index}].")
            return False

        segment_to_invert = self.deck[start_index : end_index + 1]
        segment_to_invert.reverse() # 颠倒顺序
        for card in segment_to_invert:
            card.is_operationally_reversed = not card.is_operationally_reversed # 翻转状态

        self.deck = self.deck[:start_index] + segment_to_invert + self.deck[end_index + 1:]
        print(f"Segment [{start_index}-{end_index}] inverted and flipped.")
        return True

    def op_three_pile_shuffle_and_reassemble(self, pile_order: list[int], invert_piles_flags: list[bool]):
        """
        将牌堆分成大致相等的三堆，根据invert_flags翻转某些堆，然后按pile_order重组。
        pile_order: [0,1,2] 的排列, e.g., [1,0,2] 表示中间堆放最上面，然后是第一堆，最后是第三堆。
        invert_piles_flags: [bool, bool, bool], e.g., [False, True, False] 表示翻转中间那堆。
        """
        if len(self.deck) != 78:
            print("Error: This operation expects a full 78-card deck.")
            return False
        if len(pile_order) != 3 or sorted(pile_order) != [0,1,2] or len(invert_piles_flags) != 3:
            print("Error: Invalid pile_order or invert_piles_flags.")
            return False

        pile_size = len(self.deck) // 3 # 26
        piles = [
            self.deck[0 : pile_size],
            self.deck[pile_size : 2 * pile_size],
            self.deck[2 * pile_size :]
        ]

        # 翻转指定的堆
        for i in range(3):
            if invert_piles_flags[i]:
                piles[i].reverse() # 颠倒顺序
                for card in piles[i]:
                    card.is_operationally_reversed = not card.is_operationally_reversed # 翻转状态

        # 按指定顺序重组
        new_deck = []
        for pile_idx in pile_order:
            new_deck.extend(piles[pile_idx])
        self.deck = new_deck
        print(f"Three-pile shuffle complete. Order: {pile_order}, Inversions: {invert_piles_flags}.")
        return True

    def op_random_shuffle(self):
        """简单的随机洗牌，每张牌随机确定操作翻转状态。"""
        random.shuffle(self.deck)
        for card in self.deck:
            card.is_operationally_reversed = random.choice([True, False])
        print("Deck randomly shuffled and orientations randomized.")
        return True

    def op_perfect_shuffle(self, in_shuffle=True):
        """
        完美洗牌（Perfect Shuffle）。
        in_shuffle=True: 内洗牌（In Shuffle）- 第一张牌保持在顶部
        in_shuffle=False: 外洗牌（Out Shuffle）- 第一张牌变成第二张
        """
        if len(self.deck) % 2 != 0:
            print("Warning: Perfect shuffle works best with even number of cards.")

        mid = len(self.deck) // 2
        first_half = self.deck[:mid]
        second_half = self.deck[mid:]

        new_deck = []
        for i in range(max(len(first_half), len(second_half))):
            if in_shuffle:
                # 内洗牌：第二堆的牌先插入
                if i < len(second_half):
                    new_deck.append(second_half[i])
                if i < len(first_half):
                    new_deck.append(first_half[i])
            else:
                # 外洗牌：第一堆的牌先插入
                if i < len(first_half):
                    new_deck.append(first_half[i])
                if i < len(second_half):
                    new_deck.append(second_half[i])

        self.deck = new_deck
        shuffle_type = "内洗牌 (In Shuffle)" if in_shuffle else "外洗牌 (Out Shuffle)"
        print(f"完美洗牌完成，类型: {shuffle_type}")
        return True

    def op_overhand_shuffle(self, num_cuts=5):
        """
        叠切洗牌（Overhand Shuffle）。
        从牌堆顶部取下一小叠牌，然后放到新牌堆的顶部，重复多次。
        num_cuts: 切牌次数
        """
        if num_cuts <= 0:
            print("Error: Number of cuts must be positive.")
            return False

        new_deck = []
        remaining_deck = self.deck.copy()

        for _ in range(num_cuts):
            if not remaining_deck:
                break

            # 随机决定切下多少牌（约10-30%）
            cut_size = max(1, int(len(remaining_deck) * random.uniform(0.1, 0.3)))
            cut_size = min(cut_size, len(remaining_deck))

            # 从剩余牌堆顶部切下一小叠
            cut_cards = remaining_deck[:cut_size]
            remaining_deck = remaining_deck[cut_size:]

            # 放到新牌堆顶部
            new_deck = cut_cards + new_deck

        # 添加剩余的牌
        if remaining_deck:
            new_deck = remaining_deck + new_deck

        self.deck = new_deck
        print(f"叠切洗牌完成，执行了 {num_cuts} 次切牌。")
        return True

    def op_hindu_shuffle(self, num_cuts=8):
        """
        印度式洗牌（Hindu Shuffle）。
        从牌堆底部抽出一小叠牌，然后放到新牌堆的顶部，重复多次。
        num_cuts: 切牌次数
        """
        if num_cuts <= 0:
            print("Error: Number of cuts must be positive.")
            return False

        new_deck = []
        remaining_deck = self.deck.copy()

        for _ in range(num_cuts):
            if not remaining_deck:
                break

            # 随机决定从底部切下多少牌（约10-30%）
            cut_size = max(1, int(len(remaining_deck) * random.uniform(0.1, 0.3)))
            cut_size = min(cut_size, len(remaining_deck))

            # 从剩余牌堆底部切下一小叠
            cut_cards = remaining_deck[-cut_size:]
            remaining_deck = remaining_deck[:-cut_size]

            # 放到新牌堆顶部
            new_deck = cut_cards + new_deck

        # 添加剩余的牌
        if remaining_deck:
            new_deck = remaining_deck + new_deck

        self.deck = new_deck
        print(f"印度式洗牌完成，执行了 {num_cuts} 次切牌。")
        return True

    def op_all_upright(self):
        """将所有牌设置为正位。"""
        for card in self.deck:
            card.is_operationally_reversed = False
        print("所有牌已设置为正位。")
        return True

    def op_all_reversed(self):
        """将所有牌设置为逆位。"""
        for card in self.deck:
            card.is_operationally_reversed = True
        print("所有牌已设置为逆位。")
        return True

    def op_randomize_orientation(self):
        """随机化所有牌的正逆位，但不改变顺序。"""
        for card in self.deck:
            card.is_operationally_reversed = random.choice([True, False])
        print("所有牌的正逆位已随机化。")
        return True

    @staticmethod
    def get_custom_commands_help() -> str:
        """返回自定义指令的帮助信息。"""
        help_text = """
支持的指令格式:
- CUT N: 在索引N处切牌
- INVERT N M: 翻转索引N到M的牌
- SHUFFLE: 完全随机洗牌
- PERFECT_IN: 完美洗牌(内洗)
- PERFECT_OUT: 完美洗牌(外洗)
- OVERHAND N: 叠切洗牌N次
- HINDU N: 印度式洗牌N次
- ALL_UP: 所有牌设为正位
- ALL_DOWN: 所有牌设为逆位
- RANDOM_ORIENT: 随机化所有牌的正逆位
- TAKE_TOP N TO_BOTTOM: 将顶部N张牌移到底部
- TAKE_BOTTOM N TO_TOP: 将底部N张牌移到顶部
- HELP: 显示此帮助信息

指令之间用分号(;)分隔。

例如:
CUT 30; INVERT 10 20; SHUFFLE; TAKE_TOP 5 TO_BOTTOM
"""
        return help_text

    def parse_and_execute_custom_commands(self, command_string: str) -> bool:
        """
        解析并执行用户自定义的洗牌指令序列。

        支持的指令格式:
        - CUT N: 在索引N处切牌
        - INVERT N M: 翻转索引N到M的牌
        - SHUFFLE: 完全随机洗牌
        - PERFECT_IN: 完美洗牌(内洗)
        - PERFECT_OUT: 完美洗牌(外洗)
        - OVERHAND N: 叠切洗牌N次
        - HINDU N: 印度式洗牌N次
        - ALL_UP: 所有牌设为正位
        - ALL_DOWN: 所有牌设为逆位
        - RANDOM_ORIENT: 随机化所有牌的正逆位
        - TAKE_TOP N TO_BOTTOM: 将顶部N张牌移到底部
        - TAKE_BOTTOM N TO_TOP: 将底部N张牌移到顶部
        - HELP: 显示帮助信息

        指令之间用分号(;)分隔。

        例如:
        "CUT 30; INVERT 10 20; SHUFFLE; TAKE_TOP 5 TO_BOTTOM"
        """
        if not command_string.strip():
            print("没有输入任何指令。")
            return False

        # 分割指令序列
        commands = [cmd.strip() for cmd in command_string.split(';')]
        success = True

        for cmd in commands:
            if not cmd:
                continue

            parts = cmd.split()
            if not parts:
                continue

            operation = parts[0].upper()

            try:
                if operation == "HELP":
                    print(self.get_custom_commands_help())
                    continue

                elif operation == "CUT" and len(parts) >= 2:
                    index = int(parts[1])
                    success = success and self.op_cut_deck_at_index(index)

                elif operation == "INVERT" and len(parts) >= 3:
                    start = int(parts[1])
                    end = int(parts[2])
                    success = success and self.op_invert_segment(start, end)

                elif operation == "SHUFFLE":
                    success = success and self.op_random_shuffle()

                elif operation == "PERFECT_IN":
                    success = success and self.op_perfect_shuffle(in_shuffle=True)

                elif operation == "PERFECT_OUT":
                    success = success and self.op_perfect_shuffle(in_shuffle=False)

                elif operation == "OVERHAND" and len(parts) >= 2:
                    num_cuts = int(parts[1])
                    success = success and self.op_overhand_shuffle(num_cuts)

                elif operation == "HINDU" and len(parts) >= 2:
                    num_cuts = int(parts[1])
                    success = success and self.op_hindu_shuffle(num_cuts)

                elif operation == "ALL_UP":
                    success = success and self.op_all_upright()

                elif operation == "ALL_DOWN":
                    success = success and self.op_all_reversed()

                elif operation == "RANDOM_ORIENT":
                    success = success and self.op_randomize_orientation()

                elif operation == "TAKE_TOP" and len(parts) >= 3 and parts[2].upper() == "TO_BOTTOM":
                    count = int(parts[1])
                    if 0 < count < len(self.deck):
                        top_cards = self.deck[:count]
                        self.deck = self.deck[count:] + top_cards
                        print(f"将顶部 {count} 张牌移到底部。")
                    else:
                        print(f"错误: 无效的牌数 {count}。")
                        success = False

                elif operation == "TAKE_BOTTOM" and len(parts) >= 3 and parts[2].upper() == "TO_TOP":
                    count = int(parts[1])
                    if 0 < count < len(self.deck):
                        bottom_cards = self.deck[-count:]
                        self.deck = bottom_cards + self.deck[:-count]
                        print(f"将底部 {count} 张牌移到顶部。")
                    else:
                        print(f"错误: 无效的牌数 {count}。")
                        success = False

                else:
                    print(f"错误: 未知或格式不正确的指令 '{cmd}'")
                    success = False

            except (ValueError, IndexError) as e:
                print(f"错误: 解析指令 '{cmd}' 时出错: {e}")
                success = False

        return success

    def reset_draw_status_for_session(self):
        """重置所有牌的is_drawn_in_session状态，用于开始新的解读会话。"""
        for card in self.deck:
            card.is_drawn_in_session = False
        self.next_sequential_draw_index = 0
        print("All 'drawn in session' flags reset.")
        self.save_state() # 保存这个重置


    # --- 查看/抽牌逻辑 ---
    def view_card_at_index(self, index: int) -> dict | None:
        """
        查看指定索引处的牌。
        返回包含牌名、正逆位、是否已查看过、牌意等信息的字典，或 None。
        """
        if not 0 <= index < len(self.deck):
            print(f"Error: Index {index} is out of bounds.")
            return None

        deck_card_obj = self.deck[index]
        card_definition = self.source_cards_map.get(deck_card_obj.card_id)

        if not card_definition:
            print(f"Error: Card ID '{deck_card_obj.card_id}' not found in source definitions.")
            return None # Should not happen if data is consistent

        # 最终正逆位：这里假设源牌库都是正位。如果源牌库有初始逆位，需要XOR
        # final_is_reversed = source_initial_reversed XOR deck_card_obj.is_operationally_reversed
        final_is_reversed = deck_card_obj.is_operationally_reversed # 简化：假设源牌都是正位

        card_name = card_definition["name"]
        was_previously_drawn = deck_card_obj.is_drawn_in_session

        # 获取牌意
        card_meaning = self.meaning_extractor.get_card_meaning(deck_card_obj.card_id, final_is_reversed)

        # 标记为本次会话已查看
        deck_card_obj.is_drawn_in_session = True
        self.save_state() # 保存抽牌状态

        return {
            'name': card_name,
            'is_reversed': final_is_reversed,
            'was_previously_drawn': was_previously_drawn,
            'card_id': deck_card_obj.card_id,
            'meaning': card_meaning
        }

    def view_next_sequential_cards(self, count=1) -> list[dict]:
        """按顺序查看接下来 'count' 张未被标记为 is_drawn_in_session 的牌。"""
        found_cards_info = []
        current_search_idx = self.next_sequential_draw_index
        cards_found_count = 0

        while cards_found_count < count and current_search_idx < len(self.deck):
            if not self.deck[current_search_idx].is_drawn_in_session:
                # "查看"这张牌
                card_info = self.view_card_at_index(current_search_idx) # view_card_at_index会标记is_drawn
                if card_info: # card_info is now a dict
                    found_cards_info.append(card_info)
                    cards_found_count += 1
            current_search_idx += 1

        self.next_sequential_draw_index = current_search_idx # 更新下次顺序抽牌的起始点
        self.save_state()
        return found_cards_info

    def draw_spread(self, spread_key: str) -> list[tuple[dict, dict]]:
        """
        根据指定的牌阵抽取相应数量的牌。
        返回一个列表，每个元素包含：
        - 牌信息字典 (包含name, is_reversed, was_drawn_before, meaning等)
        - 牌阵位置信息字典 {"name": "位置名", "meaning": "位置含义"}
        """
        if spread_key not in TAROT_SPREADS:
            print(f"错误: 未知的牌阵类型 '{spread_key}'")
            return []

        spread = TAROT_SPREADS[spread_key]

        # 先洗牌
        print(f"为 {spread['name']} 洗牌...")
        self.op_random_shuffle()

        # 抽取牌阵所需的牌
        cards_info = []
        for position in spread["positions"]:
            # 找到下一张未抽过的牌
            found = False
            for idx in range(len(self.deck)):
                if not self.deck[idx].is_drawn_in_session:
                    card_info = self.view_card_at_index(idx)
                    if card_info:
                        cards_info.append((card_info, position))
                        found = True
                        break

            if not found:
                print("警告: 没有足够的未抽过的牌来完成牌阵。")
                break

        self.save_state()
        return cards_info

# --- 4. 命令行界面 (CLI) ---
def display_card_info(card_info: dict, position_info=None):
    """显示牌的详细信息，包括牌意"""
    name = card_info['name']
    is_reversed = card_info['is_reversed']
    was_drawn_before = card_info['was_previously_drawn']
    meaning = card_info.get('meaning')

    orientation = "逆位 (Reversed)" if is_reversed else "正位 (Upright)"
    previously_drawn_note = " (此牌在本会话中已被查看过)" if was_drawn_before else ""

    if position_info:
        print(f"\n{position_info['name']} - {position_info['meaning']}")
        print(f"牌面: {name} - {orientation}{previously_drawn_note}")
    else:
        print(f"牌面: {name} - {orientation}{previously_drawn_note}")

    # 显示牌意
    if meaning:
        print(f"关键词: {meaning['keywords']}")
        print(f"牌意: {meaning['meaning']}")
    else:
        print("牌意: 暂无相关信息")

def cli_main():
    print("欢迎来到命令行塔罗牌解读工具！")
    deck_manipulator = DeckManipulator()

    while True:
        print("\n" + "="*30)
        user_question = input("请输入你想要问的问题 (或输入 'q' 退出): ")
        if user_question.lower() == 'q':
            break

        # 在每次新提问时，可以选择重置“本会话已抽”标记
        # 这允许对同一个问题，如果用户想重新抽“未抽过”的牌，可以实现
        # 或者，如果想保持整个CLI运行期间的“已抽”状态，则不重置
        reset_choice = input("开始新的解读会话（重置'已抽'标记）？(y/n, 默认n): ").lower()
        if reset_choice == 'y':
            deck_manipulator.reset_draw_status_for_session()

        print("\n--- 牌堆操作选项 ---")
        print("基础操作:")
        print("1. 使用预定义操作：三堆洗牌与重组")
        print("2. 使用预定义操作：随机切牌")
        print("3. 使用预定义操作：翻转牌堆中间1/3部分")
        print("4. 使用预定义操作：完全随机洗牌（包括正逆位）")

        print("\n高级洗牌操作:")
        print("5. 完美洗牌 - 内洗牌 (In Shuffle)")
        print("6. 完美洗牌 - 外洗牌 (Out Shuffle)")
        print("7. 叠切洗牌 (Overhand Shuffle)")
        print("8. 印度式洗牌 (Hindu Shuffle)")

        print("\n正逆位操作:")
        print("9. 将所有牌设置为正位")
        print("10. 将所有牌设置为逆位")
        print("11. 随机化所有牌的正逆位（不改变顺序）")

        print("\n查看与其他操作:")
        print("12. 查看当前牌堆顶牌 (顺序查看，跳过已抽)")
        print("13. 指定查看牌堆中第 N 张牌")
        print("14. 自定义操作序列 (高级)")
        print("15. 重置牌堆为初始状态 (所有牌顺序，正位)")
        print("0. 完成牌堆操作，开始抽牌/查看")

        # 牌堆操作循环
        while True:
            op_choice = input("选择操作 (或 '0' 完成操作): ")
            perform_save = True # 大部分操作后都保存

            if op_choice == '1':
                # 示例：三堆洗牌，中间堆翻转，按2-0-1顺序叠回
                # 用户可以被提示输入这些参数
                print("执行三堆洗牌：中间堆翻转，顺序为 第二堆-第一堆-第三堆")
                deck_manipulator.op_three_pile_shuffle_and_reassemble(
                    pile_order=[1,0,2],
                    invert_piles_flags=[False, True, False]
                )
            elif op_choice == '2':
                cut_idx = random.randint(10, len(deck_manipulator.deck) - 11) # 随机切牌点
                print(f"执行随机切牌，切点: {cut_idx}")
                deck_manipulator.op_cut_deck_at_index(cut_idx)
            elif op_choice == '3':
                start = len(deck_manipulator.deck) // 3
                end = start + (len(deck_manipulator.deck) // 3) -1
                print(f"翻转牌堆中间1/3部分 (索引 {start}-{end})")
                deck_manipulator.op_invert_segment(start, end)
            elif op_choice == '4':
                deck_manipulator.op_random_shuffle()

            # 高级洗牌操作
            elif op_choice == '5':
                deck_manipulator.op_perfect_shuffle(in_shuffle=True)
            elif op_choice == '6':
                deck_manipulator.op_perfect_shuffle(in_shuffle=False)
            elif op_choice == '7':
                num_cuts = 5
                try:
                    num_cuts_str = input("请输入叠切次数 (默认5): ")
                    if num_cuts_str.strip():
                        num_cuts = int(num_cuts_str)
                except ValueError:
                    print("使用默认叠切次数: 5")
                deck_manipulator.op_overhand_shuffle(num_cuts=num_cuts)
            elif op_choice == '8':
                num_cuts = 8
                try:
                    num_cuts_str = input("请输入印度式洗牌切牌次数 (默认8): ")
                    if num_cuts_str.strip():
                        num_cuts = int(num_cuts_str)
                except ValueError:
                    print("使用默认切牌次数: 8")
                deck_manipulator.op_hindu_shuffle(num_cuts=num_cuts)

            # 正逆位操作
            elif op_choice == '9':
                deck_manipulator.op_all_upright()
            elif op_choice == '10':
                deck_manipulator.op_all_reversed()
            elif op_choice == '11':
                deck_manipulator.op_randomize_orientation()

            # 查看与其他操作
            elif op_choice == '12':
                print("\n--- 查看牌堆顶牌 (顺序) ---")
                cards_info = deck_manipulator.view_next_sequential_cards(1)
                if cards_info:
                    display_card_info(cards_info[0])
                else:
                    print("没有更多未查看的牌可以按顺序抽取了。")
                perform_save = False # view_next_sequential_cards 内部已保存
            elif op_choice == '13':
                try:
                    idx_str = input(f"请输入要查看的牌的索引 (0-{len(deck_manipulator.deck)-1}): ")
                    idx_to_view = int(idx_str)
                    card_info = deck_manipulator.view_card_at_index(idx_to_view)
                    if card_info:
                        display_card_info(card_info)
                except ValueError:
                    print("无效的索引输入。")
                perform_save = False # view_card_at_index 内部已保存
            elif op_choice == '14':
                print("\n--- 自定义操作序列 ---")
                print(deck_manipulator.get_custom_commands_help())

                custom_commands = input("\n请输入自定义操作序列: ")
                if custom_commands.strip():
                    success = deck_manipulator.parse_and_execute_custom_commands(custom_commands)
                    if success:
                        print("自定义操作序列执行成功。")
                    else:
                        print("自定义操作序列执行过程中出现错误。")
                else:
                    print("未输入任何指令，操作已取消。")
                    perform_save = False
            elif op_choice == '15':
                confirm_reset = input("确定要重置整个牌堆到初始状态吗？(y/n): ").lower()
                if confirm_reset == 'y':
                    deck_manipulator._initialize_fresh_deck() # 重置
                    print("牌堆已重置为初始状态。")
            elif op_choice == '0':
                print("牌堆操作完成。")
                break # 退出操作循环
            else:
                print("无效选项。")
                perform_save = False

            if perform_save:
                deck_manipulator.save_state() # 保存操作后的牌堆状态

        # --- 牌堆操作完成后，根据问题抽牌/查看 ---
        print("\n--- 为问题 '{}' 抽牌/查看 ---".format(user_question))

        # 选择抽牌方式：牌阵或自由抽牌
        print("\n选择抽牌方式:")
        print("1. 使用塔罗牌阵")
        print("2. 自由抽牌")

        draw_choice = input("请选择 (1/2): ").strip()

        # 使用牌阵
        if draw_choice == '1':
            print("\n可用的塔罗牌阵:")
            spread_keys = list(TAROT_SPREADS.keys())
            for i, key in enumerate(spread_keys, 1):
                spread = TAROT_SPREADS[key]
                print(f"{i}. {spread['name']} - {spread['description']}")

            try:
                spread_idx = int(input("\n请选择牌阵编号: ").strip()) - 1
                if 0 <= spread_idx < len(TAROT_SPREADS):
                    spread_key = list(TAROT_SPREADS.keys())[spread_idx]
                    spread = TAROT_SPREADS[spread_key]

                    print(f"\n您选择了: {spread['name']}")
                    print(f"描述: {spread['description']}")
                    print(f"需要 {len(spread['positions'])} 张牌")

                    confirm = input("确认使用此牌阵? (y/n): ").lower()
                    if confirm == 'y':
                        # 抽取牌阵
                        spread_cards = deck_manipulator.draw_spread(spread_key)

                        # 显示牌阵结果
                        if spread_cards:
                            print(f"\n--- {spread['name']} 结果 ---")
                            for card_info, position in spread_cards:
                                display_card_info(card_info, position)

                            print(f"\n牌阵解读完成。请根据牌面含义和位置进行综合分析。")
                        else:
                            print("抽牌失败，请重试。")
                else:
                    print("无效的牌阵编号。")
            except ValueError:
                print("无效的输入。")

        # 自由抽牌
        else:
            while True:
                draw_method = input("选择查看方式: (s)顺序查看下一张, (i)指定索引查看, (d)完成本次问题查看: ").lower()
                if draw_method == 's':
                    cards_info = deck_manipulator.view_next_sequential_cards(1)
                    if cards_info:
                        display_card_info(cards_info[0])
                    else:
                        print("没有更多未查看的牌可以按顺序抽取了。")
                elif draw_method == 'i':
                    try:
                        idx_str = input(f"请输入要查看的牌的索引 (0-{len(deck_manipulator.deck)-1}): ")
                        idx_to_view = int(idx_str)
                        card_info = deck_manipulator.view_card_at_index(idx_to_view)
                        if card_info:
                            display_card_info(card_info)
                    except ValueError:
                        print("无效的索引输入。")
                elif draw_method == 'd':
                    print(f"对问题 '{user_question}' 的查看结束。")
                    break
                else:
                    print("无效选项。")

    print("感谢使用塔罗牌工具！")

# --- 5. AutoGen 工具函数 ---

def format_card_info_text(card_info, position_info=None):
    """将牌信息格式化为文本，用于AutoGen工具返回"""
    name = card_info['name']
    is_reversed = card_info['is_reversed']
    was_drawn_before = card_info['was_previously_drawn']
    meaning = card_info.get('meaning')

    orientation = "逆位 (Reversed)" if is_reversed else "正位 (Upright)"
    previously_drawn_note = " (此牌在本会话中已被查看过)" if was_drawn_before else ""

    result = ""
    if position_info:
        result += f"{position_info['name']} - {position_info['meaning']}\n"

    result += f"牌面: {name} - {orientation}{previously_drawn_note}\n"

    # 添加牌意信息
    if meaning:
        result += f"关键词: {meaning['keywords']}\n"
        result += f"牌意: {meaning['meaning']}"
    else:
        result += "牌意: 暂无相关信息"

    return result

def list_tarot_spreads() -> str:
    """
    列出所有可用的塔罗牌阵及其描述。

    此工具返回所有预定义的塔罗牌阵信息，包括名称、描述和所需牌数。

    Returns:
        包含所有可用塔罗牌阵信息的字符串
    """
    result = "可用的塔罗牌阵:\n\n"

    for key, spread in TAROT_SPREADS.items():
        result += f"【{spread['name']}】\n"
        result += f"- 代码: {key}\n"
        result += f"- 描述: {spread['description']}\n"
        result += f"- 所需牌数: {len(spread['positions'])}张\n"
        result += f"- 位置: {', '.join([pos['name'] for pos in spread['positions']])}\n\n"

    return result

def list_shuffle_methods() -> str:
    """
    列出所有可用的洗牌方法及其描述。

    此工具返回所有预定义的洗牌方法信息，包括名称和简短描述。

    Returns:
        包含所有可用洗牌方法信息的字符串
    """
    methods = [
        {"name": "随机洗牌 (Random Shuffle)", "code": "random", "description": "完全随机洗牌，每张牌随机确定正逆位。"},
        {"name": "完美洗牌-内洗 (Perfect In-Shuffle)", "code": "perfect_in", "description": "将牌堆分成两半，然后交替插入，第二堆的牌先插入。"},
        {"name": "完美洗牌-外洗 (Perfect Out-Shuffle)", "code": "perfect_out", "description": "将牌堆分成两半，然后交替插入，第一堆的牌先插入。"},
        {"name": "叠切洗牌 (Overhand Shuffle)", "code": "overhand", "description": "从牌堆顶部取下一小叠牌，然后放到新牌堆的顶部，重复多次。"},
        {"name": "印度式洗牌 (Hindu Shuffle)", "code": "hindu", "description": "从牌堆底部抽出一小叠牌，然后放到新牌堆的顶部，重复多次。"},
        {"name": "三堆洗牌 (Three-Pile Shuffle)", "code": "three_pile", "description": "将牌堆分成三堆，可选择翻转某些堆，然后按指定顺序重组。"},
        {"name": "自定义指令序列 (Custom Commands)", "code": "custom", "description": "使用自定义指令序列执行复杂的洗牌操作。"}
    ]

    result = "可用的洗牌方法:\n\n"

    for method in methods:
        result += f"【{method['name']}】\n"
        result += f"- 代码: {method['code']}\n"
        result += f"- 描述: {method['description']}\n\n"

    result += "自定义指令格式参考:\n"
    result += DeckManipulator.get_custom_commands_help()

    return result

def shuffle_tarot_deck(
    method: Annotated[str, "洗牌方法代码，可选值: random, perfect_in, perfect_out, overhand, hindu, three_pile, custom"],
    custom_commands: Annotated[str, "当method为custom时使用的自定义指令序列，例如: 'CUT 30; SHUFFLE'"] = "",
    num_cuts: Annotated[int, "叠切洗牌或印度式洗牌的切牌次数"] = 5,
    reset_session: Annotated[bool, "是否重置本次会话的抽牌状态"] = True
) -> str:
    """
    使用指定的方法洗牌。

    此工具使用指定的洗牌方法对塔罗牌进行洗牌。可以选择是否重置会话状态。

    Args:
        method: 洗牌方法代码，可选值: random, perfect_in, perfect_out, overhand, hindu, three_pile, custom
        custom_commands: 当method为custom时使用的自定义指令序列
        num_cuts: 叠切洗牌或印度式洗牌的切牌次数
        reset_session: 是否重置本次会话的抽牌状态

    Returns:
        洗牌结果描述
    """
    deck_manipulator = DeckManipulator()

    if reset_session:
        deck_manipulator.reset_draw_status_for_session()
        result = "已重置会话抽牌状态。\n"
    else:
        result = ""

    if method == "random":
        deck_manipulator.op_random_shuffle()
        result += "已完成随机洗牌，每张牌的正逆位已随机确定。"

    elif method == "perfect_in":
        deck_manipulator.op_perfect_shuffle(in_shuffle=True)
        result += "已完成完美洗牌(内洗)。"

    elif method == "perfect_out":
        deck_manipulator.op_perfect_shuffle(in_shuffle=False)
        result += "已完成完美洗牌(外洗)。"

    elif method == "overhand":
        deck_manipulator.op_overhand_shuffle(num_cuts=num_cuts)
        result += f"已完成叠切洗牌，执行了{num_cuts}次切牌。"

    elif method == "hindu":
        deck_manipulator.op_hindu_shuffle(num_cuts=num_cuts)
        result += f"已完成印度式洗牌，执行了{num_cuts}次切牌。"

    elif method == "three_pile":
        # 默认使用中间堆翻转，按2-0-1顺序叠回的三堆洗牌
        deck_manipulator.op_three_pile_shuffle_and_reassemble(
            pile_order=[1,0,2],
            invert_piles_flags=[False, True, False]
        )
        result += "已完成三堆洗牌：中间堆翻转，顺序为 第二堆-第一堆-第三堆。"

    elif method == "custom":
        if not custom_commands.strip():
            return "错误：使用custom方法时必须提供自定义指令序列。"

        success = deck_manipulator.parse_and_execute_custom_commands(custom_commands)
        if success:
            result += f"已成功执行自定义洗牌指令序列: {custom_commands}"
        else:
            result += f"执行自定义洗牌指令序列时出现错误: {custom_commands}"

    else:
        return f"错误：未知的洗牌方法 '{method}'。请使用list_shuffle_methods()查看可用的洗牌方法。"

    deck_manipulator.save_state()
    return result

def draw_tarot_spread(
    spread_key: Annotated[str, "牌阵代码，例如: three_card, celtic_cross, horseshoe, relationship, career_path"],
    question: Annotated[str, "占卜问题或主题"] = "",
    shuffle_first: Annotated[bool, "是否在抽牌前先洗牌"] = True
) -> str:
    """
    使用指定的牌阵抽取塔罗牌。

    此工具使用指定的牌阵抽取塔罗牌，并返回详细的解读结果。

    Args:
        spread_key: 牌阵代码，例如: three_card, celtic_cross, horseshoe, relationship, career_path
        question: 占卜问题或主题
        shuffle_first: 是否在抽牌前先洗牌

    Returns:
        牌阵解读结果
    """
    if spread_key not in TAROT_SPREADS:
        available_spreads = ", ".join(TAROT_SPREADS.keys())
        return f"错误：未知的牌阵代码 '{spread_key}'。可用的牌阵代码: {available_spreads}"

    deck_manipulator = DeckManipulator()

    # 如果需要，先洗牌
    if shuffle_first:
        deck_manipulator.op_random_shuffle()

    spread = TAROT_SPREADS[spread_key]

    result = f"【{spread['name']}】\n"
    if question:
        result += f"占卜问题: {question}\n"
    result += f"描述: {spread['description']}\n\n"

    # 抽取牌阵
    spread_cards = deck_manipulator.draw_spread(spread_key)

    if not spread_cards:
        return result + "抽牌失败，请重试。"

    # 格式化结果
    result += "抽牌结果:\n\n"
    for i, (card_info, position) in enumerate(spread_cards, 1):
        result += f"{i}. {format_card_info_text(card_info, position)}\n\n"

    result += "请根据牌面含义和位置进行综合分析。"
    return result

def draw_single_tarot_card(
    question: Annotated[str, "占卜问题或主题"] = "",
    shuffle_first: Annotated[bool, "是否在抽牌前先洗牌"] = True
) -> str:
    """
    抽取单张塔罗牌。

    此工具抽取单张塔罗牌，并返回详细的解读结果。

    Args:
        question: 占卜问题或主题
        shuffle_first: 是否在抽牌前先洗牌

    Returns:
        单张塔罗牌解读结果
    """
    deck_manipulator = DeckManipulator()

    if shuffle_first:
        deck_manipulator.op_random_shuffle()

    result = "【单张塔罗牌抽取】\n"
    if question:
        result += f"占卜问题: {question}\n\n"

    # 抽取单张牌
    cards_info = deck_manipulator.view_next_sequential_cards(1)

    if not cards_info:
        return result + "抽牌失败，请重试。"

    # 格式化结果
    result += format_card_info_text(cards_info[0])
    return result

def create_custom_tarot_spread(
    spread_name: Annotated[str, "自定义牌阵名称"],
    spread_description: Annotated[str, "自定义牌阵描述"],
    positions: Annotated[str, "牌位定义，格式为'位置名称:位置含义'，多个位置用分号分隔"],
    question: Annotated[str, "占卜问题或主题"] = "",
    shuffle_first: Annotated[bool, "是否在抽牌前先洗牌"] = True
) -> str:
    """
    创建并使用自定义牌阵抽取塔罗牌。

    此工具允许创建自定义牌阵并立即使用它抽取塔罗牌。

    Args:
        spread_name: 自定义牌阵名称
        spread_description: 自定义牌阵描述
        positions: 牌位定义，格式为'位置名称:位置含义'，多个位置用分号分隔
        question: 占卜问题或主题
        shuffle_first: 是否在抽牌前先洗牌

    Returns:
        自定义牌阵解读结果
    """
    # 解析位置定义
    position_list = []
    for i, pos_def in enumerate(positions.split(';')):
        pos_def = pos_def.strip()
        if not pos_def:
            continue

        parts = pos_def.split(':', 1)
        if len(parts) != 2:
            return f"错误：位置定义格式不正确 '{pos_def}'。正确格式为'位置名称:位置含义'"

        name, meaning = parts[0].strip(), parts[1].strip()
        position_list.append({"index": i, "name": name, "meaning": meaning})

    if not position_list:
        return "错误：未提供有效的位置定义。"

    deck_manipulator = DeckManipulator()

    if shuffle_first:
        deck_manipulator.op_random_shuffle()

    result = f"【{spread_name}】(自定义牌阵)\n"
    if question:
        result += f"占卜问题: {question}\n"
    result += f"描述: {spread_description}\n\n"

    # 抽取牌
    cards_info = []
    for position in position_list:
        # 找到下一张未抽过的牌
        for idx in range(len(deck_manipulator.deck)):
            if not deck_manipulator.deck[idx].is_drawn_in_session:
                card_info = deck_manipulator.view_card_at_index(idx)
                if card_info:
                    cards_info.append((card_info, position))
                    break

    if not cards_info:
        return result + "抽牌失败，请重试。"

    # 格式化结果
    result += "抽牌结果:\n\n"
    for i, (card_info, position) in enumerate(cards_info, 1):
        result += f"{i}. {format_card_info_text(card_info, position)}\n\n"

    result += "请根据牌面含义和位置进行综合分析。"
    deck_manipulator.save_state()
    return result

# --- 6. 导出为AutoGen工具 ---
# 导出的工具函数列表
tarot_tools = [
    list_tarot_spreads,
    list_shuffle_methods,
    shuffle_tarot_deck,
    draw_tarot_spread,
    draw_single_tarot_card,
    create_custom_tarot_spread
]

if __name__ == "__main__":
    # 确保源牌库ID是唯一的
    ids = [card['id'] for card in SOURCE_TAROT_CARDS]
    if len(ids) != len(set(ids)):
        print("错误：源牌库中存在重复的ID！请修正。")
        # 找出重复项
        from collections import Counter
        id_counts = Counter(ids)
        duplicates = [item for item, count in id_counts.items() if count > 1]
        print(f"重复的ID: {duplicates}")
    elif len(ids) != 78:
        print(f"警告：源牌库定义了 {len(ids)} 张牌，标准塔罗牌为78张。请检查。")
    else:
        cli_main()