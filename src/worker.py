import hashlib
import html
import json
import os
import re
from js import Response, URL, Object, Request, caches
from pyodide.ffi import to_js as _to_js


def to_js(obj):
        return _to_js(obj, dict_converter=Object.fromEntries)


# ---------------------------------------------------------------------------
# Curated, conventional renderings. Checked first; these are the "correct"
# answers a Chinese speaker would expect and are not derivable from spelling.
# ---------------------------------------------------------------------------
WORD_OVERRIDES = {
    # greetings / common words
    "hello": "哈喽", "hi": "嗨", "hey": "嘿", "bye": "拜",
    "ok": "欧凯", "okay": "欧凯", "yes": "耶斯", "no": "诺",
    "the": "泽", "and": "安德", "you": "尤", "your": "尤尔",
    "i": "艾",
    "love": "拉夫", "cool": "酷", "good": "古德", "bad": "巴德",
    "world": "沃尔德", "king": "金", "very": "维里", "happy": "哈皮",

    # tech / brands
    "cloudflare": "克劳德弗莱尔", "worker": "沃克", "workers": "沃克斯",
    "python": "派森", "javascript": "贾瓦斯克里普特", "java": "贾瓦",
    "openai": "欧朋艾", "chatgpt": "查特吉皮提", "claude": "克劳德",
    "google": "谷歌", "apple": "苹果", "microsoft": "微软",
    "amazon": "亚马逊", "facebook": "费斯布克", "meta": "梅塔",
    "twitter": "推特", "tesla": "特斯拉", "nvidia": "英伟达",
    "internet": "因特网", "computer": "康皮尤特", "server": "瑟弗",
    "data": "戴塔", "wifi": "歪法伊", "email": "伊妹儿", "app": "艾普",

    # places
    "america": "阿美瑞卡", "canada": "加拿大", "england": "英格兰",
    "london": "伦敦", "paris": "巴黎", "tokyo": "东京", "berlin": "柏林",
    "rome": "罗马", "moscow": "莫斯科", "sydney": "悉尼",
    "newyork": "纽约", "york": "约克", "san": "圣", "francisco": "弗朗西斯科",
    "washington": "华盛顿", "chicago": "芝加哥", "boston": "波士顿",

    # food / everyday
    "coffee": "咖啡", "pizza": "披萨", "chocolate": "巧克力",
    "hamburger": "汉堡", "salad": "沙拉", "sandwich": "三明治",
    "taxi": "塔克西", "bus": "巴士", "hotel": "霍特尔",
    "music": "缪吉克", "video": "维迪欧", "test": "泰斯特", "demo": "戴莫",

    # names
    "trump": "特朗普", "obama": "奥巴马", "elon": "埃隆", "musk": "马斯克",
    "john": "约翰", "michael": "迈克尔", "david": "大卫", "mary": "玛丽",
    "smith": "史密斯", "robert": "罗伯特", "peter": "彼得",
    # Simpsons characters
    "simpson": "辛普森", "homer": "霍默", "marge": "玛姬", "bart": "巴特",
    "lisa": "丽莎", "maggie": "玛吉", "seymour": "西摩",
    "superintendent": "苏佩林丹特", "chalmers": "查默斯",
}
DIGITS = {
    "0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
    "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
}


# ---------------------------------------------------------------------------
# Standard transliteration characters.
#
# FINAL_CHAR: a pinyin "final" rendered with no/zero initial (also the fallback
#   character for a final). INITIAL_CHAR: the character for a bare/leftover
#   consonant (coda or cluster member). TRANSLIT: preferred single character for
#   a full (initial+final) pinyin syllable. Anything missing from TRANSLIT falls
#   back to INITIAL_CHAR[initial] + FINAL_CHAR[final].
# ---------------------------------------------------------------------------
FINAL_CHAR = {
    "a": "阿", "o": "奥", "e": "厄", "er": "尔",
    "ai": "艾", "ei": "埃", "ao": "奥", "ou": "欧",
    "an": "安", "en": "恩", "ang": "昂", "eng": "恩", "ong": "翁",
    "i": "伊", "ia": "亚", "ie": "耶", "iao": "姚", "iu": "尤",
    "ian": "延", "in": "因", "iang": "扬", "ing": "英", "iong": "永",
    "u": "乌", "ua": "瓦", "uo": "沃", "uai": "怀", "ui": "维",
    "uan": "万", "un": "文", "uang": "旺",
    "oi": "奥伊",
}

_VOWEL_FINAL_CHARS = {ch for value in FINAL_CHAR.values() for ch in value}

INITIAL_CHAR = {
    "b": "布", "p": "普", "m": "姆", "f": "弗", "v": "夫",
    "d": "德", "t": "特", "n": "恩", "l": "尔",
    "g": "格", "k": "克", "h": "赫",
    "j": "吉", "q": "奇", "x": "希",
    "zh": "治", "ch": "奇", "sh": "什", "r": "尔",
    "z": "兹", "c": "茨", "s": "斯",
    "y": "伊", "w": "沃",
}

# Full-syllable preferred characters (pinyin -> Han). Generated from the common
# core of the standard transliteration tables.
TRANSLIT = {
    # b
    "ba": "巴", "bai": "拜", "ban": "班", "bang": "邦", "bao": "包",
    "bei": "贝", "ben": "本", "beng": "本", "bi": "比", "bian": "比安",
    "biao": "比奥", "bie": "比埃", "bin": "宾", "bing": "宾", "bo": "博",
    "bu": "布", "bou": "博",
    # p
    "pa": "帕", "pai": "派", "pan": "潘", "pang": "庞", "pao": "保",
    "pei": "佩", "pen": "彭", "peng": "彭", "pi": "皮", "pian": "皮安",
    "piao": "皮奥", "pin": "平", "ping": "平", "po": "波", "pou": "普", "pu": "普",
    # m
    "ma": "马", "mai": "迈", "man": "曼", "mang": "芒", "mao": "毛",
    "mei": "梅", "men": "门", "meng": "门", "mi": "米", "mian": "米安",
    "miao": "米奥", "mie": "米", "min": "明", "ming": "明", "mo": "莫",
    "mou": "穆", "mu": "穆",
    # f
    "fa": "法", "fan": "凡", "fang": "方", "fei": "费", "fen": "芬",
    "feng": "丰", "fo": "佛", "fou": "富", "fu": "弗",
    # d
    "da": "达", "dai": "戴", "dan": "丹", "dang": "当", "dao": "道",
    "de": "德", "dei": "戴", "den": "登", "deng": "登", "di": "迪",
    "dian": "迪安", "diao": "迪奥", "die": "迪", "ding": "丁", "diu": "丢",
    "dong": "东", "dou": "杜", "du": "杜", "duan": "杜安", "dui": "杜伊",
    "dun": "敦", "duo": "多",
    # t
    "ta": "塔", "tai": "泰", "tan": "坦", "tang": "唐", "tao": "陶",
    "te": "特", "teng": "滕", "ti": "蒂", "tian": "蒂安", "tie": "蒂",
    "ting": "廷", "tong": "通", "tou": "图", "tu": "图", "tuan": "图安",
    "tui": "图伊", "tun": "通", "tuo": "托",
    # n
    "na": "纳", "nai": "奈", "nan": "南", "nang": "囊", "nao": "瑙",
    "ne": "内", "nei": "内", "nen": "嫩", "neng": "能", "ni": "尼",
    "nian": "尼安", "niao": "尼奥", "nie": "涅", "nin": "宁", "ning": "宁",
    "niu": "纽", "nong": "农", "nou": "努", "nu": "努", "nuan": "努安",
    "nuo": "诺",
    # l
    "la": "拉", "lai": "莱", "lan": "兰", "lang": "朗", "lao": "劳",
    "le": "勒", "lei": "雷", "leng": "楞", "li": "利", "lia": "利亚",
    "lian": "利安", "liang": "良", "liao": "廖", "lie": "列", "lin": "林",
    "ling": "林", "liu": "刘", "lo": "洛", "long": "隆", "lou": "卢",
    "lu": "卢", "luan": "卢安", "lun": "伦", "luo": "罗",
    # g
    "ga": "加", "gai": "盖", "gan": "甘", "gang": "冈", "gao": "高",
    "ge": "格", "gei": "盖", "gen": "根", "geng": "庚", "gong": "贡",
    "gou": "古", "gu": "古", "gua": "瓜", "guai": "怀", "guan": "关",
    "guang": "光", "gui": "圭", "gun": "贡", "guo": "果",
    # k
    "ka": "卡", "kai": "凯", "kan": "坎", "kang": "康", "kao": "考",
    "ke": "克", "kei": "凯", "ken": "肯", "keng": "肯", "kong": "孔",
    "kou": "库", "ku": "库", "kua": "夸", "kuai": "快", "kuan": "宽",
    "kuang": "匡", "kui": "奎", "kun": "昆", "kuo": "阔",
    # h
    "ha": "哈", "hai": "海", "han": "汉", "hang": "杭", "hao": "豪",
    "he": "赫", "hei": "黑", "hen": "亨", "heng": "亨", "hong": "洪",
    "hou": "胡", "hu": "胡", "hua": "华", "huai": "怀", "huan": "环",
    "huang": "黄", "hui": "惠", "hun": "洪", "huo": "霍",
    # j
    "ji": "吉", "jia": "贾", "jian": "健", "jiang": "江", "jiao": "焦",
    "jie": "杰", "jin": "金", "jing": "京", "jiong": "炯", "jiu": "久",
    "ju": "朱", "juan": "娟", "jue": "杰", "jun": "君",
    # q
    "qi": "奇", "qia": "恰", "qian": "钱", "qiang": "强", "qiao": "乔",
    "qie": "切", "qin": "钦", "qing": "青", "qiu": "丘", "qu": "曲",
    "quan": "全", "que": "克", "qun": "群",
    # x
    "xi": "希", "xia": "夏", "xian": "先", "xiang": "香", "xiao": "肖",
    "xie": "谢", "xin": "辛", "xing": "星", "xiong": "雄", "xiu": "休",
    "xu": "许", "xuan": "宣", "xue": "雪", "xun": "训",
    # zh (English j / soft g / dg)
    "zha": "扎", "zhai": "宅", "zhan": "詹", "zhang": "张", "zhao": "赵",
    "zhe": "哲", "zhen": "真", "zheng": "郑", "zhi": "奇", "zhong": "钟",
    "zhou": "周", "zhu": "朱", "zhuan": "专", "zhuang": "庄", "zhui": "追",
    "zhun": "准", "zhuo": "卓",
    # ch
    "cha": "查", "chai": "柴", "chan": "钱", "chang": "昌", "chao": "乔",
    "che": "切", "chen": "陈", "cheng": "程", "chi": "奇", "chong": "冲",
    "chou": "仇", "chu": "楚", "chuan": "川", "chuang": "闯", "chui": "吹",
    "chun": "春",
    # sh
    "sha": "沙", "shan": "山", "shang": "尚", "shao": "绍", "she": "舍",
    "shen": "申", "sheng": "圣", "shi": "希", "shou": "寿", "shu": "舒",
    "shua": "刷", "shuai": "帅", "shuan": "拴", "shuang": "双", "shui": "水",
    "shun": "顺", "shuo": "硕",
    # r (English r is mapped to l-series in onsets; keep r-finals too)
    "re": "热", "ran": "然", "rang": "让", "rao": "饶", "ren": "伦",
    "reng": "仍", "ri": "日", "rong": "龙", "rou": "柔", "ru": "鲁",
    "ruan": "软", "rui": "瑞", "run": "润", "ruo": "若",
    # z
    "za": "扎", "zai": "宰", "zan": "赞", "zang": "藏", "zao": "藻",
    "ze": "泽", "zen": "怎", "zeng": "增", "zi": "齐", "zong": "宗",
    "zou": "邹", "zu": "祖", "zuan": "钻", "zui": "最", "zun": "尊", "zuo": "佐",
    # c (ts)
    "ca": "擦", "cai": "采", "can": "灿", "cang": "仓", "cao": "曹",
    "ce": "策", "cen": "岑", "ceng": "层", "ci": "齐", "cong": "聪",
    "cou": "凑", "cu": "粗", "cuan": "窜", "cui": "崔", "cun": "村", "cuo": "错",
    # s
    "sa": "萨", "sai": "赛", "san": "桑", "sang": "桑", "sao": "骚",
    "se": "塞", "sen": "森", "seng": "僧", "si": "西", "song": "松",
    "sou": "苏", "su": "苏", "suan": "酸", "sui": "苏伊", "sun": "孙", "suo": "索",
    # y
    "ya": "亚", "yan": "扬", "yang": "杨", "yao": "姚", "ye": "耶",
    "yi": "伊", "yin": "因", "ying": "英", "yo": "约", "yong": "永",
    "you": "尤", "yu": "于", "yuan": "元", "yue": "岳", "yun": "云",
    # w (also used for English v)
    "wa": "瓦", "wai": "怀", "wan": "万", "wang": "旺", "wei": "韦",
    "wen": "文", "weng": "翁", "wo": "沃", "wu": "乌",
    # English syllables with no pinyin counterpart (fi/ki/gi/wi/hi/fe...).
    "fi": "菲", "fe": "费", "ki": "基", "gi": "吉", "wi": "维", "hi": "希",
    # r-coloured schwa (ER) onsets: work -> 沃, bird -> 伯, person -> 珀...
    "we": "沃", "be": "伯", "pe": "珀", "me": "默",
    # zero initial
    "a": "阿", "ai": "艾", "an": "安", "ang": "昂", "ao": "奥",
    "e": "厄", "ei": "埃", "en": "恩", "eng": "恩", "er": "尔",
    "o": "奥", "ou": "欧",
    "i": "伊", "in": "因", "ing": "英",
    "u": "乌",
}


# ---------------------------------------------------------------------------
# Grapheme cleanup. Protect multi-letter sounds with single placeholder
# capitals BEFORE doing single-letter substitutions, then lower them back into
# multi-letter onset tokens the syllabifier understands.
# ---------------------------------------------------------------------------
VOWELS = set("aeiou")

# placeholder -> onset token used by the syllabifier
_PLACEHOLDERS = {
    "C": "ch",   # ch / tch
    "S": "sh",   # sh
    "Z": "zh",   # English j / soft g / dg
    "Q": "s",    # th -> s-series
    "R": "ER",   # word-final -er / -or  (renders as 尔)
    "G": "ng",   # ng nasal coda
}


EXAMPLES_JSON_PATH = os.path.join(os.path.dirname(__file__), "examples.json")


def _load_example_definitions():
    try:
        with open(EXAMPLES_JSON_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


EXAMPLE_DEFINITIONS = _load_example_definitions()


def _render_example_buttons():
    if not EXAMPLE_DEFINITIONS:
        return '      <p class="hint">No examples defined yet.</p>'

    buttons = []
    for entry in EXAMPLE_DEFINITIONS:
        label = str(entry.get("label", "") or "").strip()
        text = str(entry.get("text", "") or "").strip()
        if not text:
            continue
        if not label:
            label = "example"
        escaped_text = html.escape(text, quote=True)
        escaped_label = html.escape(label)
        buttons.append(
            f'      <button class="example" data-text="{escaped_text}">{escaped_label}</button>'
        )

    return "\n".join(buttons)


EXAMPLE_BUTTONS_HTML = _render_example_buttons()


def _clean(word):
    w = word.lower()
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return ""

    # Common suffixes whose sound is far from their spelling.
    w = re.sub(r"tion", "Sen", w)          # -tion -> "shen" (申)
    w = re.sub(r"s?sion", "Zen", w)        # -sion -> "zhen" (真)

    # Protect digraphs first (order matters).
    w = w.replace("tch", "C").replace("ch", "C")
    w = w.replace("sh", "S")
    w = re.sub(r"d?ge\b", "Z", w)          # -dge / -ge endings -> j sound
    w = re.sub(r"dg", "Z", w)
    w = w.replace("ph", "f")
    w = w.replace("th", "Q")
    w = w.replace("wh", "w")
    w = w.replace("ck", "k")
    w = re.sub(r"qu", "kw", w)
    w = w.replace("ng", "G")                # nasal-velar coda marker

    # Soft / hard c and English j / soft g.
    w = re.sub(r"c(?=[eiy])", "s", w)
    w = re.sub(r"c", "k", w)
    w = re.sub(r"[jJ]", "Z", w)             # j -> zh-series

    # Silent letters.
    w = re.sub(r"kn", "n", w)               # knee, know
    w = re.sub(r"wr", "r", w)               # write
    w = re.sub(r"mb\b", "m", w)             # thumb, lamb
    w = re.sub(r"igh", "ai", w)             # high, night-ish
    w = re.sub(r"gh", "", w)                # silent gh

    # Word-final -er / -or -> single 尔 marker.
    w = re.sub(r"([bcdfghklmnpstvwxz])(er|or)\b", r"\1R", w, flags=re.I)

    # Postvocalic r (after vowel, not before a vowel) is silent (non-rhotic).
    # 'y' counts as a following vowel so e.g. "very" keeps r as an onset.
    w = re.sub(r"(?<=[aeiou])r(?![aeiouy])", "", w)
    # Remaining r are onsets -> map English r to the l-series.
    w = w.replace("r", "l")

    # Drop a silent trailing magic-e (but keep ee / le / ye).
    if len(w) > 3 and w.endswith("e") and not re.search(r"(ee|le|ye)$", w):
        w = w[:-1]

    # Collapse doubled consonants.
    w = re.sub(r"([bcdfgklmnpstvwxz])\1+", r"\1", w)
    return w


# Vowel teams -> pinyin vowel core (without nasal coda).
_NUCLEI = [
    ("eau", "u"), ("eigh", "ei"), ("augh", "o"), ("ough", "o"),
    ("ai", "ai"), ("ay", "ei"), ("ei", "ei"), ("ey", "ei"), ("ae", "ei"),
    ("ee", "i"), ("ea", "i"), ("ie", "i"),
    ("oo", "u"), ("oa", "o"), ("oe", "o"), ("ou", "ou"), ("ow", "ou"),
    ("oi", "oi"), ("oy", "oi"),
    ("au", "o"), ("aw", "o"),
    ("ew", "iu"), ("ue", "u"), ("ui", "ui"),
    ("a", "a"), ("e", "e"), ("i", "i"), ("o", "o"), ("u", "u"), ("y", "i"),
]

# Onset tokens recognised by the syllabifier (longest first).
_ONSETS = ["ch", "sh", "zh", "ng",
           "b", "p", "m", "f", "v", "d", "t", "n", "l",
           "g", "k", "h", "s", "z", "w", "y"]

# Map a cleaned-string consonant char to an onset/initial token.
_CONS = set("bpmfvdtnlgkhszwy")


def _is_vowel(ch):
    return ch in "aeiouy"


def _take_nucleus(s, i):
    """Return (vowel_core, new_index) consuming the longest vowel team at i."""
    for team, core in _NUCLEI:
        if s.startswith(team, i):
            return core, i + len(team)
    return None, i


def _char_for(initial, final):
    syll = (initial or "") + final
    if syll in TRANSLIT:
        return TRANSLIT[syll]
    if not initial:
        return FINAL_CHAR.get(final, "")
    # Many consonant + "o" combos are not valid pinyin (do/go/no/so/...); the
    # standard mapping uses the -uo final instead (duo/guo/nuo/suo -> 多/果/诺/索).
    if final == "o" and (initial + "uo") in TRANSLIT:
        return TRANSLIT[initial + "uo"]
    return INITIAL_CHAR.get(initial, "") + FINAL_CHAR.get(final, "")


def _syllabify(w):
    """Turn a cleaned string into a list of Han characters."""
    out = []
    i = 0
    n = len(w)
    while i < n:
        ch = w[i]

        # Explicit markers.
        if ch == "C":
            initial = "ch"; i += 1
        elif ch == "S":
            initial = "sh"; i += 1
        elif ch == "Z":
            initial = "zh"; i += 1
        elif ch == "Q":
            initial = "s"; i += 1
        elif ch == "G":
            out.append("恩"); i += 1; continue          # stray nasal
        elif ch == "R":
            out.append("尔"); i += 1; continue          # -er / -or
        elif ch in _CONS:
            # Onset is the single consonant right before the vowel; any
            # consonant cluster member that is NOT adjacent to the vowel is
            # emitted as its own coda character.
            initial = ch
            i += 1
        elif _is_vowel(ch):
            initial = ""
        else:
            i += 1
            continue

        # If no plain vowel follows, the onset we just read is actually a
        # standalone coda consonant (cluster member or word-final consonant).
        next_is_vowel = i < n and _is_vowel(w[i])
        if initial and not next_is_vowel:
            out.append(INITIAL_CHAR.get(initial, ""))
            continue

        # English v uses the w-series for vowel combos (Victor -> 维克托).
        is_v = initial == "v"
        if is_v:
            initial = "w"

        # Read the vowel nucleus.
        core, j = _take_nucleus(w, i)
        if core is None:
            out.append(INITIAL_CHAR.get(initial, ""))
            continue
        i = j

        # v + front vowel -> the "wei" (韦) row rather than wo/wu.
        if is_v and core in ("e", "i"):
            core = "ei"

        # Read a nasal coda (n / ng) that is not the onset of a new syllable.
        final = core
        if i < n:
            if w[i] == "G" and not (i + 1 < n and (_is_vowel(w[i + 1]) or w[i + 1] in "CSZQ")):
                final = _add_nasal(core, "ng"); i += 1
            elif w[i] == "n" and not (i + 1 < n and (_is_vowel(w[i + 1]) or w[i + 1] in "CSZQ")):
                final = _add_nasal(core, "n"); i += 1

        # Closed-syllable short 'e' (red, bed, get) reads better as the -ei row
        # when that yields a real transliteration character.
        if final == "e" and i < n and not _is_vowel(w[i]) and (initial + "ei") in TRANSLIT:
            final = "ei"

        out.append(_char_for(initial, final))

    return "".join(c for c in out if c)


def _add_nasal(core, nasal):
    """Combine a vowel core with an n / ng coda into a pinyin final."""
    if nasal == "ng":
        return {
            "a": "ang", "e": "eng", "i": "ing", "o": "ong", "u": "ong",
            "ai": "ang", "ei": "eng", "ou": "ong", "ao": "ang",
        }.get(core, core + "ng")
    # plain -n
    return {
        "a": "an", "e": "en", "i": "in", "o": "ong", "u": "un",
        "ai": "an", "ei": "en", "ou": "un", "ao": "an", "oi": "oi",
        "ui": "un", "ua": "uan", "ia": "ian",
    }.get(core, core + "n")



# ---------------------------------------------------------------------------
# Phoneme-based common words derived from IPA pronunciations.
# ---------------------------------------------------------------------------

def _load_common_phonemes():
    path = os.path.join(os.path.dirname(__file__), "common_words_ipa.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _load_additional_ipa_records(filenames):
    path_dir = os.path.dirname(__file__)
    output = {}
    for filename in filenames:
        path = os.path.join(path_dir, filename)
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            continue
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if not key or key.startswith("_"):
                continue
            if not isinstance(value, dict):
                continue
            output[key.lower()] = value
    return output


BASE_COMMON_WORD_PHONEMES = _load_common_phonemes()
_ADDITIONAL_IPA_FILES = [
    "american_top_1000_names_ipa.json",
    "fortune_500_ipa.json",
]
ADDITIONAL_IPA_RECORDS = _load_additional_ipa_records(_ADDITIONAL_IPA_FILES)
COMMON_WORD_PHONEMES = {
    **BASE_COMMON_WORD_PHONEMES,
    **ADDITIONAL_IPA_RECORDS,
}

_IPA_VOWELS = {'AA','AE','AH','AO','AW','AY','EH','ER','EY','IH','IY','OW','OY','UH','UW'}
_IPA_VCORE = {'AA':'a','AE':'a','AH':'a','AO':'o','AW':'ao','AY':'ai','EH':'e','ER':'e',
              'EY':'ei','IH':'i','IY':'i','OW':'ou','OY':'oi','UH':'u','UW':'u'}
_IPA_ONSET = {'B':'b','CH':'ch','D':'d','DH':'z','F':'f','G':'g','HH':'h','JH':'zh','K':'k',
              'L':'l','M':'m','N':'n','P':'p','R':'l','S':'s','SH':'sh','T':'t','TH':'s',
              'V':'w','W':'w','Y':'y','Z':'z','ZH':'zh'}
_IPA_CODA = {'B':'布','CH':'奇','D':'德','DH':'斯','F':'弗','G':'格','HH':'赫','JH':'奇',
             'K':'克','L':'尔','M':'姆','N':'恩','NG':'恩','P':'普','S':'斯','SH':'什',
             'T':'特','TH':'斯','V':'夫','Z':'兹','ZH':'日','Y':'伊','W':'沃','R':''}

def _ipa_base(ph):
    return re.sub(r"\d", "", ph)

def _phonemes_to_hanzi(phones):
    out = []
    i = 0
    n = len(phones)
    while i < n:
        p = _ipa_base(phones[i])
        if p in _IPA_VOWELS:
            initial = ""
            is_v = False
            vphone = p
            core = _IPA_VCORE[p]
            i += 1
        elif p in _IPA_ONSET:
            nxt = _ipa_base(phones[i + 1]) if i + 1 < n else None
            if nxt in _IPA_VOWELS:
                is_v = (p == "V")
                initial = _IPA_ONSET[p]
                if p in ("SH", "ZH", "CH", "JH") and phones[i + 1] == "AH0" and i + 2 < n and _ipa_base(phones[i + 2]) == "N" and i + 3 == n:
                    out.append({'SH': '申', 'ZH': '真', 'JH': '真', 'CH': '申'}[p])
                    i += 3
                    continue
                i += 1
                if i >= n:
                    continue
                vphone = _ipa_base(phones[i])
                core = _IPA_VCORE.get(vphone)
                i += 1
            else:
                if p == "R":
                    i += 1
                    continue
                out.append(_IPA_CODA.get(p, ""))
                i += 1
                continue
        else:
            i += 1
            continue
        if not core:
            continue
        if is_v and core in ("i", "e", "ei"):
            core = "ei"
        final = core
        if i < n:
            nb = _ipa_base(phones[i])
            if nb == "N" and not (i + 1 < n and _ipa_base(phones[i + 1]) in _IPA_VOWELS):
                final = _add_nasal(core, "n")
                i += 1
            elif nb == "NG" and not (i + 1 < n and _ipa_base(phones[i + 1]) in _IPA_VOWELS):
                final = _add_nasal(core, "ng")
                i += 1
        if final == core:
            if vphone == "EH" and (initial + "ei") in TRANSLIT:
                final = "ei"
            elif vphone == "EY" and (initial + "ei") not in TRANSLIT and (initial + "ai") in TRANSLIT:
                final = "ai"
        out.append(_char_for(initial, final))
    return "".join(c for c in out if c)

def _phonetic_fallback_from_spelling(word):
    cleaned = _clean(word)
    if not cleaned:
        return ""
    return _pronounceable_only(_syllabify(cleaned))

_LETTER_FALLBACK = {
    **{k: v for k, v in INITIAL_CHAR.items() if len(k) == 1},
    **{k: v for k, v in FINAL_CHAR.items() if len(k) == 1},
    "y": "伊"
}

def _letter_fallback(word):
    return _pronounceable_only("".join(_LETTER_FALLBACK.get(ch, "") for ch in word.lower()))

_DIGIT_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
    5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
}
_SMALL_ONES = _DIGIT_WORDS
_SMALL_TEENS = {
    10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
    15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
}
_SMALL_TENS = {
    20: "twenty", 30: "thirty", 40: "forty", 50: "fifty",
    60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety",
}
_SCALE_WORDS = [
    (10**15, "quadrillion"),
    (10**12, "trillion"),
    (10**9, "billion"),
    (10**6, "million"),
    (10**3, "thousand"),
]

def _words_below_thousand(number):
    parts = []
    if number >= 100:
        hundreds, remainder = divmod(number, 100)
        parts.append(_SMALL_ONES[hundreds])
        parts.append("hundred")
        number = remainder
    if number >= 20:
        tens, remainder = divmod(number, 10)
        parts.append(_SMALL_TENS[tens * 10])
        if remainder:
            parts.append(_SMALL_ONES[remainder])
    elif number >= 10:
        parts.append(_SMALL_TEENS[number])
    elif number > 0 or not parts:
        parts.append(_SMALL_ONES[number])
    return parts

def _number_to_words(number):
    if number == 0:
        return ["zero"]
    parts = []
    for scale_value, scale_label in _SCALE_WORDS:
        if number >= scale_value:
            scale_count, number = divmod(number, scale_value)
            parts.extend(_number_to_words(scale_count))
            parts.append(scale_label)
    if number:
        parts.extend(_words_below_thousand(number))
    return parts

def _digits_to_words(token):
    if not token:
        return None
    if len(token) > 1 and token[0] == "0":
        return [_DIGIT_WORDS[int(digit)] for digit in token]
    try:
        numeric = int(token)
    except ValueError:
        return None
    return _number_to_words(numeric)

_DOLLAR_AMOUNT_RE = re.compile(r"\$+\s*(\d+)(?!\s+dollars)", re.IGNORECASE)


def _normalize_dollar_amounts(text):
    if not text:
        return ""
    return _DOLLAR_AMOUNT_RE.sub(r"\1 dollars", text)

def _collect_pronounceable_characters():
    import string as _string

    tables = [WORD_OVERRIDES, TRANSLIT, FINAL_CHAR, INITIAL_CHAR, DIGITS]
    allowed = set()
    for table in tables:
        for value in table.values():
            allowed.update(value)

    # Basic separators and punctuation that ElevenLabs can pronounce in voice output.
    allowed.update(
        _string.punctuation + " ·" + "，。？！：；’‘“”…—（）【】「」『』《》〈〉〝〞、·"
    )
    allowed.update("\n\r\t")
    return frozenset(allowed)

PRONOUNCEABLE_CHARACTERS = _collect_pronounceable_characters()


def _pronounceable_only(text):
    if not text:
        return ""
    return "".join(ch for ch in text if ch in PRONOUNCEABLE_CHARACTERS)


CACHE_TTL_SECONDS = 72 * 60 * 60  # 72 hours
_CACHE_BASE_URL = "https://receiptify-cache.local/cache"
TTS_VOICE_TAG = "Cheer200 Xijinping: "

def _calculate_script_signature():
    try:
        path = os.path.abspath(__file__)
    except NameError:
        return "unknown"
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return "unknown"

_SCRIPT_SIGNATURE = _calculate_script_signature()
CACHE_VERSION = os.environ.get("CACHE_VERSION") or _SCRIPT_SIGNATURE[:16]

def _cache_url_for_key(key):
    return f"{_CACHE_BASE_URL}/{key}"

def _cache_key(text, separator, length, use_tts_tag):
    normalized_text = text if text is not None else ""
    normalized_sep = separator if separator is not None else ""
    normalized_length = "" if length is None else str(length)
    normalized_tts = "1" if use_tts_tag else "0"
    payload = f"{CACHE_VERSION}|{normalized_length}|{normalized_sep}|{normalized_tts}|{normalized_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_requested_length(value):
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
    else:
        trimmed = str(value).strip()
    if not trimmed:
        return None
    if not trimmed.isdigit():
        raise ValueError("length must be a positive integer")
    length = int(trimmed)
    if length <= 0:
        raise ValueError("length must be a positive integer")
    return length


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def _repeat_or_truncate(source, target_length):
    if target_length <= 0 or not source:
        return ""
    if len(source) >= target_length:
        return source[:target_length]
    repeats = -(-target_length // len(source))
    return (source * repeats)[:target_length]


def _apply_requested_length(output, desired_length, include_tts_tag=False):
    if include_tts_tag:
        if desired_length is None:
            return TTS_VOICE_TAG + output
        if desired_length <= len(TTS_VOICE_TAG):
            return TTS_VOICE_TAG[:desired_length]
        available = desired_length - len(TTS_VOICE_TAG)
        core = _repeat_or_truncate(output, available)
        return TTS_VOICE_TAG + core
    if desired_length is None:
        return output
    return _repeat_or_truncate(output, desired_length)

async def _lookup_cached_response(key):
    cache = getattr(caches, "default", None)
    if not cache:
        return None
    try:
        request = Request.new(_cache_url_for_key(key))
        return await cache.match(request)
    except Exception:
        return None

async def _store_cached_response(key, response_obj):
    cache = getattr(caches, "default", None)
    if not cache:
        return
    try:
        request = Request.new(_cache_url_for_key(key))
        await cache.put(request, response_obj.clone())
    except Exception:
        pass


MORPH_PREFIXES = (
    "re", "un", "in", "im", "ir", "dis", "non", "pre", "post",
    "over", "under", "super", "sub", "inter", "trans", "mis", "auto",
    "anti"
)

MORPH_GENERAL_SUFFIXES = (
    "ness", "ment", "ity", "tion", "sion", "ation", "al", "ial", "er",
    "or", "est", "ism", "ist", "hood", "ship", "able", "ible", "ous",
    "ive", "less", "ful", "ward", "wards", "dom", "age", "ence", "ance",
    "ify", "ize", "ise", "ly"
)

IRREGULAR_PLURALS = {
    "children": "child",
    "people": "person",
    "men": "man",
    "women": "woman",
    "feet": "foot",
    "teeth": "tooth",
    "geese": "goose",
    "mice": "mouse",
    "indices": "index",
    "matrices": "matrix",
    "data": "datum",
}

IRREGULAR_VERBS = {
    "ran": "run",
    "gone": "go",
    "did": "do",
    "saw": "see",
    "took": "take",
    "seen": "see",
    "written": "write",
    "eaten": "eat",
    "been": "be",
    "wrote": "write",
    "wearing": "wear",
}


def _sanitize_for_lookup(word):
    return re.sub(r"[^a-z]", "", word.lower())


def _estimate_syllable_count(word):
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    nuclei = re.findall(r"[aeiouy]+", cleaned)
    return max(1, len(nuclei))


def _word_ends_with_consonant(word):
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    return bool(cleaned and cleaned[-1] in "bcdfghjklmnpqrstvwxyz")


def _ends_with_vowel_sound(text):
    for ch in reversed(text):
        if not ch.strip():
            continue
        return ch in _VOWEL_FINAL_CHARS
    return False


def _count_chinese_chars(text):
    return sum(1 for ch in text if "一" <= ch <= "鿿")


_VOWEL_END_PENALTY = 5


def _score_candidate(text, target, is_raw, prefer_consonant_end):
    count = _count_chinese_chars(text)
    if count == 0:
        count = len(text)
    diff = abs(count - target)
    penalty = 0 if is_raw else 1
    if prefer_consonant_end and _ends_with_vowel_sound(text):
        penalty += _VOWEL_END_PENALTY
    return diff * 10 + penalty


def _match_dictionary_entry(candidate):
    entry = WORD_OVERRIDES.get(candidate)
    if entry:
        return entry

    entry = COMMON_WORD_PHONEMES.get(candidate)
    if not isinstance(entry, dict):
        return None

    hanzi = entry.get("hanzi")
    if not hanzi:
        phones = entry.get("phones") or []
        hanzi = _phonemes_to_hanzi(phones)
    if not hanzi:
        return None
    return _pronounceable_only(hanzi)


def _generate_morph_candidates(cleaned, original):
    seen = set()

    def _yield(word):
        if word and word not in seen:
            seen.add(word)
            yield word

    yield from _yield(cleaned)

    lower = original.lower()
    if lower.endswith("'s") or lower.endswith("’s"):
        base = lower[:-2]
        yield from _yield(_sanitize_for_lookup(base))
    elif lower.endswith("s'"):
        base = lower[:-2]
        yield from _yield(_sanitize_for_lookup(base))

    if cleaned in IRREGULAR_PLURALS:
        yield from _yield(IRREGULAR_PLURALS[cleaned])
    if cleaned in IRREGULAR_VERBS:
        yield from _yield(IRREGULAR_VERBS[cleaned])

    for prefix in MORPH_PREFIXES:
        if cleaned.startswith(prefix) and len(cleaned) - len(prefix) >= 3:
            yield from _yield(cleaned[len(prefix):])

    for suffix in MORPH_GENERAL_SUFFIXES:
        if cleaned.endswith(suffix) and len(cleaned) - len(suffix) >= 3:
            yield from _yield(cleaned[:-len(suffix)])

    if cleaned.endswith("ing") and len(cleaned) > 4:
        base = cleaned[:-3]
        yield from _yield(base)
        if len(base) > 2 and base[-1] == base[-2]:
            yield from _yield(base[:-1])
        if not base.endswith("e"):
            yield from _yield(base + "e")

    if cleaned.endswith("ed") and len(cleaned) > 3:
        base = cleaned[:-2]
        yield from _yield(base)
        if not base.endswith("e"):
            yield from _yield(base + "e")

    if cleaned.endswith("ies") and len(cleaned) > 4:
        yield from _yield(cleaned[:-3] + "y")

    if cleaned.endswith("ves") and len(cleaned) > 4:
        stem = cleaned[:-3]
        yield from _yield(stem + "f")
        yield from _yield(stem + "fe")

    if cleaned.endswith("es") and len(cleaned) > 3:
        yield from _yield(cleaned[:-2])

    if cleaned.endswith("s") and len(cleaned) > 3 and not cleaned.endswith(("ss", "us", "is", "as")):
        yield from _yield(cleaned[:-1])


def _lookup_with_morph(cleaned, original):
    target = _estimate_syllable_count(original)
    prefer_consonant_end = _word_ends_with_consonant(original)
    best = None
    best_score = None
    for candidate in _generate_morph_candidates(cleaned, original):
        match = _match_dictionary_entry(candidate)
        if not match:
            continue
        score = _score_candidate(match, target, candidate == cleaned, prefer_consonant_end)
        if best_score is None or score < best_score:
            best_score = score
            best = match
            if score == 0:
                break
    return best


def transliterate_word(word):
    raw = _sanitize_for_lookup(word)
    if not raw:
        return ""
    lookup = _lookup_with_morph(raw, word)
    if lookup:
        return lookup
    phonetic = _phonetic_fallback_from_spelling(word)
    if phonetic:
        return phonetic
    return _letter_fallback(word)


TOKEN_RE = re.compile(r"[A-Za-z']+|\d+|[^\w\s]+|\s+", re.UNICODE)


def transliterate_text(text, separator="·"):
    tokens = TOKEN_RE.findall(_normalize_dollar_amounts(text))
    output = []
    previous_was_word = False

    for token in tokens:
        if re.fullmatch(r"[A-Za-z']+", token):
            if previous_was_word:
                output.append(separator)
            output.append(transliterate_word(token))
            previous_was_word = True
        elif re.fullmatch(r"\d+", token):
            digits_words = _digits_to_words(token)
            handled = False
            if digits_words:
                seen = 0
                for word in digits_words:
                    transliterated = transliterate_word(word)
                    if not transliterated:
                        continue
                    if previous_was_word or seen:
                        output.append(separator)
                    output.append(transliterated)
                    previous_was_word = True
                    seen += 1
                handled = seen > 0
            if handled:
                continue
            if previous_was_word:
                output.append(separator)
            digits = "".join(DIGITS.get(ch, ch) for ch in token)
            output.append(_pronounceable_only(digits))
            previous_was_word = True
        elif token.isspace():
            continue
        else:
            safe_token = _pronounceable_only(token)
            if safe_token:
                output.append(safe_token)
            previous_was_word = False

    return "".join(output)



HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>receiptify — English to Chinese Sound-Alike Characters</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Comic+Neue:ital,wght@0,300;0,400;0,700;1,300;1,400;1,700&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Righteous&display=swap" rel="stylesheet">

  <style>
    :root {
      color-scheme: light dark;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(239, 68, 68, 0.22), transparent 30%),
        radial-gradient(circle at bottom right, rgba(245, 158, 11, 0.20), transparent 35%),
        canvas;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 32px 24px 24px;
      box-sizing: border-box;
    }

    main {
      width: min(760px, 100%);
      background: color-mix(in srgb, canvas 88%, transparent);
      border: 1px solid color-mix(in srgb, canvasText 14%, transparent);
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.14);
      border-radius: 24px;
      padding: 28px;
      backdrop-filter: blur(12px);
    }

    h1 {
      margin: 0 0 8px;
      font-family: "Righteous", system-ui, sans-serif;
      font-size: clamp(2.6rem, 9vw, 5.2rem);
      line-height: 1;
      letter-spacing: 0.01em;
      background: linear-gradient(135deg, #dc2626 0%, #f59e0b 100%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
      filter: drop-shadow(0 4px 14px rgba(220, 38, 38, 0.25));
    }

    .subtitle {
      margin: 0 0 24px;
      color: color-mix(in srgb, canvasText 70%, transparent);
      font-size: 1.05rem;
    }

    label {
      display: block;
      font-weight: 700;
      margin-bottom: 8px;
    }

    textarea {
      width: 100%;
      min-height: 130px;
      box-sizing: border-box;
      resize: vertical;
      border-radius: 16px;
      border: 1px solid color-mix(in srgb, canvasText 18%, transparent);
      background: color-mix(in srgb, canvas 95%, canvasText 5%);
      color: canvasText;
      padding: 16px;
      font: inherit;
      font-size: 1.05rem;
      outline: none;
    }

    textarea:focus {
      border-color: #dc2626;
      box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.18);
    }

    input[type="number"] {
      width: min(220px, 100%);
      border-radius: 12px;
      border: 1px solid color-mix(in srgb, canvasText 18%, transparent);
      background: color-mix(in srgb, canvas 95%, canvasText 5%);
      color: canvasText;
      padding: 12px 14px;
      font: inherit;
      font-size: 1rem;
      outline: none;
      box-sizing: border-box;
      appearance: textfield;
    }

    input[type="number"]:focus {
      border-color: #dc2626;
      box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.16);
    }

    input[type="range"] {
      width: 100%;
      accent-color: #dc2626;
      height: 6px;
      border-radius: 999px;
      background: color-mix(in srgb, canvasText 14%, transparent);
      outline: none;
    }

    input[type="range"]::-webkit-slider-thumb {
      appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #dc2626;
      box-shadow: 0 2px 6px rgba(220, 38, 38, 0.35);
      cursor: pointer;
      border: 0;
    }

    input[type="range"]::-moz-range-thumb {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #dc2626;
      box-shadow: 0 2px 6px rgba(220, 38, 38, 0.35);
      cursor: pointer;
      border: 0;
    }

    input[type="range"]::-webkit-slider-runnable-track {
      height: 6px;
      border-radius: 999px;
      background: color-mix(in srgb, canvasText 18%, transparent);
    }

    input[type="range"]::-moz-range-track {
      height: 6px;
      border-radius: 999px;
      background: color-mix(in srgb, canvasText 18%, transparent);
    }

    .check-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
      font-weight: 600;
      cursor: pointer;
    }

    .check-row input {
      width: auto;
      flex-shrink: 0;
    }

    .row {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 16px;
    }

    details.bigtext-panel {
      margin-top: 20px;
      border: 1px solid color-mix(in srgb, canvasText 14%, transparent);
      border-radius: 18px;
      background: color-mix(in srgb, canvas 94%, canvasText 6%);
      overflow: hidden;
    }

    details.bigtext-panel summary {
      padding: 16px 20px;
      cursor: pointer;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      list-style: none;
    }

    details.bigtext-panel summary::marker,
    details.bigtext-panel summary::-webkit-details-marker {
      display: none;
    }

    details.bigtext-panel summary::after {
      content: ">";
      font-weight: 700;
      display: inline-block;
      transition: transform 0.2s ease;
    }

    details.bigtext-panel[open] summary {
      border-bottom: 1px solid color-mix(in srgb, canvasText 12%, transparent);
    }

    details.bigtext-panel[open] summary::after {
      transform: rotate(90deg);
    }

    .bigtext-panel-body {
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .bigtext-panel-grid {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    }

    .bigtext-control {
      display: flex;
      flex-direction: column;
      gap: 10px;
      flex: 1 1 200px;
      min-width: 200px;
    }

    .bigtext-control label {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 0;
    }

    .bigtext-control select {
      width: 100%;
    }

    .slider-value {
      font-weight: 600;
      font-size: 0.9rem;
      color: color-mix(in srgb, canvasText 55%, transparent);
    }

    button {
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }

    #convert {
      background: #dc2626;
      color: white;
    }

    #copy {
      background: color-mix(in srgb, canvasText 12%, transparent);
      color: canvasText;
    }

    .hint {
      color: color-mix(in srgb, canvasText 60%, transparent);
      font-size: 0.95rem;
    }

    details.hint-block {
      margin-top: 12px;
    }

    details.hint-block[open] {
      margin-bottom: 6px;
    }

    details.hint-block summary {
      cursor: pointer;
      font-weight: 700;
      color: color-mix(in srgb, canvasText 70%, transparent);
      list-style: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    details.hint-block summary::-webkit-details-marker {
      display: none;
    }

    details.hint-block summary::before {
      content: "▸";
      transition: transform 120ms ease;
      transform-origin: center;
    }

    details.hint-block[open] summary::before {
      transform: rotate(90deg);
    }

    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin: 0;
      font-weight: 600;
      cursor: pointer;
      user-select: none;
    }

    .toggle input {
      cursor: pointer;
    }

    .output-card {
      margin-top: 24px;
      border-radius: 20px;
      padding: 16px;
      background: color-mix(in srgb, canvasText 7%, transparent);
      border: 1px solid color-mix(in srgb, canvasText 12%, transparent);
    }

    .output-label {
      margin: 0 0 10px;
      color: color-mix(in srgb, canvasText 62%, transparent);
      font-weight: 700;
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    #output {
      min-height: 56px;
      font-size: clamp(2rem, 8vw, 4.5rem);
      line-height: 1.15;
      word-break: break-word;
      font-family: "Noto Sans Mono CJK SC", "WenQuanYi Micro Hei Mono",
        ui-monospace, "Cascadia Mono", "Menlo", monospace;
      font-variant-east-asian: full-width;
      font-feature-settings: "fwid" 1;
    }

    .examples {
      margin-top: 22px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .example {
      border: 1px solid color-mix(in srgb, canvasText 14%, transparent);
      background: transparent;
      padding: 8px 12px;
      font-size: 0.95rem;
      font-weight: 600;
    }

    footer {
      margin-top: 22px;
      color: color-mix(in srgb, canvasText 55%, transparent);
      font-size: 0.9rem;
    }

    code {
      background: color-mix(in srgb, canvasText 10%, transparent);
      padding: 2px 5px;
      border-radius: 5px;
    }

    .modes {
      display: flex;
      gap: 8px;
      margin: 0 0 22px;
      flex-wrap: nowrap;
    }

    .mode-btn {
      background: color-mix(in srgb, canvasText 12%, transparent);
      color: canvasText;
    }

    .mode-btn.active {
      background: #dc2626;
      color: white;
    }

    .chunk-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .chunk-list .output-card {
      margin-top: 0;
    }

    .art-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }

    .art-head .output-label {
      margin: 0;
    }

    .icon-copy {
      flex: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 34px;
      height: 34px;
      padding: 0;
      border-radius: 8px;
      background: color-mix(in srgb, canvasText 12%, transparent);
      color: canvasText;
    }

    .icon-copy svg {
      width: 16px;
      height: 16px;
    }

    input[type="file"] {
      display: block;
      width: 100%;
      box-sizing: border-box;
      border-radius: 12px;
      border: 1px solid color-mix(in srgb, canvasText 18%, transparent);
      background: color-mix(in srgb, canvas 95%, canvasText 5%);
      color: canvasText;
      padding: 12px 14px;
      font: inherit;
      font-size: 1rem;
    }

    select {
      width: min(240px, 100%);
      border-radius: 12px;
      border: 1px solid color-mix(in srgb, canvasText 18%, transparent);
      background: color-mix(in srgb, canvas 95%, canvasText 5%);
      color: canvasText;
      padding: 12px 40px 12px 14px;
      font: inherit;
      font-size: 1rem;
      outline: none;
      box-sizing: border-box;
      appearance: none;
      background-image: linear-gradient(45deg, transparent 50%, canvasText 50%),
        linear-gradient(135deg, canvasText 50%, transparent 50%);
      background-position: calc(100% - 18px) calc(50% - 3px), calc(100% - 12px) calc(50% - 3px);
      background-size: 6px 6px, 6px 6px;
      background-repeat: no-repeat;
    }

    select:focus {
      border-color: #dc2626;
      box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.16);
    }

    pre.art {
      margin: 0;
      overflow-x: auto;
      white-space: pre;
      font-family: "Noto Sans Mono CJK SC", "WenQuanYi Micro Hei Mono",
        ui-monospace, "Cascadia Mono", "Menlo", monospace;
      /* Force fixed advance width so Han glyphs sit on a strict grid even
         when the matched CJK font isn't strictly monospaced. */
      font-variant-east-asian: full-width;
      font-feature-settings: "fwid" 1;
      font-size: clamp(10px, 2.6vw, 15px);
      line-height: 1.05;
      letter-spacing: 0;
      color: canvasText;
    }
  </style>
</head>

<body>
  <main>
    <h1>receiptify</h1>

    <div class="modes">
      <button class="mode-btn active" type="button" data-mode="text"
        title="Text → Hanzi" aria-label="Text to Hanzi">A→汉</button>
      <button class="mode-btn" type="button" data-mode="image"
        title="Image → Hanzi art" aria-label="Image to Hanzi art">🖼→汉</button>
      <button class="mode-btn" type="button" data-mode="bigtext"
        title="Big text → Hanzi art" aria-label="Big text to Hanzi art">bigtext</button>
    </div>

    <section id="text-mode">
    <label for="input">English phrase</label>
    <textarea id="input" placeholder="Try: ...."></textarea>

    <label for="length">Output length (optional)</label>
    <input id="length" type="number" min="1" step="1" placeholder="Leave blank for default">
    <p class="hint" id="length-hint">
      Provide a positive number to truncate or repeat the result so it fills exactly that many characters.
    </p>

    <div class="row">
      <button id="convert">Convert</button>
      <button id="copy" type="button">Copy result</button>
      <label class="toggle" for="dots">
        <input type="checkbox" id="dots" checked>
        Separator dots (·)
      </label>
      <label class="check-row" for="tts-voice-tag">
        <input type="checkbox" id="tts-voice-tag" checked>
        Add TTS voice tag
      </label>
      <span class="hint" id="status"></span>
    </div>

    <section class="output-card">
      <p class="output-label">Result</p>
      <div id="output">海喽·克劳德弗莱尔·沃克斯</div>
    </section>

    <div class="examples">
{{EXAMPLE_BUTTONS}}
    </div>
    </section>

    <section id="image-mode" hidden>
      <label for="image-input">Upload an image</label>
      <input id="image-input" type="file" accept="image/*">
      <details class="hint-block">
        <summary>How this works</summary>
        <p class="hint">
          The picture is sampled at its own aspect ratio onto a 15-wide strip and
          tiled vertically to fill 32 rows. Each cell becomes a Chinese character
          (denser glyphs for darker areas, spaces for the brightest). The 33rd
          line is a fixed <code>Cheer100 </code> footer, so output is exactly 33
          lines of 15 characters.
        </p>
      </details>

      <div class="row">
        <button id="art-convert" type="button">Generate art</button>
        <button id="art-copy" type="button">Copy art</button>
        <span class="hint" id="art-status"></span>
      </div>

      <section class="output-card">
        <p class="output-label">Hanzi art (33 &times; 15)</p>
        <pre id="art-output" class="art"></pre>
      </section>

      <canvas id="art-canvas" width="15" height="33" hidden></canvas>
    </section>

    <section id="bigtext-mode" hidden>
      <label for="bigtext-input">Text to render</label>
      <textarea id="bigtext-input" placeholder="Type a short phrase..."></textarea>
      <details class="hint-block">
        <summary>How this works</summary>
        <p class="hint">
          Horizontal mode rotates the artwork 90&deg; clockwise before sampling.
          Vertical mode keeps glyphs upright and scales each character to span the
          15-character width. Every chunk fills 32 lines and ends with a fixed
          <code>Cheer100 </code> footer. Long text is split into stacked chunks;
          copy each one separately with its copy icon. Copied text has no line
          breaks.
        </p>
      </details>

      <details class="bigtext-panel">
        <summary>Font &amp; formatting</summary>
        <div class="bigtext-panel-body">
          <div class="bigtext-control bigtext-font">
            <label for="bigtext-font">Font</label>
            <select id="bigtext-font">
              <option value="sans" selected>Bold Sans</option>
              <option value="serif">Classic Serif</option>
              <option value="comic">Comic Neue</option>
              <option value="script">Handwritten Script</option>
              <option value="gothic">Gothic Blackletter</option>
            </select>
          </div>
          <div class="bigtext-panel-grid">
            <div class="bigtext-control">
              <label for="bigtext-font-size">Font size <span class="slider-value" id="bigtext-font-size-value">80px</span></label>
              <input id="bigtext-font-size" type="range" min="20" max="200" step="2" value="80">
            </div>
            <div class="bigtext-control">
              <label for="bigtext-font-weight">Font weight <span class="slider-value" id="bigtext-font-weight-value">600</span></label>
              <input id="bigtext-font-weight" type="range" min="100" max="900" step="50" value="600">
            </div>
            <div class="bigtext-control">
              <label for="bigtext-letter-spacing">Letter spacing <span class="slider-value" id="bigtext-letter-spacing-value">0px</span></label>
              <input id="bigtext-letter-spacing" type="range" min="-50" max="60" step="1" value="0">
            </div>
          </div>
          <div class="row bigtext-options">
            <label class="toggle">
              <input type="radio" name="bigtext-orientation" value="horizontal" checked>
              Horizontal
            </label>
            <label class="toggle">
              <input type="radio" name="bigtext-orientation" value="vertical">
              Vertical
            </label>
            <label class="toggle">
              <input type="checkbox" id="bigtext-latin-toggle">
              Include wide Latin characters (M, W, &mdash;)
            </label>
            <label class="toggle">
              <input type="checkbox" id="bigtext-invert-toggle">
              Invert (swap ink &amp; blank)
            </label>
          </div>
        </div>
      </details>

      <div class="row">
        <button id="bigtext-convert" type="button">Generate big text</button>
        <button id="bigtext-reset" type="button">Reset defaults</button>
        <span class="hint" id="bigtext-status"></span>
      </div>

      <div id="bigtext-output" class="chunk-list"></div>
    </section>

    <footer>
      mrdelayer - <a href="https://github.com/mr-delayer/receiptify">github</a>
    </footer>
  </main>

  <script>
    const input = document.querySelector("#input");
    const output = document.querySelector("#output");
    const status = document.querySelector("#status");
    const convert = document.querySelector("#convert");
    const copy = document.querySelector("#copy");
    const dots = document.querySelector("#dots");
    const outputLength = document.querySelector("#length");
    const voiceTag = document.querySelector("#tts-voice-tag");
    const memePhrases = [
      "My house smells like gym socks and regret, but at least the chips are still crunchy.",
      "I tried to flirt in the elevator but just ended up describing my latest belly-flop into nacho cheese.",
      "If you need me I'll be microwaving pizza rolls until the fire alarm gives up and cries.",
      "I still owe my gastroenterologist a thank-you card for tolerating my midnight burrito experiments.",
      "My love life is less of a romance and more a chemically enhanced fart playlist.",
      "I once misheard 'swipe right' as 'swipe fry' and now my dating profile is a public tribute to onion rings.",
      "Love me or hate me, but my favorite seasoning is a combo of sarcasm and leftover gym socks.",
      "My selfie routine is 10% lighting, 90% hiding the chili burrito aftermath."
    ];
    input.value = memePhrases[Math.floor(Math.random() * memePhrases.length)];

    async function transliterate() {
      const text = input.value.trim();

      const trimmedLength = outputLength.value.trim();
      let desiredLength = null;
      if (trimmedLength) {
        const parsed = Number(trimmedLength);
        if (!Number.isInteger(parsed) || parsed <= 0) {
          status.textContent = "Length must be a positive integer.";
          return;
        }
        desiredLength = parsed;
      }

      if (!text) {
        output.textContent = "";
        status.textContent = "Enter some text first.";
        return;
      }

      status.textContent = "Converting...";

        try {
          const res = await fetch("/api", {
            method: "POST",
            headers: {
              "content-type": "application/json"
            },
            body: JSON.stringify({
              text,
              separator: dots.checked ? "·" : "",
              length: desiredLength,
              ttsTag: voiceTag.checked
            })
          });

        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.error || "Request failed");
        }

        output.textContent = data.output;
        status.textContent = "Done.";
      } catch (err) {
        status.textContent = "Error: " + err.message;
      }
    }

    convert.addEventListener("click", transliterate);

    dots.addEventListener("change", () => {
      if (input.value.trim()) {
        transliterate();
      }
    });

    outputLength.addEventListener("blur", () => {
      if (input.value.trim()) {
        transliterate();
      }
    });

    voiceTag.addEventListener("change", () => {
      if (input.value.trim()) {
        transliterate();
      }
    });

    input.addEventListener("keydown", event => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        transliterate();
      }
    });

    copy.addEventListener("click", async () => {
      const text = output.textContent.trim();

      if (!text) {
        status.textContent = "Nothing to copy.";
        return;
      }

      await navigator.clipboard.writeText(text);
      status.textContent = "Copied.";
    });

    document.querySelectorAll(".example").forEach(button => {
      button.addEventListener("click", () => {
        input.value = button.dataset.text;
        transliterate();
      });
    });

    // --- Image -> Hanzi art mode -------------------------------------------
    // 15 wide x 33 tall grid. Every output cell is a single character drawn
    // from a brightness ramp of allowed characters: a space (brightest),
    // then Chinese characters of increasing ink density (darkest). The copy
    // buffer is the raw 495-character string (no newlines); the visible
    // grid only inserts line breaks for display.
    const ART_W = 15;
    const ART_H = 33;
    // Light -> dark. Index 0 is a space; the rest are Chinese characters
    // ordered by roughly increasing stroke density.
    const ART_RAMP = [
      " ", "丶", "一", "二", "三", "十", "土", "王", "木", "本",
      "禾", "田", "由", "車", "東", "其", "直", "具", "青", "面",
      "革", "頁", "風", "骨", "鬼", "高", "馬", "魚", "鳥", "鹿",
      "麥", "黑", "鼎", "鼠", "齊", "齒", "龍", "龜", "鑫", "矗",
      "麤", "鬱"
    ];
    // Non-space filler used whenever a space would land next to another space.
    const ART_FILLER = "丶";
    // Fixed last line (line 33) of every chunk: a leading space, "Cheer100 ",
    // then five low-density Hanzi. Exactly ART_W (15) characters.
    const ART_FOOTER = " Cheer100 " + "丶一二三丁";

    const imageInput = document.querySelector("#image-input");
    const artConvert = document.querySelector("#art-convert");
    const artCopy = document.querySelector("#art-copy");
    const artStatus = document.querySelector("#art-status");
    const artOutput = document.querySelector("#art-output");
    const artCanvas = document.querySelector("#art-canvas");

    let lastImage = null;

    function buildArt(img) {
      // Sample the image at its own aspect ratio onto a 15-wide tile, then
      // repeat that tile vertically to fill 33 rows. This keeps the picture
      // undistorted instead of stretching one copy over the whole grid.
      const tileH = Math.max(1, Math.round((ART_W * img.height) / img.width));
      artCanvas.width = ART_W;
      artCanvas.height = tileH;
      const ctx = artCanvas.getContext("2d", { willReadFrequently: true });
      ctx.imageSmoothingEnabled = true;
      // Composite over white so transparent pixels read as "bright".
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, ART_W, tileH);
      ctx.drawImage(img, 0, 0, ART_W, tileH);

      const pixels = ctx.getImageData(0, 0, ART_W, tileH).data;
      const maxIndex = ART_RAMP.length - 1;

      // Resolve the tile to ramp indices once, then tile by row.
      const tile = [];
      for (let y = 0; y < tileH; y++) {
        const row = [];
        for (let x = 0; x < ART_W; x++) {
          const p = (y * ART_W + x) * 4;
          const a = pixels[p + 3] / 255;
          const lum =
            (0.299 * pixels[p] + 0.587 * pixels[p + 1] + 0.114 * pixels[p + 2]) * a +
            255 * (1 - a);
          let idx = Math.round((1 - lum / 255) * maxIndex);
          if (idx < 0) idx = 0;
          if (idx > maxIndex) idx = maxIndex;
          row.push(idx);
        }
        tile.push(row);
      }

      let raw = "";
      // Art fills the first ART_H - 1 = 32 lines; line 33 is the fixed footer.
      for (let y = 0; y < ART_H - 1; y++) {
        const row = tile[y % tileH]; // wrap -> vertical tiling
        for (let x = 0; x < ART_W; x++) {
          let ch = ART_RAMP[row[x]];
          if (ch === " ") {
            ch = ART_FILLER; // replace all spaces except the footer
          }
          raw += ch;
        }
      }
      raw += ART_FOOTER; // " Cheer100 丶一二三丁" as the last line
      return raw; // exactly ART_W * ART_H chars, no newlines
    }

    function renderArt(raw) {
      const lines = [];
      for (let i = 0; i < ART_H; i++) {
        lines.push(raw.slice(i * ART_W, i * ART_W + ART_W));
      }
      // Display-only: full-width forms keep ASCII (the footer) + spaces on the
      // same monospace grid as the Hanzi. The copy buffer is left untouched.
      artOutput.textContent = toFullWidth(lines.join("\n"));
      artOutput.dataset.raw = raw;               // copy buffer stays newline-free
    }

    function generateArt() {
      if (!lastImage) {
        artStatus.textContent = "Choose an image first.";
        return;
      }
      try {
        renderArt(buildArt(lastImage));
        artStatus.textContent = "Done.";
      } catch (err) {
        artStatus.textContent = "Error: " + err.message;
      }
    }

    imageInput.addEventListener("change", () => {
      const file = imageInput.files && imageInput.files[0];
      if (!file) return;
      artStatus.textContent = "Loading image...";
      const img = new Image();
      const objectUrl = URL.createObjectURL(file);
      img.onload = () => {
        lastImage = img;
        URL.revokeObjectURL(objectUrl);
        generateArt();
      };
      img.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        artStatus.textContent = "Could not load that image.";
      };
      img.src = objectUrl;
    });

    artConvert.addEventListener("click", generateArt);

    artCopy.addEventListener("click", async () => {
      const raw = artOutput.dataset.raw || "";
      if (!raw) {
        artStatus.textContent = "Nothing to copy.";
        return;
      }
      try {
        await navigator.clipboard.writeText(raw); // raw has no newlines
        artStatus.textContent = "Copied (no line breaks).";
      } catch (err) {
        artStatus.textContent = "Copy failed: " + err.message;
      }
    });

    // --- Big text -> Hanzi art mode ----------------------------------------
    // Render text as large glyphs and sample into the same 15-wide strip used
    // by image mode. Horizontal orientation rotates glyphs 90 degrees clockwise
    // before sampling; vertical orientation keeps them upright and scales each
    // glyph to span the strip width. Long text is split into independent 15x33
    // chunks, each copyable on its own. Reuses ART_W/ART_H/ART_RAMP/ART_FILLER
    // and the brightness ramp + space-substitution rules from image mode. Copy
    // buffers are raw 495-char strings, no newlines.
    const bigtextInput = document.querySelector("#bigtext-input");
    const bigtextConvert = document.querySelector("#bigtext-convert");
    const bigtextStatus = document.querySelector("#bigtext-status");
    const bigtextOutput = document.querySelector("#bigtext-output");
    const bigtextFontSelect = document.querySelector("#bigtext-font");
    const bigtextFontSizeInput = document.querySelector("#bigtext-font-size");
    const bigtextFontWeightInput = document.querySelector("#bigtext-font-weight");
    const bigtextOrientationInputs = document.querySelectorAll('input[name="bigtext-orientation"]');
    const bigtextLatinToggle = document.querySelector("#bigtext-latin-toggle");
    const bigtextInvertToggle = document.querySelector("#bigtext-invert-toggle");
    const bigtextLetterSpacingInput = document.querySelector("#bigtext-letter-spacing");
    const bigtextFontSizeValue = document.querySelector("#bigtext-font-size-value");
    const bigtextFontWeightValue = document.querySelector("#bigtext-font-weight-value");
    const bigtextLetterSpacingValue = document.querySelector("#bigtext-letter-spacing-value");
    const bigtextResetButton = document.querySelector("#bigtext-reset");
    // Font stacks for big text rendering; each entry falls back through
    // commonly available families to keep glyph coverage broad.
    const BIGTEXT_FONT_MAP = {
      sans: '"Arial Black", "Noto Sans CJK SC", system-ui, sans-serif',
      serif: '"Playfair Display", "Times New Roman", "Songti SC", serif',
      comic: '"Comic Neue", "Comic Sans MS", "Marker Felt", cursive',
      script: '"Lucida Handwriting", "Brush Script MT", "KaiTi", cursive',
      gothic: '"UnifrakturCook", "Old English Text MT", "Gothic A1", serif'
    };
    const BIGTEXT_FONT_DEFAULT_WEIGHT = {
      sans: 600,
      serif: 700,
      comic: 600,
      script: 500,
      gothic: 700
    };
    const BIGTEXT_DEFAULT_WEIGHT = 600;
    const BIGTEXT_DEFAULT_SIZE = 80;
    const BIGTEXT_MIN_SIZE = 20;
    const BIGTEXT_MAX_SIZE = 200;
    const BIGTEXT_MIN_WEIGHT = 100;
    const BIGTEXT_MAX_WEIGHT = 900;
    const BIGTEXT_DEFAULT_LETTER_SPACING = 0;
    const BIGTEXT_MIN_LETTER_SPACING = -50;
    const BIGTEXT_MAX_LETTER_SPACING = 60;
    const BIGTEXT_FORBIDDEN_CHAR = "一";
    const BIGTEXT_SUBSTITUTE_CHAR = "丿";
    const BIGTEXT_RAMP = ART_RAMP.map(ch =>
      ch === BIGTEXT_FORBIDDEN_CHAR ? BIGTEXT_SUBSTITUTE_CHAR : ch
    );
    const BIGTEXT_FOOTER = ART_FOOTER.split(BIGTEXT_FORBIDDEN_CHAR).join(BIGTEXT_SUBSTITUTE_CHAR);
    // Optional extra glyphs for the brightness ramp: Latin/punctuation characters
    // that (unlike most Latin letters) keep a fixed ~1em advance width in
    // proportional fonts, so they stay on-grid when the art is pasted elsewhere.
    // Each is spliced in next to a Hanzi of comparable ink density.
    const BIGTEXT_LATIN_INSERTS = [
      { after: "丶", char: "—" }, // em dash: thin full-width stroke, light
      { after: "革", char: "M" },      // dense multi-stroke capital, upper-mid
      { after: "M", char: "W" }        // dense multi-stroke capital, upper-mid
    ];
    const BIGTEXT_LATIN_RAMP = BIGTEXT_RAMP.reduce((acc, ch) => {
      acc.push(ch);
      // Chase chained inserts (e.g. an insert placed after another insert)
      // until no further match is found.
      let last = ch;
      let matched = true;
      while (matched) {
        matched = false;
        for (const insert of BIGTEXT_LATIN_INSERTS) {
          if (insert.after === last) {
            acc.push(insert.char);
            last = insert.char;
            matched = true;
            break;
          }
        }
      }
      return acc;
    }, []);
    const BIGTEXT_MAX_RUN = 3;
    // Caps consecutive repeats of the same ramp character within the sampled
    // glyph pixels ("ink") at BIGTEXT_MAX_RUN by nudging overruns to a
    // neighboring density level. Structural filler/gap rows bypass this.
    function createRunLimiter(ramp, maxRun) {
      const indexOf = new Map();
      ramp.forEach((ch, i) => {
        if (!indexOf.has(ch)) indexOf.set(ch, i);
      });
      let lastChar = null;
      let run = 0;
      function limit(ch) {
        if (ch === lastChar) {
          run++;
        } else {
          lastChar = ch;
          run = 1;
        }
        if (run <= maxRun) {
          return ch;
        }
        const idx = indexOf.has(ch) ? indexOf.get(ch) : -1;
        const up = idx >= 0 ? ramp[idx + 1] : undefined;
        const down = idx >= 0 ? ramp[idx - 1] : undefined;
        const substitute = up && up !== ch ? up : (down && down !== ch ? down : ART_FILLER);
        lastChar = substitute;
        run = 1;
        return substitute;
      }
      // Call after pushing structural filler/gap content that bypasses limit(),
      // so a coincidental match on the far side of a gap isn't mistaken for a
      // continuation of the run on the near side.
      limit.reset = function reset() {
        lastChar = null;
        run = 0;
      };
      return limit;
    }
    const COPY_ICON =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2">' +
      '</rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1">' +
      '</path></svg>';
    const BIGTEXT_MAX_RENDER_ROWS = 4096;
    let bigtextWeightWasEdited = false;
    let bigtextCurrentFontKey = "sans";

    function updateSliderDisplay(inputEl, outputEl, formatter = (value) => String(value)) {
      if (!inputEl || !outputEl) return;
      const numeric = Number(inputEl.value);
      const source = Number.isFinite(numeric) ? numeric : inputEl.value;
      outputEl.textContent = formatter(source);
    }

    function formatPx(value) {
      const numeric = Number(value);
      return (Number.isFinite(numeric) ? Math.round(numeric) : value) + "px";
    }

    function formatNumber(value) {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? Math.round(numeric).toString() : String(value);
    }

    function resetBigtextControls() {
      if (bigtextFontSelect) {
        bigtextFontSelect.value = "sans";
      }
      bigtextCurrentFontKey = getBigtextFontKey();
      if (bigtextFontSizeInput) {
        bigtextFontSizeInput.value = BIGTEXT_DEFAULT_SIZE;
        updateSliderDisplay(bigtextFontSizeInput, bigtextFontSizeValue, formatPx);
      }
      if (bigtextFontWeightInput) {
        const defaultWeight = getBigtextDefaultWeight(bigtextCurrentFontKey);
        bigtextFontWeightInput.value = defaultWeight;
        bigtextWeightWasEdited = false;
        updateSliderDisplay(bigtextFontWeightInput, bigtextFontWeightValue, formatNumber);
      }
      if (bigtextLetterSpacingInput) {
        bigtextLetterSpacingInput.value = BIGTEXT_DEFAULT_LETTER_SPACING;
        updateSliderDisplay(bigtextLetterSpacingInput, bigtextLetterSpacingValue, formatPx);
      }
      const defaultOrientation = "horizontal";
      bigtextOrientationInputs.forEach(input => {
        input.checked = input.value === defaultOrientation;
      });
      if (bigtextLatinToggle) {
        bigtextLatinToggle.checked = false;
      }
      if (bigtextInvertToggle) {
        bigtextInvertToggle.checked = false;
      }
      maybeRegenerateBigText();
    }

    function getBigtextOrientation() {
      for (const input of bigtextOrientationInputs) {
        if (input.checked) {
          return input.value;
        }
      }
      return "horizontal";
    }

    function getBigtextIncludeLatin() {
      return !!(bigtextLatinToggle && bigtextLatinToggle.checked);
    }

    function getBigtextInvert() {
      return !!(bigtextInvertToggle && bigtextInvertToggle.checked);
    }

    function getBigtextFontKey() {
      const value = bigtextFontSelect ? bigtextFontSelect.value : "sans";
      return Object.prototype.hasOwnProperty.call(BIGTEXT_FONT_MAP, value) ? value : "sans";
    }

    function getBigtextDefaultWeight(fontKey) {
      const key = Object.prototype.hasOwnProperty.call(BIGTEXT_FONT_DEFAULT_WEIGHT, fontKey)
        ? fontKey
        : "sans";
      return BIGTEXT_FONT_DEFAULT_WEIGHT[key] || BIGTEXT_DEFAULT_WEIGHT;
    }

    function resolveBigtextFont(fontKey, explicitWeight) {
      const key = Object.prototype.hasOwnProperty.call(BIGTEXT_FONT_MAP, fontKey) ? fontKey : "sans";
      const family = BIGTEXT_FONT_MAP[key];
      const defaultWeight = getBigtextDefaultWeight(key);
      let weight = defaultWeight;
      if (Number.isFinite(explicitWeight)) {
        const clamped = Math.round(
          Math.min(BIGTEXT_MAX_WEIGHT, Math.max(BIGTEXT_MIN_WEIGHT, explicitWeight))
        );
        weight = clamped;
      }
      return { key, family, weight, defaultWeight };
    }

    function getBigtextFontSize() {
      if (!bigtextFontSizeInput) {
        return BIGTEXT_DEFAULT_SIZE;
      }
      const raw = Number.parseFloat(bigtextFontSizeInput.value || "");
      if (!Number.isFinite(raw)) {
        bigtextFontSizeInput.value = BIGTEXT_DEFAULT_SIZE;
        updateSliderDisplay(bigtextFontSizeInput, bigtextFontSizeValue, formatPx);
        return BIGTEXT_DEFAULT_SIZE;
      }
      const clamped = Math.round(
        Math.min(BIGTEXT_MAX_SIZE, Math.max(BIGTEXT_MIN_SIZE, raw))
      );
      if (clamped !== raw) {
        bigtextFontSizeInput.value = clamped;
      }
      updateSliderDisplay(bigtextFontSizeInput, bigtextFontSizeValue, formatPx);
      return clamped;
    }

    function getBigtextFontWeight(fontKey) {
      const defaultWeight = getBigtextDefaultWeight(fontKey);
      if (!bigtextFontWeightInput) {
        return defaultWeight;
      }
      const rawValue = (bigtextFontWeightInput.value || "").trim();
      if (!rawValue) {
        bigtextFontWeightInput.value = defaultWeight;
        bigtextWeightWasEdited = false;
        updateSliderDisplay(bigtextFontWeightInput, bigtextFontWeightValue, formatNumber);
        return defaultWeight;
      }
      const parsed = Number.parseInt(rawValue, 10);
      if (!Number.isFinite(parsed)) {
        bigtextFontWeightInput.value = defaultWeight;
        bigtextWeightWasEdited = false;
        updateSliderDisplay(bigtextFontWeightInput, bigtextFontWeightValue, formatNumber);
        return defaultWeight;
      }
      const clamped = Math.round(
        Math.min(BIGTEXT_MAX_WEIGHT, Math.max(BIGTEXT_MIN_WEIGHT, parsed))
      );
      if (clamped !== parsed) {
        bigtextFontWeightInput.value = clamped;
      }
      updateSliderDisplay(bigtextFontWeightInput, bigtextFontWeightValue, formatNumber);
      return clamped;
    }

    function getBigtextLetterSpacing() {
      if (!bigtextLetterSpacingInput) {
        return BIGTEXT_DEFAULT_LETTER_SPACING;
      }
      const raw = Number.parseFloat(bigtextLetterSpacingInput.value || "");
      if (!Number.isFinite(raw)) {
        bigtextLetterSpacingInput.value = BIGTEXT_DEFAULT_LETTER_SPACING;
        updateSliderDisplay(bigtextLetterSpacingInput, bigtextLetterSpacingValue, formatPx);
        return BIGTEXT_DEFAULT_LETTER_SPACING;
      }
      const clamped = Math.round(
        Math.min(BIGTEXT_MAX_LETTER_SPACING, Math.max(BIGTEXT_MIN_LETTER_SPACING, raw))
      );
      if (clamped !== raw) {
        bigtextLetterSpacingInput.value = clamped;
      }
      updateSliderDisplay(bigtextLetterSpacingInput, bigtextLetterSpacingValue, formatPx);
      return clamped;
    }

    bigtextCurrentFontKey = getBigtextFontKey();
    updateSliderDisplay(bigtextFontSizeInput, bigtextFontSizeValue, formatPx);
    updateSliderDisplay(bigtextFontWeightInput, bigtextFontWeightValue, formatNumber);
    updateSliderDisplay(bigtextLetterSpacingInput, bigtextLetterSpacingValue, formatPx);

    function makeChunkAccumulator(footer = ART_FOOTER) {
      const bodyHeight = ART_H - 1;
      const fillerRow = ART_FILLER.repeat(ART_W);
      const fillerChunkBody = fillerRow.repeat(bodyHeight);
      const chunks = [];
      let chunkBody = "";
      let rowsInChunk = 0;

      function emitChunk() {
        if (chunkBody !== fillerChunkBody) {
          chunks.push(chunkBody + footer);
        }
        chunkBody = "";
        rowsInChunk = 0;
      }

      function pushRow(row) {
        for (let i = 0; i < row.length; i++) {
          let ch = row[i];
          if (ch === " ") {
            ch = ART_FILLER;
          }
          chunkBody += ch;
        }
        rowsInChunk++;
        if (rowsInChunk === bodyHeight) {
          emitChunk();
        }
      }

      function finalize() {
        if (!rowsInChunk) {
          return;
        }
        do {
          pushRow(fillerRow);
        } while (rowsInChunk > 0);
      }

      return { pushRow, finalize, chunks };
    }

    const GRAPHEME_SEGMENTER = typeof Intl !== "undefined" && Intl.Segmenter
      ? new Intl.Segmenter(undefined, { granularity: "grapheme" })
      : null;

    function splitGraphemes(value) {
      if (!value) return [];
      if (GRAPHEME_SEGMENTER) {
        return Array.from(GRAPHEME_SEGMENTER.segment(value), segment => segment.segment);
      }
      return Array.from(value);
    }

    function buildBigChunks(text, orientation, fontKey, fontSize, fontWeight, letterSpacing, includeLatin, invert) {
      const trimmed = text.replace(/^\s+|\s+$/g, "");
      if (!trimmed) return [];
      const glyphs = splitGraphemes(trimmed);
      return orientation === "vertical"
        ? buildVerticalChunks(glyphs, fontKey, fontSize, fontWeight, letterSpacing, includeLatin, invert)
        : buildHorizontalChunks(glyphs, fontKey, fontSize, fontWeight, letterSpacing, includeLatin, invert);
    }

    function buildHorizontalChunks(glyphs, fontKey, fontSize, fontWeight, letterSpacing, includeLatin, invert) {
      const F = Number.isFinite(fontSize)
        ? Math.max(BIGTEXT_MIN_SIZE, Math.min(BIGTEXT_MAX_SIZE, Math.round(fontSize)))
        : BIGTEXT_DEFAULT_SIZE;
      const spacing = Number.isFinite(letterSpacing)
        ? Math.max(BIGTEXT_MIN_LETTER_SPACING, Math.min(BIGTEXT_MAX_LETTER_SPACING, letterSpacing))
        : BIGTEXT_DEFAULT_LETTER_SPACING;
      const { family, weight } = resolveBigtextFont(fontKey, fontWeight);
      const font = weight + " " + F + "px " + family;
      const pad = Math.round(F * 0.08);
      const textH = Math.ceil(F * 1.2);
      const scale = ART_W / textH;
      const ramp = includeLatin ? BIGTEXT_LATIN_RAMP : BIGTEXT_RAMP;
      const runLimiter = createRunLimiter(ramp, BIGTEXT_MAX_RUN);

      const measureCanvas = document.createElement("canvas");
      const measureCtx = measureCanvas.getContext("2d");
      measureCtx.font = font;

      const charWidths = glyphs.map(ch => measureCtx.measureText(ch).width);

      const prefixWidths = [0];
      for (let i = 0; i < charWidths.length; i++) {
        prefixWidths[i + 1] = prefixWidths[i] + charWidths[i];
      }

      function measureRange(start, end) {
        if (end <= start) return 0;
        const width = prefixWidths[end] - prefixWidths[start];
        const gaps = Math.max(0, end - start - 1);
        return width + gaps * spacing;
      }

      const tmp = document.createElement("canvas");
      const sample = document.createElement("canvas");
      const segments = [];
      let start = 0;
      while (start < glyphs.length) {
        let end = start;
        while (end < glyphs.length) {
          const nextEnd = end + 1;
          const approxWidth = measureRange(start, nextEnd);
          const rows = Math.max(1, Math.round((approxWidth + pad * 2) * scale));
          if (rows > BIGTEXT_MAX_RENDER_ROWS) break;
          end = nextEnd;
        }
        if (end === start) end = start + 1;
        segments.push([start, end]);
        start = end;
      }

      const acc = makeChunkAccumulator(BIGTEXT_FOOTER);

      function sampleSegment(segmentStart, segmentEnd, padLeft, padRight) {
        const segmentText = glyphs.slice(segmentStart, segmentEnd).join("");
        const targetWidth = Math.max(
          1,
          Math.ceil(measureRange(segmentStart, segmentEnd)) + padLeft + padRight
        );

        tmp.width = targetWidth;
        tmp.height = textH;
        const tctx = tmp.getContext("2d");
        tctx.font = font;
        tctx.textAlign = "left";
        tctx.textBaseline = "middle";
        tctx.fillStyle = "#ffffff";
        tctx.fillRect(0, 0, targetWidth, textH);
        tctx.fillStyle = "#000000";

        let cursor = padLeft;
        for (let i = segmentStart; i < segmentEnd; i++) {
          const ch = glyphs[i];
          const width = charWidths[i] || measureCtx.measureText(ch).width;
          tctx.fillText(ch, cursor, textH / 2);
          if (i === segmentEnd - 1) {
            cursor += width;
          } else {
            cursor += width + spacing;
          }
        }

        const rows = Math.max(1, Math.round(targetWidth * scale));
        sample.width = ART_W;
        sample.height = rows;
        const sctx = sample.getContext("2d", { willReadFrequently: true });
        sctx.imageSmoothingEnabled = true;
        sctx.fillStyle = "#ffffff";
        sctx.fillRect(0, 0, ART_W, rows);
        sctx.save();
        sctx.translate(ART_W, 0);
        sctx.rotate(Math.PI / 2);
        sctx.scale(scale, scale);
        sctx.drawImage(tmp, 0, 0);
        sctx.restore();

        const pixels = sctx.getImageData(0, 0, ART_W, rows).data;
        const maxIndex = ramp.length - 1;
        const segmentRows = [];
        for (let y = 0; y < rows; y++) {
          let row = "";
          for (let x = 0; x < ART_W; x++) {
            const p = (y * ART_W + x) * 4;
            const a = pixels[p + 3] / 255;
            const lum =
              (0.299 * pixels[p] + 0.587 * pixels[p + 1] + 0.114 * pixels[p + 2]) * a +
              255 * (1 - a);
            const brightness = invert ? lum / 255 : 1 - lum / 255;
            let idx = Math.round(brightness * maxIndex);
            if (idx < 0) idx = 0;
            if (idx > maxIndex) idx = maxIndex;
            row += runLimiter(ramp[idx]);
          }
          segmentRows.push(row);
        }
        return segmentRows;
      }

      segments.forEach(([segmentStart, segmentEnd], index) => {
        const padLeft = index === 0 ? pad : 0;
        const padRight = index === segments.length - 1 ? pad : 0;
        const segmentRows = sampleSegment(segmentStart, segmentEnd, padLeft, padRight);
        segmentRows.forEach(row => acc.pushRow(row));
      });

      acc.finalize();
      return acc.chunks;
    }

    function buildVerticalChunks(glyphs, fontKey, fontSize, fontWeight, letterSpacing, includeLatin, invert) {
      const F = Number.isFinite(fontSize)
        ? Math.max(BIGTEXT_MIN_SIZE, Math.min(BIGTEXT_MAX_SIZE, Math.round(fontSize)))
        : BIGTEXT_DEFAULT_SIZE;
      const spacing = Number.isFinite(letterSpacing)
        ? Math.max(BIGTEXT_MIN_LETTER_SPACING, Math.min(BIGTEXT_MAX_LETTER_SPACING, letterSpacing))
        : BIGTEXT_DEFAULT_LETTER_SPACING;
      const { family, weight } = resolveBigtextFont(fontKey, fontWeight);
      const font = weight + " " + F + "px " + family;
      const padX = Math.max(2, Math.round(F * 0.02));
      const padY = Math.round(F * 0.1);
      const drawHeight = Math.ceil(F * 1.2) + padY * 2;
      const fillerRow = ART_FILLER.repeat(ART_W);
      const VERTICAL_HEIGHT_FACTOR = 0.8;
      const ramp = includeLatin ? BIGTEXT_LATIN_RAMP : BIGTEXT_RAMP;
      const runLimiter = createRunLimiter(ramp, BIGTEXT_MAX_RUN);

      const measureCanvas = document.createElement("canvas");
      const measureCtx = measureCanvas.getContext("2d");
      measureCtx.font = font;

      const tmp = document.createElement("canvas");
      const sample = document.createElement("canvas");
      const acc = makeChunkAccumulator(BIGTEXT_FOOTER);

      for (let i = 0; i < glyphs.length; i++) {
        const glyph = glyphs[i];
        if (glyph === "\r") continue;
        const nextGlyph = i + 1 < glyphs.length ? glyphs[i + 1] : null;

        if (glyph === "\n") {
          if (nextGlyph !== null) {
            acc.pushRow(fillerRow);
            runLimiter.reset();
          }
          continue;
        }

        if (glyph === " ") {
          if (nextGlyph !== null) {
            acc.pushRow(fillerRow);
            acc.pushRow(fillerRow);
            runLimiter.reset();
          }
          continue;
        }

        const measured = Math.ceil(measureCtx.measureText(glyph).width);
        const drawWidth = Math.max(1, measured) + padX * 2;

        tmp.width = drawWidth;
        tmp.height = drawHeight;
        const tctx = tmp.getContext("2d");
        tctx.font = font;
        tctx.textAlign = "center";
        tctx.textBaseline = "middle";
        tctx.fillStyle = "#ffffff";
        tctx.fillRect(0, 0, drawWidth, drawHeight);
        tctx.fillStyle = "#000000";
        tctx.fillText(glyph, drawWidth / 2, drawHeight / 2);

        const scale = ART_W / drawWidth;
        const rows = Math.max(
          1,
          Math.min(
            BIGTEXT_MAX_RENDER_ROWS,
            Math.round(drawHeight * scale * VERTICAL_HEIGHT_FACTOR)
          )
        );

        sample.width = ART_W;
        sample.height = rows;
        const sctx = sample.getContext("2d", { willReadFrequently: true });
        sctx.imageSmoothingEnabled = true;
        sctx.fillStyle = "#ffffff";
        sctx.fillRect(0, 0, ART_W, rows);
        sctx.save();
        sctx.scale(scale, scale);
        sctx.drawImage(tmp, 0, 0);
        sctx.restore();

        const pixels = sctx.getImageData(0, 0, ART_W, rows).data;
        const maxIndex = ramp.length - 1;

        const rowData = [];
        for (let y = 0; y < rows; y++) {
          let row = "";
          let blank = true;
          for (let x = 0; x < ART_W; x++) {
            const p = (y * ART_W + x) * 4;
            const a = pixels[p + 3] / 255;
            const lum =
              (0.299 * pixels[p] + 0.587 * pixels[p + 1] + 0.114 * pixels[p + 2]) * a +
              255 * (1 - a);
            // Blank/trim detection always uses the uninverted sense of "no ink
            // here" -- it's about the glyph's geometric footprint, not display.
            let geometricIdx = Math.round((1 - lum / 255) * maxIndex);
            if (geometricIdx < 0) geometricIdx = 0;
            if (geometricIdx > maxIndex) geometricIdx = maxIndex;
            if (geometricIdx !== 0) blank = false;
            const brightness = invert ? lum / 255 : 1 - lum / 255;
            let idx = Math.round(brightness * maxIndex);
            if (idx < 0) idx = 0;
            if (idx > maxIndex) idx = maxIndex;
            row += ramp[idx];
          }
          rowData.push({ row, blank });
        }

        let start = 0;
        while (start < rowData.length && rowData[start].blank) start++;
        let end = rowData.length;
        while (end > start && rowData[end - 1].blank) end--;

        let emittedRows = 0;
        for (let y = start; y < end; y++) {
          let limitedRow = "";
          for (const ch of rowData[y].row) {
            limitedRow += runLimiter(ch);
          }
          acc.pushRow(limitedRow);
          emittedRows++;
        }

        if (emittedRows === 0) {
          acc.pushRow(fillerRow);
          runLimiter.reset();
        }

        const shouldAddGap = nextGlyph !== null && nextGlyph !== "\r" && nextGlyph !== "\n" && nextGlyph !== " ";
        if (shouldAddGap) {
          const gapRows = 1 + Math.max(0, Math.round(spacing * scale));
          for (let g = 0; g < gapRows; g++) {
            acc.pushRow(fillerRow);
          }
          runLimiter.reset();
        }
      }

      acc.finalize();
      return acc.chunks;
    }

    // Display-only: map ASCII (the "Cheer100 " prefix) and the space to their
    // full-width Unicode forms so they occupy one full cell and render in the
    // same monospace grid as the Hanzi. The copy buffer keeps plain ASCII.
    function toFullWidth(s) {
      let out = "";
      for (let i = 0; i < s.length; i++) {
        const c = s.charCodeAt(i);
        if (c === 0x20) out += "　"; // space -> ideographic space (U+3000)
        else if (c >= 0x21 && c <= 0x7e) out += String.fromCharCode(c + 0xfee0);
        else out += s[i]; // Hanzi, newlines, etc. pass through unchanged
      }
      return out;
    }

    function renderBigChunks(chunks) {
      bigtextOutput.replaceChildren();
      chunks.forEach((raw, i) => {
        const card = document.createElement("section");
        card.className = "output-card";

        const head = document.createElement("div");
        head.className = "art-head";

        const label = document.createElement("p");
        label.className = "output-label";
        label.textContent =
          chunks.length > 1
            ? "Part " + (i + 1) + " / " + chunks.length + " (33 × 15)"
            : "Hanzi art (33 × 15)";

        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "icon-copy";
        copyBtn.title = "Copy this chunk (no line breaks)";
        copyBtn.dataset.raw = raw; // newline-free copy buffer
        copyBtn.innerHTML = COPY_ICON;

        head.append(label, copyBtn);

        const pre = document.createElement("pre");
        pre.className = "art";
        const lines = [];
        for (let r = 0; r < ART_H; r++) {
          lines.push(raw.slice(r * ART_W, r * ART_W + ART_W));
        }
        // Display-only: full-width forms keep ASCII + spaces on the same grid.
        pre.textContent = toFullWidth(lines.join("\n"));

        card.append(head, pre);
        bigtextOutput.append(card);
      });
    }

    function generateBigText() {
      const orientation = getBigtextOrientation();
      const fontKey = getBigtextFontKey();
      const fontSize = getBigtextFontSize();
      const fontWeight = getBigtextFontWeight(fontKey);
      const letterSpacing = getBigtextLetterSpacing();
      const includeLatin = getBigtextIncludeLatin();
      const invert = getBigtextInvert();
      const chunks = buildBigChunks(
        bigtextInput.value,
        orientation,
        fontKey,
        fontSize,
        fontWeight,
        letterSpacing,
        includeLatin,
        invert
      );
      if (!chunks.length) {
        bigtextOutput.replaceChildren();
        bigtextStatus.textContent = "Enter some text first.";
        return;
      }
      renderBigChunks(chunks);
      bigtextStatus.textContent =
        "Done (" + chunks.length + (chunks.length === 1 ? " chunk)." : " chunks).");
    }

    bigtextConvert.addEventListener("click", generateBigText);

    function maybeRegenerateBigText() {
      if (!bigtextInput.value.trim()) return;
      if (!bigtextOutput.childElementCount) return;
      generateBigText();
    }

    bigtextOrientationInputs.forEach(input => {
      input.addEventListener("change", () => {
        if (!input.checked) return;
        maybeRegenerateBigText();
      });
    });

    if (bigtextLatinToggle) {
      bigtextLatinToggle.addEventListener("change", maybeRegenerateBigText);
    }

    if (bigtextInvertToggle) {
      bigtextInvertToggle.addEventListener("change", maybeRegenerateBigText);
    }

    if (bigtextFontSelect) {
      bigtextFontSelect.addEventListener("change", () => {
        const nextKey = getBigtextFontKey();
        if (bigtextFontWeightInput) {
          const prevDefault = getBigtextDefaultWeight(bigtextCurrentFontKey);
          const currentParsed = Number.parseInt(bigtextFontWeightInput.value || "", 10);
          if (!bigtextWeightWasEdited || currentParsed === prevDefault || Number.isNaN(currentParsed)) {
            const nextDefault = getBigtextDefaultWeight(nextKey);
            bigtextFontWeightInput.value = nextDefault;
            bigtextWeightWasEdited = false;
            updateSliderDisplay(bigtextFontWeightInput, bigtextFontWeightValue, formatNumber);
          }
        }
        bigtextCurrentFontKey = nextKey;
        maybeRegenerateBigText();
      });
    }

    if (bigtextFontSizeInput) {
      bigtextFontSizeInput.addEventListener("input", () => {
        updateSliderDisplay(bigtextFontSizeInput, bigtextFontSizeValue, formatPx);
      });
      bigtextFontSizeInput.addEventListener("change", () => {
        updateSliderDisplay(bigtextFontSizeInput, bigtextFontSizeValue, formatPx);
        maybeRegenerateBigText();
      });
    }

    if (bigtextFontWeightInput) {
      bigtextFontWeightInput.addEventListener("input", () => {
        bigtextWeightWasEdited = true;
        updateSliderDisplay(bigtextFontWeightInput, bigtextFontWeightValue, formatNumber);
      });
      bigtextFontWeightInput.addEventListener("change", () => {
        updateSliderDisplay(bigtextFontWeightInput, bigtextFontWeightValue, formatNumber);
        maybeRegenerateBigText();
      });
    }

    if (bigtextLetterSpacingInput) {
      bigtextLetterSpacingInput.addEventListener("input", () => {
        updateSliderDisplay(bigtextLetterSpacingInput, bigtextLetterSpacingValue, formatPx);
      });
      bigtextLetterSpacingInput.addEventListener("change", () => {
        updateSliderDisplay(bigtextLetterSpacingInput, bigtextLetterSpacingValue, formatPx);
        maybeRegenerateBigText();
      });
    }

    if (bigtextResetButton) {
      bigtextResetButton.addEventListener("click", () => {
        resetBigtextControls();
        bigtextStatus.textContent = "Controls reset to defaults.";
      });
    }

    bigtextOutput.addEventListener("click", async (e) => {
      const btn = e.target.closest(".icon-copy");
      if (!btn) return;
      try {
        await navigator.clipboard.writeText(btn.dataset.raw || "");
        bigtextStatus.textContent = "Copied chunk (no line breaks).";
      } catch (err) {
        bigtextStatus.textContent = "Copy failed: " + err.message;
      }
    });

    document.querySelectorAll(".mode-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const mode = btn.dataset.mode;
        document.querySelectorAll(".mode-btn").forEach(b => {
          b.classList.toggle("active", b === btn);
        });
        document.querySelector("#text-mode").hidden = mode !== "text";
        document.querySelector("#image-mode").hidden = mode !== "image";
        document.querySelector("#bigtext-mode").hidden = mode !== "bigtext";
      });
    });
  </script>
</body>
</html>
"""


# Inject the dynamically rendered example buttons into the page template.
PAGE_HTML = HTML.replace("{{EXAMPLE_BUTTONS}}", EXAMPLE_BUTTONS_HTML)


def response(body, status=200, content_type="text/html; charset=utf-8", headers=None):
    base_headers = {
        "content-type": content_type,
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, POST, OPTIONS",
        "access-control-allow-headers": "content-type"
    }
    if headers:
        base_headers.update(headers)
    return Response.new(
        body,
        to_js({
            "status": status,
            "headers": base_headers
        })
    )


def json_response(data, status=200, cache_control=None):
    headers = {"cache-control": cache_control} if cache_control else None
    return response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        content_type="application/json; charset=utf-8",
        headers=headers
    )


async def on_fetch(request, env):
    if request.method == "OPTIONS":
        return response("", status=204, content_type="text/html")

    url = URL.new(request.url)
    path = url.pathname

    # JSON API endpoint used by the HTML UI.
    if path == "/api":
        if request.method != "POST":
            return json_response(
                {"error": "Use POST with JSON: {\"text\":\"hello world\"}"},
                status=405
            )

        try:
            raw_body = await request.text()
            data = json.loads(raw_body or "{}")
        except Exception:
            return json_response(
                {"error": "Invalid JSON. Use: {\"text\":\"hello world\"}"},
                status=400
            )

        text = str(data.get("text", ""))
        separator = str(data.get("separator", "·"))
        try:
            desired_length = _parse_requested_length(data.get("length"))
        except ValueError:
            return json_response(
                {"error": "Length must be null or a positive non-zero integer."},
                status=400
            )
        use_tts_tag = _coerce_bool(data.get("ttsTag", True))

        cache_key = _cache_key(text, separator, desired_length, use_tts_tag)
        cached_response = await _lookup_cached_response(cache_key)
        if cached_response:
            return cached_response

        output = transliterate_text(text, separator=separator)
        adjusted_output = _apply_requested_length(output, desired_length, use_tts_tag)

        payload = {
            "input": text,
            "output": adjusted_output,
            "separator": separator,
            "note": "Approximate phonetic transliteration, not translation."
        }
        cache_control = f"public, max-age={CACHE_TTL_SECONDS}"
        response_obj = json_response(payload, cache_control=cache_control)
        await _store_cached_response(cache_key, response_obj)
        return response_obj

    # Optional simple GET API:
    # /?q=hello%20world
    q = url.searchParams.get("q")
    if q is not None:
        text = str(q)
        output = transliterate_text(text)

        return json_response({
            "input": text,
            "output": output,
            "note": "Approximate phonetic transliteration, not translation."
        })

    # Main HTML UI.
    return response(PAGE_HTML)
