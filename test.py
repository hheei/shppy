import re

text = """
&nm1
  a = 1,
  path = '/usr/local/bin/data/',  ! 這裡的斜線不會觸發結束
  message = "Don't stop here /",  ! 雙引號內的斜線也安全
  CARDS = 2
/

CARDS
1.0 2.0 3.0

&nm2
  b = 3
/

POINTS ABC
7 8 9
"""

# 定義已知的 Cards 關鍵字
known_cards = ["CARDS", "POINTS", "ELEMENTS"]
cards_pattern = "|".join(known_cards)

# [升級] Namelist 規則：略過字串內的斜線
# 解析：匹配單引號字串 | 匹配雙引號字串 | 匹配非斜線非引號的字元
namelist_regex = r"(?:^&(\w+)((?:'[^']*'|\"[^\"]*\"|[^/\"']+)*)/)"

# Cards 規則 (與上次相同，包含可選屬性)
cards_regex = rf"(?:^({cards_pattern})\b(?:[ \t]+([^\n\r]+?))?[ \t]*(?:\r?\n|\Z)(.*?)(?=^&|^(?:{cards_pattern})\b|\Z))"

# 組合正則表達式
regex = namelist_regex + "|" + cards_regex
pattern = re.compile(regex, re.MULTILINE | re.DOTALL)

result_dict = {}

for match in pattern.finditer(text):
    # Group 1: Namelist
    if match.group(1): 
        title = match.group(1).strip()
        content = match.group(2).strip()
        result_dict[title] = {
            "type": "namelist",
            "attribute": None,
            "content": content
        }
        
    # Group 3: Cards (由於 Namelist 佔用了 Group 1, 2，這裡變成 Group 3 開始)
    elif match.group(3): 
        title = match.group(3).strip()
        attribute = match.group(4).strip() if match.group(4) else None
        content = match.group(5).strip()
        result_dict[title] = {
            "type": "card",
            "attribute": attribute,
            "content": content
        }

print("解析結果 Dict：\n")
for k, v in result_dict.items():
    print(f"[{k}]")
    print(f"  Type:      {v['type']}")
    print(f"  Attribute: {v['attribute']}")
    print(f"  Content:\n{v['content']}")
    print("-" * 20)