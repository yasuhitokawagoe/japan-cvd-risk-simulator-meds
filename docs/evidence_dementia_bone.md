# 認知症・骨の健康：モデル採用根拠

最終確認日: 2026-09-26

この文書は、アプリで採用した数値、採用しなかった関連、限界を再現可能な形で残すための記録である。文献探索にはConsensusを使用し、効果量は原著またはメタ解析の記載に基づく。

## 認知症

### 構成

- 認知症は全死亡、心筋梗塞、脳卒中、透析、大切断、失明と同列の主要アウトカムとする。
- 基礎曲線は、2型糖尿病患者用DSDRSの年齢点数だけに対応する観察10年リスクへ一致させる。
- 元研究の検証範囲である10年までは実線とする。10年超は、同じ年齢別発症率と介入の相対効果が続く仮定の外挿として点線で表示する。
- 元研究の対象外である60歳未満の期間は発症率を外挿しない。
- 日本人に較正された個人予測ではなく、研究集団からの参考推定として表示する。
- 高齢者で認知症発症前の死亡を無視して累積率が過大にならないよう、厚生労働省「令和6(2024)年簡易生命表」の性・年齢別死亡率を競合リスクとして年ごとに反映する。

### 基礎曲線

ExaltoらのDiabetes Specific Dementia Risk Scoreで、年齢だけを加点し、未入力の既往症などを加点しない場合の観察10年リスクを使用する。各10年リスクへ一致する認知症ハザードを置き、同時に日本の生命表死亡ハザードを加えて累積発症関数を計算する。したがって表示値は、死亡を競合リスクとして補正する前の下表より低くなる。生命表の5歳刻み死亡確率は対数線形補間し、100歳超は100歳値を据え置く。

| 年齢 | 10年リスク |
|---|---:|
| 60–64 | 7.4% |
| 65–69 | 14.8% |
| 70–74 | 24.5% |
| 75–79 | 40.3% |
| 80–84 | 49.9% |
| 85以上 | 63.1% |

以前は年齢別粗発症率を到達年齢ごとに積算していたため、60歳の10年リスクが11.9%となり、元モデルの7.4%より高かった。2026-09-26に元モデルへ再較正した。

2026-09-26にさらに、認知症発症前の死亡を競合リスクとして追加した。特に高齢者・男性で、生存者だけを前提にした単純な1−生存曲線による過大推定を抑える。死亡率の出典: [厚生労働省 令和6年簡易生命表](https://www.mhlw.go.jp/toukei/saikin/hw/life/life24/)。

出典: Exalto LG et al. *Risk score for prediction of 10 year dementia risk in individuals with type 2 diabetes: a cohort study.* Lancet Diabetes Endocrinol. 2013;1:183-190. DOI: 10.1016/S2213-8587(13)70048-2. [Consensus](https://consensus.app/papers/risk-score-for-prediction-of-10-year-dementia-risk-in-exalto-biessels/ba8f28761c10508a89fc8c000e3c93e3/)

外的整合性の確認:

- 日本人を含むアジア系集団では白人より基礎発症率が低い可能性がある一方、日本系集団における糖尿病の相対リスクはHR 1.44で白人と同程度だった。Hayes-Larson E et al. Am J Epidemiol. 2024. DOI: 10.1093/aje/kwae051. [Consensus](https://consensus.app/papers/heterogeneity-in-the-effect-of-type-2-diabetes-on-dementia-hayes%E2%80%90larson-zhou/5ead5967f4ae5fc3a83cce0a72d2c23f/)
- 久山町研究では2012年コホートの認知症発症率が2002年コホートより低下した。現代日本人へそのまま移植すると過大推定の可能性がある。Ohara T et al. Alzheimers Res Ther. 2025;17:264. DOI: 10.1186/s13195-025-01909-1. [Consensus](https://consensus.app/papers/thirtysevenyear-trends-in-the-prevalence-incidence-and-ohara-minohara/7eb7c094342e5d568e70660d0f94af3d/)

### 曲線へ採用する介入効果

#### 降圧治療

- 採用値: 0.87
- 二重盲検RCT 5試験、28,008人の個人データメタ解析で認知症OR 0.87（95%CI 0.75–0.99）。
- 観察研究の個人データメタ解析でも、高血圧者における降圧薬使用HR 0.88（95%CI 0.79–0.98）であり、乖離は小さい。

出典:

- Peters R et al. Eur Heart J. 2022. DOI: 10.1093/eurheartj/ehac584. [Consensus](https://consensus.app/papers/blood-pressure-lowering-and-prevention-of-dementia-an-peters-xu/80e4c462131a5a9da849201e137c347d/)
- Ding J et al. Lancet Neurol. 2020;19:61-70. DOI: 10.1016/S1474-4422(19)30393-X. [Consensus](https://consensus.app/papers/antihypertensive-medications-and-risk-for-incident-ding-davis-plourde/108f37cf6c6e5c82958f0e80fe039b07/)

血圧低下は薬剤選択の有無ではなく、現在値から介入後値まで10 mmHg低下するごとに0.87を指数換算して反映する。外挿過大を避けるため30 mmHgまでとする。

#### LDL低下

- 採用値: LDL 60 mg/dL低下あたり0.74（観察研究からの探索的換算）
- LDL 70 mg/dL未満は130 mg/dL超と比較して全認知症が26%少なかった。連続的な用量反応は未確立のため、60 mg/dL差を上限として対数線形換算する。
- スタチン使用は低LDL群内でも追加13%低下と関連したため、LDL値による効果とスタチン固有の観察研究効果を別に反映する。
- 薬剤、食事、運動、手入力を問わず、実際のLDL低下量から計算する。

出典: Lee MW et al. J Neurol Neurosurg Psychiatry. 2025;96:981-989. DOI: 10.1136/jnnp-2024-334708. [Consensus](https://consensus.app/papers/lowdensity-lipoprotein-cholesterol-levels-and-risk-of-lee-lee/4bf9a1f3fed25c058b00c34b5a05de67/)

#### GLP-1受容体作動薬

- 採用値: 0.90（保守的中心値）
- 109,778人の観察コホートで認知症HR 0.90（95%CI 0.83–0.97）。
- 観察研究ネットワークメタ解析ではOR 0.58、探索的RCTメタ解析ではOR 0.55だが、認知症は多くの試験で主要評価項目ではない。
- 研究間の幅が大きいため、曲線には最も保守的な0.90を使用する。

出典:

- Cheng HW et al. Diabetes Metab Res Rev. 2025;41. DOI: 10.1002/dmrr.70058. [Consensus](https://consensus.app/papers/impact-of-glucagon%E2%80%90like-peptide%E2%80%901-receptor-agonists-on-cheng-yang/89acae5b8222597b836f4beedcfe34d8/)
- Li ZL et al. Alzheimers Res Ther. 2024;16. DOI: 10.1186/s13195-024-01645-y. [Consensus](https://consensus.app/papers/antidiabetic-agents-and-the-risks-of-dementia-in-patients-li-lin/9856bad4379c53e1acf01068f0233af3/)

#### スタチン

- 採用値: 0.87（観察研究）
- 観察研究55件、700万人超のメタ解析で全体HR 0.86（95%CI 0.82–0.91）、2型糖尿病サブグループHR 0.87（95%CI 0.85–0.89）。
- RCTでは認知症予防効果が確立していないため、画面上で観察研究由来と明示する。同一クラスの複数選択は重複計上しない。

出典: Westphal F et al. Alzheimers Dement (N Y). 2025;11. DOI: 10.1002/trc2.70039. [Consensus](https://consensus.app/papers/statin-use-and-dementia-risk-a-systematic-review-and-westphal-lopes/ee237a45c6cc5bcd9113cdfa6f85426f/)

#### SGLT2阻害薬

- 採用値: 0.56（観察研究）
- 41観察研究、3,307,483人のネットワークメタ解析で、非使用者に対する全認知症OR 0.56（95%CI 0.45–0.69）。RCTでは薬剤間・プラセボ間の認知症リスク差は確立していない。

#### ビグアナイド（メトホルミン）

- 採用値: 0.89（観察研究の保守値）
- 同ネットワークメタ解析で全認知症OR 0.89（95%CI 0.80–0.99）。別の20コホート、3,463,100人のメタ解析では非使用者比HR 0.76だったが、I² 98.9%と異質性が高いため0.89を使用する。

出典:

- Li ZL et al. Alzheimers Res Ther. 2024;16. DOI: 10.1186/s13195-024-01645-y. [Consensus](https://consensus.app/papers/antidiabetic-agents-and-the-risks-of-dementia-in-patients-li-lin/9856bad4379c53e1acf01068f0233af3/)
- Tang C et al. Diabetes Obes Metab. 2025;27:1992-2001. DOI: 10.1111/dom.16192. [Consensus](https://consensus.app/papers/association-of-metformin-use-with-risk-of-dementia-in-tang-hao/92b46ddd42815880a49c1f15d978e5e5/)

### 曲線へ採用しない関連

- HbA1c強化: 厳格血糖管理RCTでは認知機能低下予防が一貫せず、低血糖の害も考慮し、HbA1c低下量から認知症効果を推定しない。
- DPP-4阻害薬: Alzheimer病ではOR 0.73が報告されたが、全認知症の有意な予防効果が示されていないため採用しない。
- GIP/GLP-1受容体作動薬: GLP-1単独の結果をチルゼパチドへ外挿しない。
- PCSK9阻害薬・吸収阻害薬: 認知症予防の直接的な効果量を採用できる根拠がない。
- 併用: 異なる薬剤クラスの直接的な併用効果試験はない。選択時は独立・乗算を仮定し、同一クラスは1回だけ計上する。

## 骨粗鬆症・骨折

### アプリでの位置付け

- 主要アウトカムではなく「骨の健康（参考）」とする。
- 骨密度、既往骨折、末梢神経障害、転倒歴などが未入力のため、絶対リスク曲線や骨粗鬆症診断を表示しない。
- 現在の入力で確認できる年齢、性別、低BMI、腎機能、インスリン使用から、追加評価を検討するフラグのみ表示する。

### 根拠

- 日本の全国調査では2017年の大腿骨近位部骨折は約193,400件と推定され、年齢・性別差が大きい。Takusari E et al. JBMR Plus. 2021;5. DOI: 10.1002/jbm4.10428. [Consensus](https://consensus.app/papers/trends-in-hip-fracture-incidence-in-japan-estimates-based-takusari-sakata/cc4a0b53336757fa9fdd09ee3e2ef9e0/)
- 中国の2型糖尿病患者用CDFRモデルは、年齢、性別、既往骨折、インスリン、末梢神経障害、脂質項目を含み、10年主要骨粗鬆症性骨折のC統計量0.803。ただし単施設で外部検証が不足する。Kong XK et al. Osteoporos Int. 2022;33:1957-1967. DOI: 10.1007/s00198-022-06425-8. [Consensus](https://consensus.app/papers/major-osteoporosis-fracture-prediction-in-type-2-diabetes-kong-zhao/ab024f9bfd1552d8a948c9c9bf03a515/)
- 骨粗鬆症治療薬は69 RCT、8万人超のネットワークメタ解析で骨折予防効果が確認されている。Händel MN et al. BMJ. 2023;381:e068033. DOI: 10.1136/bmj-2021-068033. [Consensus](https://consensus.app/papers/fracture-risk-reduction-and-safety-by-osteoporosis-h%C3%A4ndel-cardoso/ed519e3e91b452beb364985de7d04176/)
- DPP-4阻害薬、GLP-1受容体作動薬、SGLT2阻害薬は177 RCT、165,081人の解析で全骨折リスクを有意に増加させなかった。ただし追跡中央値26週と短く、骨折予防効果としては使用しない。Chai S et al. Front Pharmacol. 2022;13:825417. DOI: 10.3389/fphar.2022.825417. [Consensus](https://consensus.app/papers/risk-of-fracture-with-dipeptidyl-peptidase4-inhibitors-chai-liu/3c397c65e77d5d94b942366f34a47365/)

### 将来、数値曲線へ拡張する条件

少なくとも既往骨折、DXA/Tスコア、末梢神経障害、転倒歴、ステロイド、飲酒、骨粗鬆症薬を追加入力し、日本人または日本で較正されたモデルを採用する。条件が揃うまでは、骨折確率を表示しない。
