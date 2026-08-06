import csv, math, yaml, numpy as np, os
from typing import Dict, List, Any
from meds_catalog import MedicationAdjustment

# 性別の正規化ヘルパー
_SEX_ALIASES = {
    "男性": "male", "女性": "female",
    "男": "male", "女": "female",
    "M": "male", "F": "female",
    "m": "male", "f": "female",
    "man": "male", "woman": "female",
    "♂": "male", "♀": "female",
}

def _norm_sex(sex: str) -> str:
    """性別文字列を正規化してconfig.yamlのキーに合わせる"""
    if sex is None:
        return "male"   # デフォルト
    s = str(sex).strip()
    return _SEX_ALIASES.get(s, s)

class OutcomesEngine:
    # 年齢帯ごとに RR の“効き”を重み付け（lnRRに乗る係数 alpha）
    # alpha=1.0 → フル効果 / alpha=0.0 → 効果ゼロ（RR→1.0）
    def _alpha_by_age(self, kind: str, age: float) -> float:
        if kind == "sbp":
            # SBPは 75歳まではフル、75→85でゼロへ線形、85+はゼロ
            if age < 75:
                return 1.0
            if age >= 85:
                return 0.0
            return 1.0 - (age - 75.0) / 10.0
        if kind == "ldl":
            # LDL: <85はフル効果、85→95で係数を0.7へ線形減衰、95+は0.7固定
            if age < 85:
                return 1.0
            if age >= 95:
                return 0.7
            return 1.0 - (1.0 - 0.7) * (age - 85.0) / 10.0
        if kind == "hba1c":
            # HbA1cは宏血管に関して控えめ：75まではフル、75→85でゼロ、85+はゼロ
            if age < 75:
                return 1.0
            if age >= 85:
                return 0.0
            return 1.0 - (age - 75.0) / 10.0
        return 1.0
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.cfg = yaml.safe_load(f)
        self._load_baselines()

    def _load_baselines(self):
        self.mi_points = self._read_points_csv('data/baseline_incidence_mi.csv')
        self.stroke_points = self._read_points_csv('data/baseline_incidence_stroke.csv')
        self.mort_points = self._read_points_csv('data/baseline_incidence_mortality.csv')

    @staticmethod
    def _read_points_csv(path):
        try:
            # フォールバック: data/～ が無ければ同名のベース名をルート直下で探す
            load_path = path
            if not os.path.exists(load_path):
                alt = os.path.basename(path)
                if os.path.exists(alt):
                    load_path = alt
            # RailwayでPandas 3の文字列比較がネイティブクラッシュしたため、
            # 小さな基準発生率CSVは標準ライブラリで読み、性別ごとのNumPy配列にする。
            points = {}
            with open(load_path, newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    sex = str(row.get("sex", "")).strip().lower()
                    if not sex or not row.get("age"):
                        continue
                    value_key = "qx" if row.get("qx") not in (None, "") else "incidence_per_100k"
                    if row.get(value_key) in (None, ""):
                        continue
                    bucket = points.setdefault(sex, {"age": [], "value": [], "is_qx": value_key == "qx"})
                    bucket["age"].append(float(row["age"]))
                    bucket["value"].append(float(row[value_key]))
            for bucket in points.values():
                order = np.argsort(np.asarray(bucket["age"], dtype=float))
                bucket["age"] = np.asarray(bucket["age"], dtype=float)[order]
                values = np.asarray(bucket["value"], dtype=float)[order]
                bucket["value"] = values if bucket["is_qx"] else values / 100000.0
            return points or None
        except Exception:
            return None

    def _interp_baseline(self, outcome: str, sex: str, age: float):
        # 性別を正規化
        sex = _norm_sex(sex)
        
        pts = {'mi': self.mi_points, 'stroke': self.stroke_points, 'mortality': self.mort_points}[outcome]
        # CSV がある場合は優先して使用
        if pts:
            sub = pts.get(sex.lower())
            if sub and len(sub["age"]) >= 2:
                xs, ys = sub["age"], sub["value"]
                if age <= xs[0]: return float(ys[0])
                if age >= xs[-1]: return float(ys[-1])
                return float(np.interp(age, xs, ys))

        # フォールバック: キーが存在しない場合の処理
        data_by_sex = self.cfg['baseline_incidence'][outcome]
        if sex not in data_by_sex:
            # 存在するキーの先頭を使う（ログを出しておく）
            print(f"[warn] unknown sex key '{sex}', fallback to available keys {list(data_by_sex.keys())}")
            sex = next(iter(data_by_sex.keys()))
            
        a = self.cfg['baseline_incidence'][outcome][sex]['a']
        b = self.cfg['baseline_incidence'][outcome][sex]['b']
        # CSV が無い場合は指数近似。mortality でも "qx 近似" をそのまま確率として返す。
        return a * math.exp(b * (age - 40.0))

    def _attenuate_rr(self, rr: float, effect_key: str, age: float) -> float:
        """Apply age-based attenuation on a risk ratio rr using config age_effect.
        Attenuation is applied on log scale: ln(rr)_eff = ln(rr) * (1 - strength * w),
        where w increases linearly from 0 at start_age to 1 at end_age. Outside the
        range, w is 0 (below) or 1 (above). strength in [0,1].
        """
        if rr <= 0.0 or rr == 1.0:
            return 1.0 if rr <= 0.0 else rr
        cfg = (self.cfg.get('age_effect') or {}).get(effect_key)
        if not cfg:
            return rr
        start_age = float(cfg.get('start_age', 9999))
        end_age = float(cfg.get('end_age', start_age))
        strength = float(cfg.get('strength', 0.0))
        if strength <= 0.0 or age < start_age:
            return rr
        if age >= end_age:
            w = 1.0
        else:
            denom = max(1e-9, (end_age - start_age))
            w = max(0.0, min(1.0, (age - start_age) / denom))
        if w <= 0.0:
            return rr
        ln_rr = math.log(rr)
        ln_rr_eff = ln_rr * max(0.0, (1.0 - strength * w))
        return math.exp(ln_rr_eff)

    # --- BMI→RR（U字）年齢補正つき／1BMIごとの連続効果 ---
    # ・年齢に応じて「最適BMI（谷）」を若年=23.5 → 高齢=26.5に線形シフト
    # ・高BMI側/低BMI側の傾き（5BMIあたりRR）も年齢で補正
    # ・1BMI刻みの連続モデル：beta = ln(RR5)/5 → RR = exp(beta * 差)
    def rr_bmi(self, age: float, bmi: float) -> float:
        # 谷（最適BMI）の年齢シフト
        if age <= 40:
            bmi_nadir = 23.5
        elif age >= 80:
            bmi_nadir = 26.5
        else:
            bmi_nadir = 23.5 + (26.5 - 23.5) * (age - 40.0) / 40.0

        # 高BMI側（若年ほど影響大、超高齢で中立化）
        if age <= 40:
            rr5_high = 1.25
        elif age <= 75:
            rr5_high = 1.10 + (1.25 - 1.10) * (75 - age) / 35.0
        elif age <= 85:
            rr5_high = 1.00 + (1.10 - 1.00) * (85 - age) / 10.0
        else:
            rr5_high = 1.00

        # 低BMI側（高齢ほど不利）
        if age <= 40:
            rr5_low = 1.05
        elif age <= 75:
            rr5_low = 1.10 + (1.05 - 1.10) * (75 - age) / 35.0
        elif age <= 85:
            rr5_low = 1.20 + (1.10 - 1.20) * (85 - age) / 10.0
        else:
            rr5_low = 1.20

        beta_high = math.log(rr5_high) / 5.0
        beta_low = math.log(rr5_low) / 5.0

        if bmi >= bmi_nadir:
            delta = max(0.0, bmi - bmi_nadir)
            rr = math.exp(beta_high * delta)
        else:
            delta = max(0.0, bmi_nadir - bmi)
            rr = math.exp(beta_low * delta)

        # 極端値の暴れ防止（任意）
        return float(min(max(rr, 0.5), 2.0))

    # --- CKD（eGFR/ACR）リスク：年齢減衰＋アウトカム別調整 ---
    # rr_egfr: >=60→1.0, 45–59→1.30, <45→1.80
    # rr_acr:  A1→1.0, A2→1.35, A3→1.90
    # 結合は初期は max(rr_egfr, rr_acr) とし、年齢で lnRR に係数αを掛ける
    def rr_ckd(self, age: float, egfr: float, acr: str, outcome: str) -> float:
        if egfr is None and (acr is None or acr == ""):
            return 1.0

        # eGFR カテゴリ
        rr_egfr = 1.0
        if egfr is not None:
            if egfr < 45:
                rr_egfr = 1.80
            elif egfr < 60:
                rr_egfr = 1.30
            else:
                rr_egfr = 1.0

        # アルブミン尿/尿蛋白カテゴリ
        acr_cat = (acr or "A1").upper()
        rr_acr = {"A1": 1.0, "A2": 1.35, "A3": 1.90}.get(acr_cat, 1.0)

        # 初期は過大評価回避のため max を採用
        rr_base = max(rr_egfr, rr_acr)

        # 年齢による相対効果減衰 α(age)
        has_alb = rr_acr > 1.0
        low_gfr_only = (rr_egfr > 1.0 and rr_acr == 1.0)
        both = (rr_egfr > 1.0 and rr_acr > 1.0)
        if age <= 75:
            a = 1.0
        elif age <= 85:
            a = 1.0 - ((age - 75.0) / 10.0) * (0.15 if has_alb else 0.20)
        else:
            a = 0.80 if has_alb else 0.70
        if both:
            if age <= 75:
                a = 1.0
            elif age <= 85:
                a = 1.0 - ((age - 75.0) / 10.0) * 0.10
            else:
                a = 0.85

        rr_age = (rr_base ** a)

        # アウトカム別調整
        outcome_adj = 1.0
        if outcome == 'mi':
            outcome_adj = 0.8
        elif outcome == 'mortality':
            outcome_adj = 1.1
        else:
            outcome_adj = 1.0  # stroke は標準

        return rr_age * outcome_adj

    def rr_sbp(self, outcome: str, delta_sbp_mmHg: float) -> float:
        key = {'mi':'rr_per_10mmhg_mi', 'stroke':'rr_per_10mmhg_stroke', 'mortality':'rr_per_10mmhg_mortality'}[outcome]
        rr10 = self.cfg['risk_models']['sbp'][key]
        return rr10 ** (delta_sbp_mmHg / 10.0)
    
    def rr_sbp_with_ci(self, outcome: str, delta_sbp_mmHg: float, confidence_level: float = 0.95) -> dict:
        """血圧の相対リスクと95%信頼区間を計算"""
        key = {'mi':'rr_per_10mmhg_mi', 'stroke':'rr_per_10mmhg_stroke', 'mortality':'rr_per_10mmhg_mortality'}[outcome]
        rr10 = self.cfg['risk_models']['sbp'][key]
        
        # 標準誤差（主要メタ解析研究に基づく）
        # 血圧10mmHg上昇あたりのlog(RR)の標準誤差
        se_log_rr_per_10mmhg = {
            'mi': 0.02,      # 心筋梗塞：Lewington et al. Lancet 2002
            'stroke': 0.025, # 脳卒中：Lewington et al. Lancet 2002  
            'mortality': 0.02 # 死亡：Lewington et al. Lancet 2002
        }[outcome]
        
        # 95%CIの計算
        z_score = 1.96 if confidence_level == 0.95 else 2.576  # 99%CI
        log_rr = math.log(rr10) * (delta_sbp_mmHg / 10.0)
        se_log_rr = se_log_rr_per_10mmhg * abs(delta_sbp_mmHg) / 10.0
        
        ci_lower = math.exp(log_rr - z_score * se_log_rr)
        ci_upper = math.exp(log_rr + z_score * se_log_rr)
        point_estimate = rr10 ** (delta_sbp_mmHg / 10.0)
        
        return {
            'point': point_estimate,
            'lower': ci_lower,
            'upper': ci_upper
        }

    def rr_ldl(self, outcome: str, delta_ldl_mmol: float) -> float:
        key = {'mi':'rr_per_1mmol_mi', 'stroke':'rr_per_1mmol_stroke', 'mortality':'rr_per_1mmol_mortality'}[outcome]
        r = self.cfg['risk_models']['ldl'][key]
        return r ** (delta_ldl_mmol)
    
    def rr_ldl_with_ci(self, outcome: str, delta_ldl_mmol: float, confidence_level: float = 0.95) -> dict:
        """LDLコレステロールの相対リスクと95%信頼区間を計算"""
        key = {'mi':'rr_per_1mmol_mi', 'stroke':'rr_per_1mmol_stroke', 'mortality':'rr_per_1mmol_mortality'}[outcome]
        r = self.cfg['risk_models']['ldl'][key]
        
        # 標準誤差（主要メタ解析研究に基づく）
        # LDL 1mmol/L上昇あたりのlog(RR)の標準誤差
        se_log_rr_per_1mmol = {
            'mi': 0.03,      # 心筋梗塞：Cholesterol Treatment Trialists' Collaboration
            'stroke': 0.04,  # 脳卒中：Cholesterol Treatment Trialists' Collaboration
            'mortality': 0.035 # 死亡：Cholesterol Treatment Trialists' Collaboration
        }[outcome]
        
        # 95%CIの計算
        z_score = 1.96 if confidence_level == 0.95 else 2.576
        log_rr = math.log(r) * delta_ldl_mmol
        se_log_rr = se_log_rr_per_1mmol * abs(delta_ldl_mmol)
        
        ci_lower = math.exp(log_rr - z_score * se_log_rr)
        ci_upper = math.exp(log_rr + z_score * se_log_rr)
        point_estimate = r ** delta_ldl_mmol
        
        return {
            'point': point_estimate,
            'lower': ci_lower,
            'upper': ci_upper
        }

    def rr_hba1c(self, outcome: str, delta_hba1c: float, target_hba1c: float) -> float:
        key = {'mi':'rr_per_1pct_mi', 'stroke':'rr_per_1pct_stroke', 'mortality':'rr_per_1pct_mortality'}[outcome]
        base = self.cfg['risk_models']['hba1c'][key]
        # HbA1cは「1%増加あたりRR>1」なので、改善（now>target）でRR<1になるよう符号を反転
        rr = base ** (-(delta_hba1c))
        thr = self.cfg['risk_models']['hba1c'].get('u_shape_low_threshold', None)
        mult = self.cfg['risk_models']['hba1c'].get('u_shape_multiplier', 1.0)
        if thr is not None and target_hba1c < float(thr):
            rr *= float(mult)
        return rr
    
    def rr_hba1c_with_ci(self, outcome: str, delta_hba1c: float, target_hba1c: float, confidence_level: float = 0.95) -> dict:
        """HbA1cの相対リスクと95%信頼区間を計算"""
        key = {'mi':'rr_per_1pct_mi', 'stroke':'rr_per_1pct_stroke', 'mortality':'rr_per_1pct_mortality'}[outcome]
        base = self.cfg['risk_models']['hba1c'][key]
        
        # 標準誤差（主要メタ解析研究に基づく）
        # HbA1c 1%上昇あたりのlog(RR)の標準誤差
        se_log_rr_per_1pct = {
            'mi': 0.04,      # 心筋梗塞：Selvin et al. Diabetes Care 2010
            'stroke': 0.05,  # 脳卒中：Selvin et al. Diabetes Care 2010
            'mortality': 0.045 # 死亡：Selvin et al. Diabetes Care 2010
        }[outcome]
        
        # 95%CIの計算
        z_score = 1.96 if confidence_level == 0.95 else 2.576
        # 増加あたりRR>1のため、改善方向でRR<1となるよう符号を反転
        log_rr = math.log(base) * (-(delta_hba1c))
        se_log_rr = se_log_rr_per_1pct * abs(delta_hba1c)
        
        ci_lower = math.exp(log_rr - z_score * se_log_rr)
        ci_upper = math.exp(log_rr + z_score * se_log_rr)
        point_estimate = base ** (-(delta_hba1c))
        
        # U-shape効果の適用
        thr = self.cfg['risk_models']['hba1c'].get('u_shape_low_threshold', None)
        mult = self.cfg['risk_models']['hba1c'].get('u_shape_multiplier', 1.0)
        if thr is not None and target_hba1c < float(thr):
            point_estimate *= float(mult)
            ci_lower *= float(mult)
            ci_upper *= float(mult)
        
        return {
            'point': point_estimate,
            'lower': ci_lower,
            'upper': ci_upper
        }

    def _beta_smoke(self, outcome: str) -> float:
        return self.cfg['risk_models']['smoking'][
            {'mi':'beta_packyear_mi','stroke':'beta_packyear_stroke','mortality':'beta_packyear_mortality'}[outcome]
        ]

    def hr_current_smoker(self, outcome: str, pack_years: float) -> float:
        beta = self._beta_smoke(outcome)
        pmax = float(self.cfg['risk_models']['smoking']['packyear_max'])
        p = max(0.0, min(pmax, float(pack_years)))
        return math.exp(beta * p)

    def hr_after_quit(self, outcome: str, pack_years: float, years_since_quit: float) -> float:
        if years_since_quit <= 0.0:
            return self.hr_current_smoker(outcome, pack_years)
        hr_start = self.hr_current_smoker(outcome, pack_years)
        hr_min = self.cfg['risk_models']['smoking'][
            {'mi':'residual_hr_after_long_quit_mi','stroke':'residual_hr_after_long_quit_stroke','mortality':'residual_hr_after_long_quit_mortality'}[outcome]
        ]
        t_star = float(self.cfg['risk_models']['smoking']['years_to_reach_residual'])
        k = -math.log((hr_min - 1.0) / (hr_start - 1.0)) / t_star
        hr_t = 1.0 + (hr_start - 1.0) * math.exp(-k * years_since_quit)
        return max(hr_t, hr_min)

    def cumulative_incidence(self, outcome: str, sex: str, start_age: int, years: int,
                             sbp_now: float, sbp_target: float,
                             ldl_now_mg: float, ldl_target_mg: float,
                             hba1c_now: float, hba1c_target: float,
                             smoking_status: str, cigs_per_day: int,
                             years_smoked: float, years_since_quit: float,
                             assume_quit_today_in_target: bool = False) -> dict:
        # 現在の値と目標値の差を計算（正の値はリスク増加、負の値はリスク減少）
        delta_sbp = sbp_now - sbp_target
        delta_ldl_mmol = (ldl_now_mg - ldl_target_mg) / 38.67
        delta_hba1c = hba1c_now - hba1c_target

        pack_years = (cigs_per_day / 20.0) * max(0.0, years_smoked)

        if smoking_status == 'never':
            hr_smoke_base_fn = lambda age_offset: 1.0
            hr_smoke_tgt_fn  = lambda age_offset: 1.0
        elif smoking_status == 'former':
            hr_smoke_base_fn = lambda age_offset: self.hr_after_quit(outcome, pack_years, years_since_quit + age_offset)
            hr_smoke_tgt_fn  = hr_smoke_base_fn
        else:
            hr_smoke_base_fn = lambda age_offset: self.hr_current_smoker(outcome, pack_years)
            if assume_quit_today_in_target:
                hr_smoke_tgt_fn = lambda age_offset: self.hr_after_quit(outcome, pack_years, age_offset)
            else:
                hr_smoke_tgt_fn = hr_smoke_base_fn

        # 対称性の担保：current→target の変化量をそのまま指数に使う
        # baseline 側は「変化なし」= 1.0、target 側は「差分」を反映
        rr_sbp_base = 1.0
        rr_ldl_base = 1.0
        rr_a1c_base = 1.0
        rr_sbp_target = self.rr_sbp(outcome, delta_sbp)           
        rr_ldl_target = self.rr_ldl(outcome, delta_ldl_mmol)      
        rr_a1c_target = self.rr_hba1c(outcome, delta_hba1c, hba1c_target)

        risk_base = 0.0; surv_base = 1.0
        risk_tgt  = 0.0; surv_tgt  = 1.0

        for t in range(int(years)):
            age = start_age + t
            q0_or_h0 = self._interp_baseline(outcome, sex, age)
            
            # 現在のリスク因子でのリスク
            rr_total_b = rr_sbp_base * rr_ldl_base * rr_a1c_base * hr_smoke_base_fn(t)
            # 年次死亡確率を正しく累積計算
            if outcome == 'mortality':
                # q0_or_h0は既に確率（0-1の範囲）なのでそのまま使用
                q_b = min(max(q0_or_h0 * rr_total_b, 0.0), 1.0)
            else:
                q_b = 1.0 - math.exp(-q0_or_h0 * rr_total_b)
            risk_base += surv_base * q_b
            surv_base *= (1.0 - q_b)

            # 目標達成時のリスク（年齢帯ごとの alpha を直接乗せる方式）
            a_sbp   = self._alpha_by_age('sbp', age)
            a_ldl   = self._alpha_by_age('ldl', age)
            a_hba1c = self._alpha_by_age('hba1c', age)
            rr_sbp_t_eff   = rr_sbp_target ** a_sbp
            rr_ldl_t_eff   = rr_ldl_target ** a_ldl
            rr_a1c_t_eff   = rr_a1c_target ** a_hba1c
            rr_total_t = rr_sbp_t_eff * rr_ldl_t_eff * rr_a1c_t_eff * hr_smoke_tgt_fn(t)
            if outcome == 'mortality':
                # q0_or_h0は既に確率（0-1の範囲）なのでそのまま使用
                q_t = min(max(q0_or_h0 * rr_total_t, 0.0), 1.0)
            else:
                q_t = 1.0 - math.exp(-q0_or_h0 * rr_total_t)
            risk_tgt += surv_tgt * q_t
            surv_tgt *= (1.0 - q_t)

        return {'baseline': risk_base, 'target': risk_tgt}
    
    def cumulative_incidence_with_ci(self, outcome: str, sex: str, start_age: int, years: int,

                                   sbp_now: float, sbp_target: float,
                                   ldl_now_mg: float, ldl_target_mg: float,
                                   hba1c_now: float, hba1c_target: float,
                                   smoking_status: str, cigs_per_day: int,
                                   years_smoked: float, years_since_quit: float,
                                   assume_quit_today_in_target: bool = False,
                                   confidence_level: float = 0.95,
                                   bmi_now: float = None,
                                   bmi_target: float = None,
                                   egfr_now: float = None,
                                   egfr_target: float = None,
                                   acr_now: str = None,
                                   acr_target: str = None) -> dict:
        """信頼区間付きの累積リスク計算"""
        # 性別を正規化
        sex = _norm_sex(sex)
        
        # 現在の値と目標値の差を計算
        delta_sbp = sbp_now - sbp_target
        delta_ldl_mmol = (ldl_now_mg - ldl_target_mg) / 38.67
        delta_hba1c = hba1c_now - hba1c_target
        
        pack_years = (cigs_per_day / 20.0) * max(0.0, years_smoked)
        
        # 喫煙のハザード比
        if smoking_status == 'never':
            hr_smoke_base_fn = lambda age_offset: 1.0
            hr_smoke_tgt_fn  = lambda age_offset: 1.0
        elif smoking_status == 'former':
            hr_smoke_base_fn = lambda age_offset: self.hr_after_quit(outcome, pack_years, years_since_quit + age_offset)
            hr_smoke_tgt_fn  = hr_smoke_base_fn
        else:
            hr_smoke_base_fn = lambda age_offset: self.hr_current_smoker(outcome, pack_years)
            if assume_quit_today_in_target:
                hr_smoke_tgt_fn = lambda age_offset: self.hr_after_quit(outcome, pack_years, age_offset)
            else:
                hr_smoke_tgt_fn = hr_smoke_base_fn
        
        # 信頼区間の計算（3つのシナリオ）
        scenarios = ['point', 'lower', 'upper']
        # ベースラインCI幅（±p）を設定（config優先、無ければデフォルト）
        ci_cfg = (self.cfg.get('baseline_ci_percent') or {})
        p_default = {'mi': 0.20, 'stroke': 0.15, 'mortality': 0.05}
        p = float(ci_cfg.get(outcome, p_default[outcome]))
        scale = {'point': 1.0, 'lower': max(0.0, 1.0 - p), 'upper': 1.0 + p}
        results = {}
        
        for scenario in scenarios:
            # 各シナリオでの相対リスクを計算
            if scenario == 'point':
                # 点推定値：現在は1.0、目標は改善効果
                rr_sbp_base = 1.0
                rr_ldl_base = 1.0
                rr_a1c_base = 1.0
                rr_sbp_target = self.rr_sbp(outcome, delta_sbp)
                rr_ldl_target = self.rr_ldl(outcome, delta_ldl_mmol)
                rr_a1c_target = self.rr_hba1c(outcome, delta_hba1c, hba1c_target)
            else:
                # Baseline は常に RR=1.0（変化なし）。CIは当てない。
                rr_sbp_base = 1.0
                rr_ldl_base = 1.0
                rr_a1c_base = 1.0

                # Target のみに効果量の不確実性を反映
                rr_sbp_ci = self.rr_sbp_with_ci(outcome, delta_sbp, confidence_level)
                rr_ldl_ci = self.rr_ldl_with_ci(outcome, delta_ldl_mmol, confidence_level)
                rr_a1c_ci = self.rr_hba1c_with_ci(outcome, delta_hba1c, hba1c_target, confidence_level)

                rr_sbp_target = rr_sbp_ci[scenario]
                rr_ldl_target = rr_ldl_ci[scenario]
                rr_a1c_target = rr_a1c_ci[scenario]
            
            # 累積リスクの計算
            risk_base = 0.0; surv_base = 1.0
            risk_tgt  = 0.0; surv_tgt  = 1.0
            
            for t in range(int(years)):
                age = start_age + t
                q0_or_h0 = self._interp_baseline(outcome, sex, age)
                # Baseline側の不確実性：ベースライン年次リスク（qxまたはハザード近似）をスケール
                if scenario == 'point':
                    hq0_base = q0_or_h0
                else:
                    hq0_base = q0_or_h0 * scale[scenario]
                
                # 現在のリスク因子でのリスク（変化なし = 1.0）+ BMI/CKD（現在値）
                rr_total_b = rr_sbp_base * rr_ldl_base * rr_a1c_base * hr_smoke_base_fn(t)
                if bmi_now is not None:
                    rr_total_b *= self.rr_bmi(age, bmi_now)
                # CKD（現在値）
                rr_total_b *= self.rr_ckd(age, egfr_now, acr_now, outcome)
                if outcome == 'mortality':
                    q_b = min(max(hq0_base * rr_total_b, 0.0), 1.0)
                else:
                    q_b = 1.0 - math.exp(-hq0_base * rr_total_b)
                risk_base += surv_base * q_b
                surv_base *= (1.0 - q_b)
                
                # 目標達成時のリスク（年齢帯ごとの alpha を直接乗せる方式）
                a_sbp   = self._alpha_by_age('sbp', age)
                a_ldl   = self._alpha_by_age('ldl', age)
                a_hba1c = self._alpha_by_age('hba1c', age)
                rr_sbp_t_eff   = rr_sbp_target ** a_sbp
                rr_ldl_t_eff   = rr_ldl_target ** a_ldl
                rr_a1c_t_eff   = rr_a1c_target ** a_hba1c
                # 目標側 BMI
                rr_bmi_t = 1.0
                if (bmi_target is not None) or (bmi_now is not None):
                    rr_bmi_t = self.rr_bmi(age, bmi_target if bmi_target is not None else bmi_now)
                # 目標側 CKD
                rr_ckd_t = self.rr_ckd(age, egfr_target if egfr_target is not None else egfr_now,
                                        acr_target if acr_target is not None else acr_now,
                                        outcome)
                rr_total_t = rr_sbp_t_eff * rr_ldl_t_eff * rr_a1c_t_eff * rr_bmi_t * rr_ckd_t * hr_smoke_tgt_fn(t)
                if outcome == 'mortality':
                    q_t = min(max(q0_or_h0 * rr_total_t, 0.0), 1.0)
                else:
                    q_t = 1.0 - math.exp(-q0_or_h0 * rr_total_t)
                risk_tgt += surv_tgt * q_t
                surv_tgt *= (1.0 - q_t)
            
            results[scenario] = {'baseline': risk_base, 'target': risk_tgt}
        
        return results

    def cumulative_incidence_with_adjustment(
        self,
        outcome: str,
        sex: str,
        start_age: int,
        years: int,
        sbp_now: float,
        ldl_now_mg: float,
        hba1c_now: float,
        current_meds: Dict[str, List[Dict[str, Any]]],
        adjusted_meds: Dict[str, List[Dict[str, Any]]],
        smoking_status: str,
        cigs_per_day: int,
        years_smoked: float,
        years_since_quit: float,
        assume_quit_today_in_target: bool = False,
        confidence_level: float = 0.95,
        bmi_now: float = None,
        bmi_target: float = None,
        egfr_now: float = None,
        egfr_target: float = None,
        acr_now: str = None,
        acr_target: str = None,
    ) -> Dict[str, Any]:
        """
        現在の服薬状態から変更後の服薬状態への累積リスクを計算する。
        
        baseline側は現在の測定値を、そのまま使用する。
        target側は現在の測定値に薬剤変更差分を加えた値を使用する。
        """
        # 1. 薬剤変更差分を計算
        adj = MedicationAdjustment(
            sbp_now, ldl_now_mg, hba1c_now,
            current_meds, adjusted_meds
        )
        
        # 2. 変更後の目標値を取得
        adj_targets = adj.adjusted_targets()
        
        # 3. 既存メソッドを呼び出す
        # baselineは現在値そのままなので、sbp_now等をbaselineとして渡す
        res = self.cumulative_incidence_with_ci(
            outcome, sex, start_age, years,
            sbp_now, adj_targets["sbp_target"],
            ldl_now_mg, adj_targets["ldl_target"],
            hba1c_now, adj_targets["a1c_target"],
            smoking_status, cigs_per_day, years_smoked, years_since_quit,
            assume_quit_today_in_target,
            confidence_level,
            bmi_now, bmi_target,
            egfr_now, egfr_target,
            acr_now, acr_target,
        )
        
        # 4. 費用・副作用情報を付加
        res["costs"] = adj.costs()
        res["side_effect_changes"] = adj.side_effect_changes()
        
        return res
