# meds_catalog.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

# -------------------------
# Parsers
# -------------------------

_minus_chars = "−–—-"  # 全角/半角マイナスゆれ
_range_sep = r"(?:～|〜|to|TO|-)"

def _norm(s: Any) -> str:
    if s is None:
        return ""
    s = str(s)
    s = re.sub(f"[{_minus_chars}]", "-", s)  # マイナスを統一
    s = s.replace("\u3000", " ").strip()     # 全角スペース→半角
    return s

def _parse_yen_per_year(x: Any) -> Optional[int]:
    """'4,088 円/年' などから整数円を返す"""
    if x is None:
        return None
    s = _norm(x)
    m = re.search(r"([0-9][0-9,]*)\s*円", s)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))

def _parse_ci_triplet_from_text(s: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    例:
      'LDL -52% (95% CI -55〜-50%)'
      'HbA1c -0.8% (95% CI -0.9〜-0.7)'
      '-6.3 (95% CI -8.9～-3.7)'
    -> (mean, low, high)
    """
    s = _norm(s)
    mean = low = high = None

    m_mean = re.search(r"(-?\d+(?:\.\d+)?)", s)
    if m_mean:
        mean = float(m_mean.group(1))

    m_ci = re.search(
        r"95%\s*CI\s*(-?\d+(?:\.\d+)?)\s*" + _range_sep + r"\s*(-?\d+(?:\.\d+)?)",
        s, flags=re.I
    )
    if m_ci:
        low = float(m_ci.group(1))
        high = float(m_ci.group(2))

    return mean, low, high

def _parse_bp_effect_sbp_mmHg(effect_text: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    降圧効果欄の例:
      '−11.7/−6.8 mmHg'  -> SBP=-11.7 とみなす（DBPは無視）
      '−6.3 (95% CI −8.9～−3.7)' -> SBP=-6.3, CI=-8.9..-3.7
    """
    s = _norm(effect_text)
    if not s:
        return None, None, None

    if "/" in s:
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*/", s)
        if m:
            mean = float(m.group(1))
            _, low, high = _parse_ci_triplet_from_text(s)
            return mean, low, high

    mean, low, high = _parse_ci_triplet_from_text(s)
    return mean, low, high

def _parse_ldl_reduction_percent(effect_text: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    'LDL -52% (95% CI -55〜-50%)' -> reduction=0.52
    """
    s = _norm(effect_text)
    if not s:
        return None, None, None
    
    mean, low, high = _parse_ci_triplet_from_text(s)
    # mean等は「-52」のように負で入ってくる想定 -> reduction(正)へ変換
    def conv(x):
        if x is None:
            return None
        return abs(x) / 100.0
    
    return conv(mean), conv(low), conv(high)

def _parse_hba1c_delta_pct(effect_text: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    'HbA1c -0.8% (95% CI -0.9〜-0.7)' -> delta=-0.8（%ポイント）
    """
    s = _norm(effect_text)
    if not s:
        return None, None, None

    # 「HbA1c」の数字1を平均変化量として誤検出しないよう、先頭ラベルを除く。
    # 例: "HbA1c -1.0% (95% CI -1.27〜-0.90%)"
    s = re.sub(r"^HbA1c\s*", "", s, flags=re.I)
    mean, low, high = _parse_ci_triplet_from_text(s)
    return mean, low, high

# -------------------------
# Catalog Loader
# -------------------------

@dataclass
class Med:
    key: str                 # 表示名（薬剤名・用量）
    category: str            # 分類
    domain: str              # 'sbp' | 'ldl' | 'hba1c'
    mean: float              # effect mean（domainごと単位が違う）
    low: Optional[float]     # CI low（同上）
    high: Optional[float]    # CI high（同上）
    annual_cost_yen: Optional[int]
    side_effects: str
    ref: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "category": self.category,
            "domain": self.domain,
            "effect": {"mean": self.mean, "low": self.low, "high": self.high},
            "annual_cost_yen": self.annual_cost_yen,
            "side_effects": self.side_effects,
            "ref": self.ref,
        }

def load_meds_catalog(
    xlsx_bp_path: str,
    xlsx_ldl_hba1c_path: str,
    bp_sheet: str = "Sheet1",
    ldl_sheet: str = "LDL用量別（薬価付き）",
    hba1c_sheet: str = "HbA1c用量別（薬価付き）",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns:
      {
        "sbp":   [Med...dict],
        "ldl":   [...],
        "hba1c": [...],
      }
    """
    meds: List[Med] = []
    
    # ---- BP (SBP) ----
    df_bp = pd.read_excel(xlsx_bp_path, sheet_name=bp_sheet)
    for _, row in df_bp.iterrows():
        key = _norm(row.get("薬剤名・用量", ""))
        if not key:
            continue
        category = _norm(row.get("分類", ""))
        effect = row.get("降圧効果（平均変化・95%CI）", "")
        mean, low, high = _parse_bp_effect_sbp_mmHg(effect)
        if mean is None:
            continue
        annual = _parse_yen_per_year(row.get("年間薬価（円/年）"))
        se = _norm(row.get("主な副作用（頻度）", ""))
        ref = _norm(row.get("参考文献（Circulation形式・英語タイトル）", ""))
        meds.append(Med(
            key=key, category=category, domain="sbp",
            mean=float(mean), low=low, high=high,
            annual_cost_yen=annual, side_effects=se, ref=ref
        ))
    
    # ---- LDL ----
    df_ldl = pd.read_excel(xlsx_ldl_hba1c_path, sheet_name=ldl_sheet)
    for _, row in df_ldl.iterrows():
        key = _norm(row.get("薬剤名・用量", ""))
        if not key:
            continue
        category = _norm(row.get("分類", ""))
        effect = row.get("効果（平均変化・95%CI）", "")
        mean, low, high = _parse_ldl_reduction_percent(effect)
        if mean is None:
            continue
        annual = _parse_yen_per_year(row.get("年間薬価（円/年）"))
        se = _norm(row.get("主な副作用（頻度）", ""))
        ref = _norm(row.get("参考文献（Circulation形式・英語タイトル）", ""))
        meds.append(Med(
            key=key, category=category, domain="ldl",
            mean=float(mean), low=low, high=high,
            annual_cost_yen=annual, side_effects=se, ref=ref
        ))
    
    # ---- HbA1c ----
    df_h = pd.read_excel(xlsx_ldl_hba1c_path, sheet_name=hba1c_sheet)
    for _, row in df_h.iterrows():
        key = _norm(row.get("薬剤名・用量", ""))
        if not key:
            continue
        category = _norm(row.get("分類", ""))
        effect = row.get("効果（平均変化・95%CI）", "")
        mean, low, high = _parse_hba1c_delta_pct(effect)
        if mean is None:
            continue
        annual = _parse_yen_per_year(row.get("年間薬価（円/年）"))
        se = _norm(row.get("主な副作用（頻度）", ""))
        ref = _norm(row.get("参考文献（Circulation形式・英語タイトル）", ""))
        meds.append(Med(
            key=key, category=category, domain="hba1c",
            mean=float(mean), low=low, high=high,
            annual_cost_yen=annual, side_effects=se, ref=ref
        ))
    
    out: Dict[str, List[Dict[str, Any]]] = {"sbp": [], "ldl": [], "hba1c": []}
    for m in meds:
        out[m.domain].append(m.to_dict())
    
    # 画面で見やすいように、カテゴリ→薬剤名でソート
    def sort_key(d):
        return (d.get("category", ""), d.get("key", ""))
    
    for k in out:
        out[k] = sorted(out[k], key=sort_key)
    
    return out

def apply_meds_to_targets(
    sbp_now: float,
    ldl_now_mg: float,
    a1c_now: float,
    selected_sbp: List[Dict[str, Any]],
    selected_ldl: List[Dict[str, Any]],
    selected_a1c: List[Dict[str, Any]],
    clip_sbp: Tuple[float, float] = (90.0, 200.0),
    clip_ldl: Tuple[float, float] = (30.0, 250.0),
    clip_a1c: Tuple[float, float] = (5.0, 12.0),
) -> Dict[str, Any]:
    """
    合成ルール:
      SBP: 低下量(mmHg)を足し算（meanは負値） -> sbp_target = now + sum(delta)
      LDL: 低下率(0-1)を逐次掛け算           -> ldl_target = now * Π(1 - reduction)
      A1c: 変化量(%ポイント)を足し算（meanは負値） -> a1c_target = now + sum(delta)
    """
    # SBP
    sbp_delta = sum(float(m["effect"]["mean"]) for m in selected_sbp) if selected_sbp else 0.0
    sbp_target = sbp_now + sbp_delta
    
    # LDL
    mult = 1.0
    for m in selected_ldl:
        r = float(m["effect"]["mean"])  # reduction positive (e.g. 0.52)
        mult *= max(0.0, (1.0 - r))
    ldl_target = ldl_now_mg * mult
    
    # HbA1c
    a1c_delta = sum(float(m["effect"]["mean"]) for m in selected_a1c) if selected_a1c else 0.0
    a1c_target = a1c_now + a1c_delta
    
    # clip
    sbp_target = float(min(max(sbp_target, clip_sbp[0]), clip_sbp[1]))
    ldl_target = float(min(max(ldl_target, clip_ldl[0]), clip_ldl[1]))
    a1c_target = float(min(max(a1c_target, clip_a1c[0]), clip_a1c[1]))
    
    # cost
    def cost_sum(arr):
        total = 0
        for m in arr:
            c = m.get("annual_cost_yen")
            if c is not None:
                total += int(c)
        return total
    
    annual_cost = cost_sum(selected_sbp) + cost_sum(selected_ldl) + cost_sum(selected_a1c)
    
    # side effects: 薬剤ごとに並べる（MVP）
    def side_effect_lines(arr):
        lines = []
        for m in arr:
            se = (m.get("side_effects") or "").strip()
            if se:
                lines.append(f"- {m['key']}: {se}")
        return lines
    
    side_effects_md = "\n".join(side_effect_lines(selected_sbp) + side_effect_lines(selected_ldl) + side_effect_lines(selected_a1c))
    
    return {
        "sbp_target": sbp_target,
        "ldl_target": ldl_target,
        "a1c_target": a1c_target,
        "annual_cost_yen": annual_cost,
        "side_effects_md": side_effects_md,
        "deltas": {"sbp_mmHg": sbp_delta, "ldl_mult": mult, "a1c_pctpt": a1c_delta},
    }
