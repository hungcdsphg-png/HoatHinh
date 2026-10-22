"""Chuẩn hoá chữ trước khi đưa cho giọng đọc: mã sản phẩm, số, đơn vị, số điện thoại.
VD: "W2" -> "vê kép hai", "TD-CA 30kg" -> "tê đê xê a ba mươi ki lô gam",
    "0961.022.023" -> "không chín sáu một, không hai hai, không hai ba"."""
import re

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
LETTERS = {
    "A": "a", "B": "bê", "C": "xê", "D": "đê", "Đ": "đê", "E": "e", "F": "ép", "G": "giê", "H": "hát", "I": "i",
    "J": "giây", "K": "ca", "L": "en lờ", "M": "em", "N": "en", "O": "ô", "P": "pê", "Q": "quy", "R": "rờ", "S": "ét",
    "T": "tê", "U": "u", "V": "vê", "W": "vê kép", "X": "ích", "Y": "i dài", "Z": "dét",
}
UNITS = {
    "kg": "ki lô gam", "g": "gam", "gr": "gam", "mg": "mi li gam", "t": "tấn", "tấn": "tấn",
    "km": "ki lô mét", "m": "mét", "cm": "xen ti mét", "mm": "mi li mét", "inch": "inch",
    "l": "lít", "lít": "lít", "ml": "mi li lít",
    "w": "oát", "kw": "ki lô oát", "v": "vôn", "mah": "mi li am pe giờ", "ah": "am pe giờ", "hz": "héc",
    "h": "giờ", "giờ": "giờ", "s": "giây", "%": "phần trăm", "đ": "đồng", "k": "nghìn", "tr": "triệu", "gb": "ghi ga bai",
}


# Tên chữ cái đọc kiểu tiếng Anh, dùng cho từ viết tắt quốc tế (LCD -> eo si đi, USB -> diu ét bi).
EN_LETTERS = {
    "A": "ây", "B": "bi", "C": "si", "D": "đi", "E": "i", "F": "ép", "G": "gi", "H": "ết", "I": "ai", "J": "giây",
    "K": "cây", "L": "eo", "M": "em", "N": "en", "O": "ô", "P": "pi", "Q": "kiu", "R": "a", "S": "ét", "T": "ti",
    "U": "diu", "V": "vi", "W": "đắp liu", "X": "ích", "Y": "oai", "Z": "dét",
}
# Từ tiếng Anh và từ viết tắt hay gặp -> cách đọc bằng âm tiếng Việt. Khoá viết thường; so khớp nguyên từ, không phân biệt hoa thường.
# Cách đọc người dùng gõ ở tab Âm thanh và cách đọc AI gợi ý luôn được ưu tiên hơn bảng này.
EN_WORDS = {
    # viết tắt đọc thành từ
    "led": "lét", "oled": "ô lét", "wifi": "oai phai", "wi-fi": "oai phai", "vip": "víp", "iso": "i sô", "sim": "sim",
    "gps": "gi pi ét", "ok": "ô kê", "hd": "hát đê", "tv": "ti vi", "pc": "pi xi", "qr": "kiu a",
    "cnc": "xê en xê", "kcs": "ca xê ét", "atm": "a tê em", "vat": "vát", "ceo": "xi i ô", "seo": "xeo",
    # viết tắt tiếng Việt
    "tnhh": "trách nhiệm hữu hạn", "tp": "thành phố", "tp.hcm": "thành phố hồ chí minh", "hcm": "hồ chí minh", "tphcm": "thành phố hồ chí minh",
    "hn": "hà nội", "vn": "việt nam", "vnđ": "đồng", "vnd": "đồng", "sđt": "số điện thoại", "đt": "điện thoại", "cty": "công ty",
    "mtv": "một thành viên", "cp": "cổ phần", "ubnd": "uỷ ban nhân dân", "bhxh": "bảo hiểm xã hội", "gđ": "giám đốc", "ks": "kỹ sư",
    # từ tiếng Anh thông dụng
    "online": "on lai", "offline": "óp lai", "email": "i meo", "mail": "meo", "website": "oép sai", "web": "oép", "internet": "in tơ nét",
    "app": "áp", "smartphone": "xờ mát phôn", "laptop": "láp tóp", "tablet": "táp lét", "camera": "ca mê ra", "video": "vi đi ô", "clip": "cờ líp",
    "file": "phai", "sale": "xeo", "sales": "xeo", "marketing": "ma két tinh", "livestream": "lai xờ trim", "shop": "sốp", "ship": "síp",
    "shipper": "síp pơ", "order": "o đờ", "review": "ri viu", "feedback": "phít béc", "test": "tét", "check": "chéc", "code": "cốt",
    "bluetooth": "bờ lu tút", "tiktok": "tíc tốc", "facebook": "phây búc", "youtube": "diu túp", "zalo": "da lô", "google": "gu gồ",
    "excel": "ích xeo", "windows": "uyn đâu", "sensor": "xen xơ", "loadcell": "lốt xeo", "load cell": "lốt xeo", "model": "mô đeo",
    "series": "xê ri", "mini": "mi ni", "pro": "pờ rô", "max": "mắc", "plus": "pờ lớt", "combo": "com bô", "hotline": "hót lai",
    "logo": "lô gô", "robot": "rô bốt", "chip": "chíp", "server": "xơ vơ", "data": "đa ta", "software": "xóp que", "update": "ắp đết",
    "smart": "xờ mát", "digital": "đi gi tồ", "display": "đít pờ lây", "touch": "tắt", "menu": "me niu", "setup": "xét ắp", "reset": "ri xét",
    "start": "xờ tát", "stop": "xờ tóp", "on": "on", "off": "óp", "mode": "mốt", "level": "le vồ", "team": "tim", "leader": "li đơ",
    "deadline": "đét lai", "meeting": "mít tinh", "content": "con ten", "trend": "tren", "view": "viu", "like": "lai", "share": "se",
    "comment": "com men", "follow": "pho lâu", "idol": "ai đồ", "fan": "phan", "game": "ghêm", "top": "tóp", "hot": "hót", "new": "niu",
    "free": "phờ ri", "premium": "pờ ri mi ầm", "standard": "xờ tan đợt", "basic": "bây xích", "prompt": "pờ rom", "chatbot": "chát bót",
    "claude": "cờ lốt", "chatgpt": "chát gi pi ti", "gemini": "giê mi ni", "token": "tâu cần", "startup": "xờ tát ắp", "outsource": "ao sót",
    "freelance": "phờ ri lan", "freelancer": "phờ ri lan xơ", "manager": "ma ni giơ", "sếp": "sếp", "bug": "bấc", "fix": "phích",
    "backup": "béc ắp", "download": "đao lâu", "upload": "ắp lâu", "link": "linh", "click": "cờ líc", "scan": "xờ can", "print": "pờ rin",
    "barcode": "ba cốt", "indicator": "in đi cây tơ", "weight": "quây", "scale": "xờ keo", "pallet": "pa lét", "container": "công ten nơ",
    "inverter": "in vơ tơ", "motor": "mô tơ", "pin": "pin", "adapter": "a đáp tơ", "module": "mô đun", "relay": "rơ le", "plc": "pi eo si",
}


# Viết tắt trùng với từ tiếng Việt thường gặp: chỉ đổi khi viết HOA đúng như dưới ("ai cũng biết" giữ nguyên).
CASE_WORDS = {"AI": "ây ai", "IT": "ai ti", "UI": "diu ai", "UX": "diu ích", "AN": "ây en"}
_SYLLABLE = re.compile(r"(ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|[bcdghklmnpqrstvx])?[aeiouy]{1,3}(ch|ng|nh|[cmnpt])?")


def _apply_words(text: str) -> str:
    text = re.sub(r"(?<![\wÀ-ỹ])(" + "|".join(CASE_WORDS) + r")(?![\wÀ-ỹ])", lambda m: CASE_WORDS[m.group(1)], text)
    keys = sorted(EN_WORDS, key=len, reverse=True)
    pat = r"(?<![\wÀ-ỹ])(" + "|".join(re.escape(k) for k in keys) + r")(?![\wÀ-ỹ])"
    return re.sub(pat, lambda m: EN_WORDS[m.group(1).lower()], text, flags=re.IGNORECASE)


def _three(n: int, full: bool) -> str:
    tr, ch, dv = n // 100, n // 10 % 10, n % 10
    out = []
    if full or tr:
        out += [DIGITS[tr], "trăm"]
    if ch == 0:
        if dv and (full or tr):
            out.append("linh")
    elif ch == 1:
        out.append("mười")
    else:
        out += [DIGITS[ch], "mươi"]
    if dv:
        if dv == 1 and ch > 1:
            out.append("mốt")
        elif dv == 5 and ch > 0:
            out.append("lăm")
        elif dv == 4 and ch > 1:
            out.append("tư")
        else:
            out.append(DIGITS[dv])
    return " ".join(out)


def so(n: int) -> str:
    """Đọc số nguyên thành chữ."""
    if n == 0:
        return "không"
    if n < 0:
        return "âm " + so(-n)
    groups = []
    while n:
        groups.append(n % 1000)
        n //= 1000
    names = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
    out = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        out.append(_three(g, full=(i < len(groups) - 1)))
        if names[i]:
            out.append(names[i])
    return " ".join(out)


def so_chuoi(s: str) -> str:
    """'1.250' -> một nghìn hai trăm năm mươi; '0,1' / '0.1' -> không phẩy một."""
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):  # dấu chấm ngăn nghìn
        return so(int(s.replace(".", "")))
    m = re.fullmatch(r"(\d+)[.,](\d+)", s)
    if m:
        a, b = m.groups()
        b_txt = so(int(b)) if len(b) <= 2 and not b.startswith("0") else " ".join(DIGITS[int(c)] for c in b)
        return f"{so(int(a))} phẩy {b_txt}"
    if s.isdigit():
        if len(s) > 1 and s.startswith("0"):
            return " ".join(DIGITS[int(c)] for c in s)
        return so(int(s))
    return s


def _phone(m: re.Match) -> str:
    parts = re.split(r"[\s.\-]+", m.group(0).strip())
    return ", ".join(" ".join(DIGITS[int(c)] for c in p) for p in parts if p)


def _code(tok: str) -> str:
    """Mã sản phẩm: W2, TD-CA, X100, RTX4090 -> đánh vần chữ, đọc số."""
    out = []
    for part in re.findall(r"[A-ZĐ]+|\d+(?:[.,]\d+)?", tok):
        if part[0].isdigit():
            out.append(so_chuoi(part))
        else:
            out.append(" ".join(LETTERS.get(ch, ch) for ch in part))
    return " ".join(out)


def _apply_dict(text: str, pron: str) -> str:
    for line in (pron or "").splitlines():
        if "=" not in line:
            continue
        a, b = line.split("=", 1)
        a, b = a.strip(), b.strip()
        if a and b:
            text = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", b, text, flags=re.IGNORECASE)
    return text


def chuan_hoa(text: str, pron: str = "") -> str:
    t = " ".join(str(text or "").split())
    t = _apply_dict(t, pron)  # cách đọc riêng người dùng gõ được ưu tiên trước
    t = _apply_words(t)  # từ tiếng Anh và từ viết tắt hay gặp
    # số điện thoại: 09xx.xxx.xxx, 1900 xxxx …
    t = re.sub(r"(?<![\w.])(?:0\d{2,3}|1[89]00)[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}(?![\w.])", _phone, t)
    # số + đơn vị: 30kg, 0.1g, 1000W, 50%, 2,5 lít
    unit_re = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
    t = re.sub(r"(?<![\w.,])(\d+(?:[.,]\d+)*)\s?(" + unit_re + r")(?![\wÀ-ỹ])",
               lambda m: so_chuoi(m.group(1)) + " " + UNITS[m.group(2).lower()], t, flags=re.IGNORECASE)
    # mã viết hoa có chữ (W2, TD-CA, LCD, X100); bỏ qua từ tiếng Việt viết hoa có dấu (ĐẾM, CÂN …)
    def code(m):
        tok = m.group(0)
        if not re.search(r"[A-ZĐ]", tok):
            return tok
        letters = re.sub(r"[^A-ZĐ]", "", tok)
        if not re.search(r"\d", tok) and "-" not in tok and len(letters) > 4:
            return tok  # từ viết hoa dài (SALE, MARCUS) để giọng đọc tự xử lý
        if tok.isalpha() and tok.isascii() and _SYLLABLE.fullmatch(tok.lower()):
            return tok  # chữ in hoa không dấu nhưng là một tiếng đọc được (GHI, TAY, MUA, RAM): để nguyên
        if tok.isalpha() and tok.isascii() and 2 <= len(tok) <= 4:
            return " ".join(EN_LETTERS[ch] for ch in tok)  # viết tắt quốc tế: LCD -> eo si đi, USB -> diu ét bi
        return _code(tok)
    t = re.sub(r"(?<![\wÀ-ỹ])[A-ZĐ0-9]+(?:-[A-ZĐ0-9]+)*(?![\wÀ-ỹ])", code, t)
    # số còn lại
    t = re.sub(r"(?<![\w])\d+(?:[.,]\d+)*(?![\w])", lambda m: so_chuoi(m.group(0)), t)
    t = t.replace("&", " và ").replace("+", " cộng ").replace("/", " trên ")
    return " ".join(t.split())


if __name__ == "__main__":
    for s in ["Máy W2 mới", "Cân đếm Marcus TD-CA 30kg", "Độ chính xác 0.1g", "Kiểm 1.250 cái ốc", "Hotline 0961.022.023",
              "Bảo hành 24 tháng", "Công suất 1000W, pin 5000mAh", "Giảm 15%", "Màn hình LCD", "Giá 2,5 triệu", "X100 chỉ 21 kg",
              "Model ABC-2024", "Màn hình LED và LCD, cổng USB, kết nối wifi", "Công ty TNHH ABC", "Check hàng online qua app", "Cân có chế độ ON OFF", "GHI TAY SAI SỐ, AI cũng biết ai", "CPU, RAM, API và ERP", "Phòng IT"]:
        print(s, "->", chuan_hoa(s))
    print(chuan_hoa("Máy W2", "W2 = đắp liu hai"))
