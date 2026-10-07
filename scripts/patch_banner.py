# -*- coding: utf-8 -*-
"""
在 ksud 源码里找出品牌横幅（ASCII 图案 / 品牌名），并换成「开星内核」。

用法：
  python3 patch_banner.py scan     SOURCE_DIR   只扫描，不改动
  python3 patch_banner.py kaixing  SOURCE_DIR   替换成开星内核笑脸
  python3 patch_banner.py remove   SOURCE_DIR   直接删掉横幅

两种检测方式并用，哪个先命中算哪个：
  1) 搜品牌关键词（SUKISU / SukiSU / ULTRA / Ultra ...）
  2) 连续 >=3 行的 ASCII art 特征

参数用英文，避免不同 shell 环境下中文参数出问题。
"""
import re, sys, os

ART_CHARS = set('#*=_./\\|-()[]{}<>^+~`:;,\'"')

# 品牌关键词：SukiSU Ultra 大概率把自己的名字写在横幅里
BRAND_WORDS = ['sukisu', 'suki su', 'ultra', 'sukisuultra', 'suki-su']

W = 31  # 横幅内部宽度


def make_kaixing():
    """程序化生成，保证每一行严格等宽对齐"""
    def bar(content):
        body = content.center(W)
        assert len(body) == W, '内容超宽: %s' % content
        return "  |" + body + "|"
    rows = [
        "  ." + "-" * W + ".",
        bar("o               o"),
        bar(""),
        bar("\\_________/"),
        bar(""),
        bar("K A I X I N G   KERNEL"),
        bar(""),
        "  '" + "-" * W + "'",
    ]
    widths = set(len(r) for r in rows)
    assert len(widths) == 1, '宽度不一致: %s' % widths
    return rows


KAIXING = make_kaixing()


def is_art_line(s):
    t = s.strip()
    if len(t) < 8:
        return False
    chars = [c for c in t if not c.isspace()]
    if len(chars) < 6:
        return False
    art = sum(1 for c in chars if c in ART_CHARS)
    return art / len(chars) >= 0.6


def is_brand_line(s):
    """这一行是不是在打印品牌名（SUKISU / ULTRA 之类）

    必须去掉空格再匹配：ASCII 横幅常把字母拆开写，
    比如 "S U K I S U   U L T R A"，直接搜 "sukisu" 是搜不到的。
    """
    low = s.lower()
    nospace = low.replace(' ', '')
    return any(w in low or w in nospace for w in BRAND_WORDS)


def find_brand_block(lines):
    """找出连续的品牌打印行。
    很多横幅是「几行图案 + 一行品牌名」，图案部分没有文字，
    所以要用品牌名定位，再往上把相邻的 println! 一起吃掉。"""
    hits = [i for i in range(len(lines)) if is_brand_line(lines[i])]
    if not hits:
        return None
    # 取第一处品牌行
    c = hits[0]
    # 只向两侧扩「图案行或品牌行」。
    # 不能简单看 println! —— 那样会把 "- Preparing" 这类正常输出一起吃掉。
    def keep(i):
        if not (0 <= i < len(lines)):
            return False
        if 'println!' not in lines[i]:
            return False
        return is_art_line(lines[i]) or is_brand_line(lines[i])

    a = c
    while keep(a - 1):
        a -= 1
    b = c + 1
    while keep(b):
        b += 1
    # 至少要 2 行才当成横幅，避免误删单行无关输出
    if b - a < 2:
        return None
    return (a, b)


def find_kaixing_block(lines):
    """检测文件里是否已经是「开星内核」横幅。
    没有这个的话，替换完再执行 remove 会找不到（新横幅符号占比不够）。"""
    ka = [r.strip() for r in KAIXING]
    for i in range(len(lines)):
        if ka[0] and ka[0] in lines[i]:
            j, idx = i, 0
            while j < len(lines) and idx < len(ka):
                if ka[idx] in lines[j]:
                    idx += 1
                    j += 1
                else:
                    break
            if idx >= 3:
                return (i, j)
    return None


def find_blocks(lines):
    """找出连续 >=3 行的 ASCII art 块"""
    blocks = []
    kb = find_kaixing_block(lines)
    if kb:
        blocks.append(kb)
    bb = find_brand_block(lines)
    if bb and not any(not (bb[1] <= a2 or bb[0] >= b2) for a2, b2 in blocks):
        blocks.append(bb)
    i = 0
    while i < len(lines):
        if is_art_line(lines[i]):
            j = i
            while j < len(lines) and is_art_line(lines[j]):
                j += 1
            # 向下只扩「图案行或品牌行」。
            # 不能简单看 println! —— 会把 "- Preparing" 这类正常输出一起吃掉。
            k = j
            while k < len(lines) and k - j < 2 and 'println!' in lines[k] \
                    and (is_art_line(lines[k]) or is_brand_line(lines[k])):
                k += 1
            if j - i >= 3:
                # 别跟已找到的开星横幅区域重叠
                overlap = any(not (k <= a2 or i >= b2) for a2, b2 in blocks)
                if not overlap:
                    blocks.append((i, k))
            i = k
        else:
            i += 1
    return blocks


def process(path, mode):
    src = open(path, encoding='utf-8', errors='ignore').read()
    lines = src.split('\n')
    blocks = find_blocks(lines)
    if not blocks:
        return 0, []
    info = []
    new_lines = []
    prev = 0
    for (a, b) in sorted(blocks):
        new_lines.extend(lines[prev:a])
        info.append((path, a + 1, b, lines[a:b]))
        if mode == 'kaixing':
            m = re.match(r'^(\s*)', lines[a])
            indent = m.group(1) if m else ''
            # 用 raw string，内容里的反斜杠不需要转义
            for art in KAIXING:
                new_lines.append('%sprintln!(r#"%s"#);' % (indent, art))
        prev = b
    new_lines.extend(lines[prev:])
    if mode in ('kaixing', 'remove'):
        open(path, 'w', encoding='utf-8').write('\n'.join(new_lines))
    return len(blocks), info


if __name__ == '__main__':
    mode = sys.argv[1]
    root = sys.argv[2]
    total = 0
    for r, d, fs in os.walk(root):
        if 'target' in r or '.git' in r or 'build' in r.split(os.sep):
            continue
        for f in fs:
            if not f.endswith('.rs'):
