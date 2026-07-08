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

    s = re.sub(r"^HbA1c\s*", "", s, flags=re.I)  # 先頭ラベル「HbA1c」を除去（"A1c"の"1"誤検出を防ぐ）
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



# ------------------------------------------------------------------
# MedicationAdjustment
# ------------------------------------------------------------------
# 患者がすでに薬を服用している状態を基準にして、薬を追加・減少・入れ替え
# した場合の "調整差分" を計算するためのクラス。
#
# 従来の `apply_meds_to_targets()` は「薬なし / 未治療状態」からの絶対目標値を
# 計算するのに対し、本クラスは「現在の服薬状態」からの相対的な変化量を扱う。
#
# 計算モデル:
#   baseline = 現在の測定値（= 現在の服薬状態を反映済み）
#   target   = 現在の測定値 + 薬剤変更差分
#
# SBP / HbA1c: 効果量を単純に足し引きする
# LDL        : 残存比率（1 - 低下率）の掛け算の比率を取る
# 費用        : 選択された薬の年間薬価を単純加算する
# 副作用      : baselineにあって adjusted にない薬 = 中止薬
#               adjustedにあって baseline にない薬 = 追加薬
# ------------------------------------------------------------------

class MedicationAdjustment:
    """
    現在の服薬状態から変更後の服薬状態への差分を計算する。

    Parameters
    ----------
    sbp_now : float
        現在の収縮期血圧測定値（mmHg）。現在の薬が効いた状態の値。
    ldl_now_mg : float
        現在のLDLコレステロール測定値（mg/dL）。
    a1c_now : float
        現在のHbA1c測定値（%）。
    current_meds : dict
        現在服用中の薬リスト。
        例: {"sbp": [med1, med2], "ldl": [med3], "hba1c": []}
    adjusted_meds : dict
        変更後に残す薬リスト。同じ形式。
    """

    def __init__(
        self,
        sbp_now: float,
        ldl_now_mg: float,
        a1c_now: float,
        current_meds: Dict[str, List[Dict[str, Any]]],
        adjusted_meds: Dict[str, List[Dict[str, Any]]],
    ):
        self.sbp_now = sbp_now
        self.ldl_now = ldl_now_mg
        self.a1c_now = a1c_now
        self.current = current_meds
        self.adjusted = adjusted_meds

    # ------------------------- 内部計算 -------------------------

    def _effect_sum(self, meds: List[Dict[str, Any]]) -> float:
        """
        SBP または HbA1c の効果量を合計する。
        薬カタログ内の effect["mean"] は負値（低下効果）で格納されている。
        """
        return sum(float(m["effect"]["mean"]) for m in meds) if meds else 0.0

    def _ldl_mult(self, meds: List[Dict[str, Any]]) -> float:
        """
        LDL の「残存比率」を計算する。
        例: 低下率 30% の薬なら (1 - 0.30) = 0.70 を掛ける。
        複数薬があればそれらを順次掛け算する。
        """
        mult = 1.0
        for m in meds:
            # effect["mean"] は 0〜1 の正の値として格納されている（例: 0.30）
            r = float(m["effect"]["mean"])
            mult *= max(0.0, 1.0 - r)
        return mult

    def _sbp_delta(self) -> float:
        """
        SBP の調整差分を計算。
        adjusted_meds の合計効果から current_meds の合計効果を引く。
        戻り値が負なら血圧が下がる（改善）、正なら上がる（悪化）。
        """
        return (
            self._effect_sum(self.adjusted.get("sbp", []))
            - self._effect_sum(self.current.get("sbp", []))
        )

    def _ldl_ratio(self) -> float:
        """
        LDL の調整比率を計算。
        adjusted_meds の残存比率を current_meds の残存比率で割る。
        比率 < 1.0 なら LDL が下がる（改善）、> 1.0 なら上がる（悪化）。
        """
        cur_mult = self._ldl_mult(self.current.get("ldl", []))
        adj_mult = self._ldl_mult(self.adjusted.get("ldl", []))
        # current_meds が空（未服薬）の場合を除くためのガード
        return adj_mult / cur_mult if cur_mult > 0 else 1.0

    def _a1c_delta(self) -> float:
        """
        HbA1c の調整差分を計算。
        adjusted_meds の合計効果から current_meds の合計効果を引く。
        戻り値が負なら HbA1c が下がる（改善）、正なら上がる（悪化）。
        """
        return (
            self._effect_sum(self.adjusted.get("hba1c", []))
            - self._effect_sum(self.current.get("hba1c", []))
        )

    # ------------------------- 公開メソッド -------------------------

    def baseline_targets(self) -> Dict[str, float]:
        """
        baseline 側の目標値を返す。
        現在の測定値そのままを使う（現在の薬効はすでに反映されていると解釈）。
        """
        return {
            "sbp_target": self.sbp_now,
            "ldl_target": self.ldl_now,
            "a1c_target": self.a1c_now,
        }

    def adjusted_targets(self) -> Dict[str, float]:
        """
        変更後（adjusted）側の目標値を返す。
        現在の測定値に薬剤変更差分を加える。
        """
        return {
            "sbp_target": self.sbp_now + self._sbp_delta(),
            "ldl_target": self.ldl_now * self._ldl_ratio(),
            "a1c_target": self.a1c_now + self._a1c_delta(),
        }

    def costs(self) -> Dict[str, int]:
        """
        baseline（現在の服薬）と adjusted（変更後）の年間薬剤費を計算する。
        戻り値には差分も含める。
        """
        def _total(meds_list: List[Dict[str, Any]]) -> int:
            # annual_cost_yen が None の場合は 0 円として扱う
            return sum(int(m.get("annual_cost_yen", 0) or 0) for m in meds_list)

        baseline = (
            _total(self.current.get("sbp", []))
            + _total(self.current.get("ldl", []))
            + _total(self.current.get("hba1c", []))
        )
        adjusted = (
            _total(self.adjusted.get("sbp", []))
            + _total(self.adjusted.get("ldl", []))
            + _total(self.adjusted.get("hba1c", []))
        )
        return {
            "baseline": baseline,
            "adjusted": adjusted,
            "delta": adjusted - baseline,
        }

    def side_effect_changes(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        薬剤変更によって中止される薬と新規追加される薬を特定する。

        Returns
        -------
        dict
            {
                "stopped":  [baselineにあって adjusted にない薬のリスト],
                "added":    [adjustedにあって baseline にない薬のリスト],
            }
        """
        # key（薬剤名＋用量）をキーにして辞書化
        current_keys = {m["key"]: m for domain in self.current.values() for m in domain}
        adjusted_keys = {m["key"]: m for domain in self.adjusted.values() for m in domain}

        # baseline にあって adjusted にないもの = 中止薬
        stopped = [current_keys[k] for k in current_keys if k not in adjusted_keys]
        # adjusted にあって baseline にないもの = 追加薬
        added = [adjusted_keys[k] for k in adjusted_keys if k not in current_keys]

        return {"stopped": stopped, "added": added}
