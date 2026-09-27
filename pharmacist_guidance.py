"""Evidence-linked counseling, isolated from all risk/effect calculations.

Adult counseling prompts, not an exhaustive contraindication or prescribing engine.
Source review and scope: docs/evidence_pharmacist_guidance.md.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from html import escape
from typing import Iterable, Mapping

REVIEWED_ON = "2026-09-27"
VERSION = "2026-09-27.1"
SICK_DAY_URL = "https://dmic.jihs.go.jp/general/about-dm/040/060/06.html"
LOW_GLUCOSE_URL = "https://dmic.jihs.go.jp/general/about-dm/040/050/05.html"
SGLT2_URL = "https://www.fa.kyorin.co.jp/jds/uploads/recommendation_SGLT2.pdf"

EMERGENCY = (
    "意識がない・反応がおかしい、強い息苦しさ、強い胸痛、突然の片側の麻痺や言葉の出にくさは119番。"
    "唇・舌・のどの腫れと呼吸の異常も救急です。測定や薬局への連絡を待たずに対応してください。"
)
GENERAL = (
    "薬袋・お薬手帳の用法を優先し、飲み忘れを埋めるために2回分をまとめて使わないでください。",
    "下記の休薬・受診の注意や、あらかじめ医師と決めた対応を除き、自分で増減・中止・再開しないでください。",
    "市販薬・サプリ・他院の薬、妊娠の可能性、手術・検査の予定を医師・薬剤師へ伝えてください。",
)
BP_LOW = (
    "立ちくらみ・ふらつきがあれば転倒しないよう座るか横になり、運転を避けてください。"
    "落ち着いて測れる状態なら血圧・脈拍・症状を記録し、普段より低い状態や症状が続くときは当日中に医療機関へ相談。"
    "一度の数値だけで全員同じように休薬する基準は設けず、次の服用は個別の指示を確認してください。"
)
LOW_GLUCOSE = (
    "血糖値が70mg/dL未満、または冷汗・手のふるえ・強い空腹など低血糖が疑われる場合は対応します。"
    "意識がはっきりして安全に飲み込める場合はブドウ糖10g。"
    "15分後に症状と測れる場合は血糖を確認し、低値や症状が続けば同量をもう一度とり、改善しない・繰り返す場合は速やかに受診。"
    "意識が悪い・飲み込めない場合は口に物を入れず119番。回復しても医療機関へ連絡してください。"
)
DIABETES_SICK = (
    "発熱・嘔吐・下痢・食事がとれない日は早めに医療機関へ連絡し、食事量、飲水量、症状、測れる場合は血糖値を伝えてください。"
    "水分も保てない、強いだるさ、意識の変化は受診を急いでください。"
    "併用中のインスリンは一律に中止せず、事前に決めた指示を確認してください。"
)
DENTAL = "歯科にも薬名を伝え、口の清潔と歯科受診を続けてください。抜歯前に自分で休薬せず、処方医と歯科医で相談します。"
MUSCLE = "原因不明の強い筋肉痛・脱力・赤褐色の尿は、次の服用を見合わせて速やかに医療機関へ連絡・受診してください。"
PANCREAS = "強い腹痛が続くとき（吐き気・嘔吐を伴う場合を含む）は使用を中止し、すぐ受診してください。腹部の張りと嘔吐、便・ガスが出ない場合も受診を急いでください。"


@dataclass(frozen=True)
class Content:
    focus: str
    routine: tuple[str, ...]
    sick: tuple[str, ...]
    urgent: tuple[str, ...]
    missed: str = "2回分をまとめて使わず、薬袋・患者向けガイドの指示を確認。不明なら薬剤師に相談してください。"


CLASSES = {
    "ccb": Content("立ちくらみ・むくみと飲み合わせ", ("家庭血圧と、足のむくみ・動悸などの変化を記録してください。", "グレープフルーツジュースとの飲み合わせに注意し、摂取を控えてください。"), (BP_LOW,), ("失神や強い息苦しさは救急。むくみが急に増えるときは医療機関へ相談してください。",)),
    "arb": Content("血圧低下・脱水・カリウム", ("血圧の記録に加え、腎機能とカリウムの採血予定を確認してください。", "カリウム入り減塩塩・サプリや市販の鎮痛薬を追加する前に相談。妊娠に気づいたら服用を中止し、直ちに医師へ連絡してください。"), (BP_LOW, "嘔吐・下痢や飲水困難があるときは、脱水による腎機能悪化の懸念があるため次の服用について当日中に相談してください。"), ("尿が極端に減る、強い脱力・脈の乱れは速やかに受診。舌・のどの腫れと息苦しさは119番。",)),
    "ace": Content("空咳・血管性浮腫・血圧低下", ("腎機能・カリウムを定期確認。空咳が続く場合は相談してください。", "妊娠に気づいたら服用を中止し、直ちに医師へ連絡。エンレストとの切替は医師の指示が必要です。"), (BP_LOW, "嘔吐・下痢や飲水困難時は次の服用を当日中に医療機関へ確認してください。"), ("唇・舌・のどが腫れたら使用を中止し、直ちに受診。呼吸がおかしいときは119番。",)),
    "beta": Content("急にやめない・脈が遅いとき", ("血圧と脈拍を記録。自己判断で急に中断すると病状が悪化するおそれがあります。", "糖尿病薬も使用中なら低血糖の動悸などに気づきにくいことがあります。冷汗などにも注意してください。"), (BP_LOW, "食べられない日や脈が普段より遅く、だるい日は当日中に相談。急な中断・再開は医師の指示を確認してください。"), ("失神、強い息苦しさ、胸痛は119番。息切れ・むくみ・体重増加の悪化も早めに相談してください。",)),
    "arni": Content("ACE阻害薬との切替・低血圧", ("腎機能・カリウム・家庭血圧を確認。ACE阻害薬との同時使用は禁止され、相互の切替には少なくとも36時間の間隔が必要です。", "ARB成分を含みます。他のARBとの重複や妊娠の可能性を必ず確認してください。"), (BP_LOW, "脱水時は次の服用を当日中に相談。妊娠に気づいたら服用を中止し、直ちに医師へ連絡してください。"), ("唇・舌・のどの腫れは使用を中止して直ちに受診。呼吸の異常は119番。尿量の著しい減少も速やかに相談。",)),
    "thiazide": Content("脱水・塩分やカリウムの異常", ("採血でナトリウム・カリウム・腎機能・尿酸を確認。血圧と体重を記録してください。", "飲水量は心臓・腎臓の状態に合わせた指示を優先し、無理な水分制限や大量飲水は避けてください。"), (BP_LOW, "高熱・嘔吐・下痢や水分がとれない日は、次の服用を当日中に医療機関へ確認してください。"), ("意識の変化・けいれんは119番。強い脱力、筋けいれん、尿量減少は速やかに受診してください。",)),
    "mra": Content("高カリウム血症を採血で確認", ("腎機能とカリウムの採血を忘れずに。カリウム入り減塩塩・サプリや鎮痛薬を追加する前に相談してください。", "ほかのカリウムを保持する利尿薬との重複を処方医・薬剤師が確認します。"), (BP_LOW, "嘔吐・下痢、飲水困難時は次の服用を当日中に相談。尿量の変化も伝えてください。"), ("強い脱力、手足のしびれ、脈の乱れ、尿量の著しい減少は速やかに受診。失神は119番。",)),
    "statin": Content("筋肉症状・飲み合わせの確認", ("脂質・肝機能の検査を継続。抗菌薬、市販薬やサプリを追加する前に薬剤師へ確認してください。", "妊娠の可能性や授乳中であることを必ず伝え、妊娠が分かった場合は服用せず医師へ連絡してください。"), ("食べられない・脱水がある日は相談。単にLDL値が低くなったという理由で自己中断しないでください。",), (MUSCLE, "皮膚や白目が黄色い、濃い尿と強いだるさがある場合は速やかに相談してください。")),
    "ezetimibe": Content("併用薬・筋肉症状の確認", ("脂質検査を継続。スタチン併用時は筋肉症状や肝機能にも注意します。",), ("嘔吐・下痢や食事がとれない日は相談。LDL値だけで自己中断しないでください。",), (MUSCLE, "黄疸や強いだるさは速やかに相談。顔・のどの腫れと息苦しさは119番。")),
    "pcsk9": Content("注射日・保管と自己注射の手順", ("処方された注射間隔を確認。自己注射は指導を受けてから行い、器具を共有しないでください。", "凍結を避けた冷蔵保管など、使用製品の説明書に従い、注射部位を変えてください。"), ("発熱や体調不良で注射できないときは、追加注射せず日程を医療機関へ確認してください。",), ("全身のじんましんや顔・のどの腫れは直ちに相談。息苦しさ・意識の異常は119番。",), "注射を忘れたら次回日程を医療機関へ確認し、埋め合わせで2回分を注射しないでください。"),
    "inclisiran": Content("医療機関での注射予約を守る", ("初回、3か月後、その後6か月ごとの医療機関での注射です。次回予約を確認してください。", "注射した場所の痛み・赤み・腫れが続く場合は相談してください。"), ("体調不良や予約に行けない場合は医療機関へ連絡して日程を調整。自宅で追加注射する薬ではありません。",), ("全身のじんましん・顔の腫れは直ちに相談。強い息苦しさや意識の異常は119番。",), "予約を過ぎたら医療機関に連絡してください。遅れに応じた投与計画は医師が決めます。"),
    "acl": Content("尿酸・痛風とスタチン併用", ("尿酸値を確認し、痛風歴を伝えてください。スタチン併用時は筋肉症状とCKなども確認します。", "妊娠の可能性を伝え、妊娠が分かったら使用せず医師へ連絡してください。"), ("急に関節が赤く腫れて痛む場合や、脱水・食事がとれない場合は医療機関へ相談してください。",), (MUSCLE,)),
    "metformin": Content("シックデイは一時休薬・乳酸アシドーシス", ("腎機能検査を継続し、過度の飲酒を避けてください。", "ヨード造影検査や手術の前には薬名を伝え、休薬期間と再開の指示を事前に確認してください。"), ("発熱・嘔吐・下痢・食事が十分とれない日や脱水時は、いったん休薬し、医療機関へ連絡してください。再開は回復状況と医師の指示を確認します。", DIABETES_SICK), ("吐き気・腹痛と強いだるさ、筋肉痛、息苦しさがある場合は乳酸アシドーシスの可能性があるため、使用を中止して直ちに受診してください。",), "忘れた分は飛ばして次の服用時に1回分。2回分を一度に飲まないでください。"),
    "sglt2": Content("シックデイの休薬・血糖が高くなくても注意", ("脱水と陰部・尿路の感染に注意。飲水量は心不全・腎臓病の指示に合わせてください。", "予定手術の休薬計画を早めに相談。糖尿病治療では学会は術前3日前からの休薬を推奨しています。適応・術式に合わせ処方医に確認してください。"), ("発熱・嘔吐・下痢・食事が十分とれない日や脱水時は休薬して医療機関へ連絡。回復後の再開は医師に確認してください。", DIABETES_SICK), ("血糖値が高くなくても、強いだるさ・吐き気・腹痛・息苦しさはケトアシドーシスの可能性があり、使用を中止して直ちに受診。", "陰部・会陰の強い痛みや腫れと発熱、背中の痛みと発熱は受診を急いでください。")),
    "dpp4": Content("低血糖・強い腹痛・水ぶくれ", ("特にSU薬やインスリンとの併用時は低血糖に注意。腎機能に応じた用量確認が必要な製品があります。",), (DIABETES_SICK, "一律の休薬や半量への変更はせず、食事量・血糖・併用薬を伝えて次の服用を確認してください。"), (PANCREAS, "皮膚に広がる水ぶくれ・ただれは使用を中止し、速やかに医師へ相談してください。")),
    "glp1": Content("強い腹痛・嘔吐・脱水に注意", ("自己判断で増量しないでください。吐き気や便秘、食事量・体重の変化を確認します。", "手術・内視鏡で麻酔や深い鎮静を予定する場合は薬名と最終使用日を伝えてください。"), (DIABETES_SICK, "嘔吐が続く、飲水・食事ができない場合は次の使用前に医療機関へ連絡。週1回薬は中断後もしばらく作用が残ります。"), (PANCREAS, "水分が保てない・尿が減るときも受診を急いでください。")),
    "imeglimin": Content("胃腸症状・腎機能に応じた用量確認", ("吐き気・下痢・食事量の低下を確認。メトホルミン併用時は胃腸症状に特に注意してください。", "腎機能で用量・回数が変わります。検査値を確認し、自己調整しないでください。"), (DIABETES_SICK, "食べられないときは次の服用を相談。メトホルミンと同じ薬ではなく、その休薬ルールを機械的には当てはめません。"), ("飲水できないほどの嘔吐・下痢や低血糖が続く場合は速やかに受診してください。",)),
    "su": Content("食べられない日の低血糖を防ぐ", ("食事を抜く・食事量が減ると低血糖が起きやすくなります。ブドウ糖を携帯し、家族とも対応を共有してください。",), (DIABETES_SICK, "食事がとれない場合は減量・休薬が必要になることがあります。事前のシックデイ指示に従い、なければ次の服用前に医療機関へ相談してください。"), ("低血糖は一度改善しても再発・長引くことがあります。繰り返すときは速やかに受診してください。",)),
    "tzd": Content("むくみ・体重増加・息切れ", ("体重・足のむくみを確認。心不全のある方や既往がある方は使用できないため、必ず伝えてください。", "骨折歴や血尿も医師へ伝えてください。"), (DIABETES_SICK, "急な体重増加、むくみ、息切れがあれば使用を中止して医師へ連絡してください。"), ("強い息苦しさや胸痛は119番。新しい血尿や排尿痛は速やかに相談してください。",)),
    "oral_bone": Content("起床時の飲み方・横にならない", ("内服錠は起床時、食事や他の薬より前に、コップ1杯の水でかまずに服用。少なくとも30分は横にならず、飲食・他の内服も避けます。", DENTAL), ("吐いている、飲み込めない、上体を起こせない日は無理に服用せず医療機関へ相談してください。",), ("飲み込むときの痛み・胸やけ・胸の痛みは服用を中止して受診。あごや太ももの付け根の痛みも早めに相談してください。",), "毎日・週1回・月1回など製剤で異なります。実際の製品を確認し、忘れた分をまとめず薬剤師に確認してください。"),
    "zoledronate": Content("点滴前後の脱水・腎機能", ("点滴前後の腎機能・カルシウム検査を確認。飲水量は医師の指示に従ってください。", DENTAL), ("発熱・嘔吐・下痢で脱水がある場合は予定どおり点滴せず、事前に医療機関へ連絡してください。",), ("点滴後に尿が減る、飲水できない、唇・指先のしびれがある場合は速やかに受診。けいれんは119番。",), "年1回の骨粗鬆症用点滴です。予約に行けないときは医療機関へ連絡して調整してください。"),
    "denosumab": Content("注射を自己中断しない・低カルシウム", ("骨粗鬆症では通常6か月ごと。中断・終了後に複数の背骨の骨折が起きることがあるため、後続治療も含め医師と計画します。", "指示されたカルシウム・ビタミンDと採血を継続。特に重い腎機能低下がある方は要確認。", DENTAL), ("体調不良や補充薬が飲めない場合、予約に行けない場合は医療機関へ連絡し、自己判断で延期を続けないでください。",), ("唇・指先のしびれ、筋けいれんはすぐ受診。強いけいれん・意識異常は119番。新しい強い背中の痛みも相談してください。",), "注射予定を過ぎたらすぐ医療機関へ連絡し、投与日程を確認してください。"),
    "romosozumab": Content("心血管症状・12か月後の治療計画", ("過去1年以内の心筋梗塞などの虚血性心疾患・脳血管障害を必ず申告してください。", "通常月1回、12か月まで。終了後の別の骨粗鬆症薬と、カルシウム・ビタミンDの指示を確認してください。", DENTAL), ("体調不良や注射予約の変更は医療機関へ連絡。後続薬は処方医の指示で開始し、自動的に追加しません。",), ("突然の胸痛、冷汗、片側の麻痺・言葉が出ない場合は119番。唇・指先のしびれやけいれんも直ちに受診してください。",), "予約を過ぎたら医療機関へ連絡。自分で投与間隔や本数を変えないでください。"),
    "teriparatide": Content("注射後のふらつき・製剤と回数の確認", ("毎日・週単位など製剤で回数・器具が異なります。実薬の名前、回数、使用期間を確認してください。", "注射後は安静にし、ふらつきがあれば座るか横になってください。器具は共有せず製品の保管・廃棄方法に従います。"), ("体調不良や嘔吐が続くときは次の注射前に医療機関へ相談してください。",), ("失神・意識の異常は119番。吐き気・便秘と強い脱力が続く場合は速やかに受診してください。",), "製剤ごとに異なるため薬剤師へ確認し、2回分を一度に注射しないでください。"),
    "serm": Content("血栓の症状・手術や長期安静の予定", ("閉経後骨粗鬆症の薬です。血栓症の既往や手術・長期安静の予定を必ず伝えてください。",), ("長く寝たきりになる予定では、少なくとも3日前からの休薬が必要です。予定外に動けなくなった場合もすぐ連絡し、再開は十分に歩ける状態になって医師へ確認してください。",), ("片脚の痛み・腫れや急な視力異常は服用を中止して直ちに受診。突然の息苦しさ・胸痛は119番。",)),
}


@dataclass(frozen=True)
class Guide:
    id: str
    name: str
    group: str
    source_url: str
    extra: str = ""
    missed: str = ""
    domain: str = ""

    @property
    def content(self) -> Content:
        base = CLASSES[self.group]
        return replace(base, routine=base.routine + ((self.extra,) if self.extra else ()),
                       missed=self.missed or base.missed)


# Exact catalog names, not substring inference. Unreviewed additions fail coverage tests.
GUIDES = (
    Guide("amlodipine", "アムロジピン", "ccb", "https://www.info.pmda.go.jp/downfiles/guide/ph/450064_2171022F1053_2_00G.pdf"),
    Guide("cilnidipine", "シルニジピン", "ccb", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2149037F1032_2?user=1"),
    Guide("nifedipine", "ニフェジピンCR", "ccb", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/630004_2171014G3022_1_26", "CR錠は割る・砕く・かむことをせず、そのまま飲んでください。"),
    Guide("azilsartan", "アジルサルタン", "arb", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2149048F1022_1?user=1"),
    Guide("olmesartan", "オルメサルタン", "arb", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2149044F5020_1?user=1", "長引く下痢や体重減少があれば薬名を伝え、医師へ相談してください。"),
    Guide("candesartan", "カンデサルタン", "arb", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2149040F1026_2?user=1"),
    Guide("telmisartan", "テルミサルタン", "arb", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2149042F1025_1?user=1"),
    Guide("losartan", "ロサルタン", "arb", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/181615_2149039F1031_3_04"),
    Guide("enalapril", "エナラプリル（レニベース）", "ace", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2144002F1024_3?user=2"),
    Guide("carvedilol", "カルベジロール", "beta", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/430574_2149032F1021_2_15"),
    Guide("bisoprolol", "ビソプロロール", "beta", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/400315_2123016F1107_1_20"),
    Guide("sacubitril_valsartan", "サクビトリル/バルサルタン", "arni", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/300242_2190041F1027_1_09"),
    Guide("hctz", "ヒドロクロロチアジド", "thiazide", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/480235_2132004F1103_1_08"),
    Guide("trichlormethiazide", "フルイトラン（トリクロルメチアジド）", "thiazide", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/343018_2132003F1257_2_04"),
    Guide("spironolactone", "スピロノラクトン", "mra", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2133001C1097_3?user=1", "乳房の張り・痛みなどが続く場合も相談してください。"),
    Guide("esaxerenone", "ミネブロ（エサキセレノン）", "mra", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2149049F1027_1?user=1"),
    Guide("atorvastatin", "アトルバスタチン", "statin", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2189015F1023_2?user=1", "グレープフルーツジュースを多量にとらず、飲み合わせを相談してください。"),
    Guide("rosuvastatin", "ロスバスタチン", "statin", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/670227_2189017F1022_1_33", "腎機能が低下している場合は用量の確認が必要です。"),
    Guide("pitavastatin", "ピタバスタチン", "statin", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2189016F1028_1?user=1"),
    Guide("pravastatin", "プラバスタチン", "statin", "https://www.info.pmda.go.jp/downfiles/guide/ph/430574_2189010C1032_2_00G.pdf"),
    Guide("ezetimibe", "エゼチミブ", "ezetimibe", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2189018F1027_3?user=1"),
    Guide("evolocumab", "レパーサ（エボロクマブ）", "pcsk9", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2189401G2026_2?user=1"),
    Guide("inclisiran", "レクビオ（インクリシラン）", "inclisiran", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/2189403G1029_1?user=1"),
    Guide("bempedoic_acid", "ネクセトール（ベムペド酸）", "acl", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/180078_2189022F1023_1_01"),
    Guide("metformin", "メトホルミン", "metformin", "https://www.info.pmda.go.jp/downfiles/guide/ph/400093_3962002F2027_1_00G.pdf"),
    Guide("sitagliptin", "ジャヌビア（シタグリプチン）", "dpp4", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3969010F1034_2?user=1", "腎機能によって用量調整が必要です。"),
    Guide("teneligliptin", "テネリア（テネリグリプチン）", "dpp4", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3969015F1029_2?user=1"),
    Guide("linagliptin", "トラゼンタ", "dpp4", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3969014F1024_1?user=1"),
    Guide("empagliflozin", "ジャディアンス", "sglt2", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3969023F1023_1?user=1"),
    Guide("dapagliflozin", "フォシーガ（ダパグリフロジン）", "sglt2", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3969019F1027_2?user=1"),
    Guide("canagliflozin", "カナグル（カナグリフロジン）", "sglt2", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3969022F1029_1?user=1"),
    Guide("ipragliflozin", "スーグラ（イプラグリフロジン）", "sglt2", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3969018F1022_1?user=1"),
    Guide("semaglutide_oral", "リベルサス（セマグルチド）", "glp1", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/620023_2499014F1021_1_07", "その日の最初の飲食前、空腹で水120mL以下と1錠を服用。少なくとも30分は飲食・他の内服を避け、割ったりかんだりしないでください。", "飲み忘れた日は服用せず、翌日に通常どおり1回分。2回分をまとめないでください。"),
    Guide("semaglutide_injection", "オゼンピック（セマグルチド）", "glp1", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/620023_2499418G4027_1_07", "週1回、決めた曜日の注射です。自己注射の手順・保管・針の廃棄を確認し、注入器は共有しません。", "次の予定まで48時間以上なら気づいた時に1回分、48時間未満なら飛ばして予定日に。判断に迷えば医療機関に確認してください。"),
    Guide("dulaglutide", "トルリシティ（デュラグルチド）", "glp1", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/ResultDataSetPDF/530471_2499416G1029_1_24", "週1回、決めた曜日の注射。保管・器具の操作と廃棄を確認してください。", "次の予定まで72時間以上なら気づいた時に1回分、72時間未満なら飛ばして予定日に。2回分をまとめないでください。"),
    Guide("liraglutide", "ビクトーザ（リラグルチド）", "glp1", "https://www.pmda.go.jp/PmdaSearch/rdSearch/02/2499410G1021?user=1", "1日1回の注射です。週1回薬と混同せず、自己注射の手順・保管・針の廃棄を確認してください。", "2回分をまとめず、再開する量・タイミングは医療機関へ確認してください。"),
    Guide("tirzepatide", "マンジャロ（チルゼパチド）", "glp1", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/530471_2499422G1024_1_11", "週1回、決めた曜日の注射です。同じ成分のゼップバウンドなどとの重複を避け、処方どおりの増量間隔を守ってください。", "次の予定まで72時間以上なら気づいた時に1回分、72時間未満なら飛ばして予定日に。2回分をまとめないでください。"),
    Guide("imeglimin", "ツイミーグ（イメグリミン）", "imeglimin", "https://www.pmda.go.jp/PmdaSearch/iyakuDetail/400093_3969026F1027_1_07"),
    Guide("pioglitazone", "ピオグリタゾン", "tzd", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3969007F1024_2?user=1"),
    Guide("glimepiride", "グリメピリド", "su", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3961008F1020_1?user=1"),
    Guide("alendronate", "アレンドロネート", "oral_bone", "https://www.info.pmda.go.jp/downfiles/ph/GUI/181615_3999018F2028_3_02G.pdf", "この説明は内服錠向けです。ゼリー・点滴など別剤形では製品ごとの説明を確認してください。", domain="bone"),
    Guide("risedronate", "リセドロネート", "oral_bone", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3999019F2022_2?user=1", "毎日・週1回・月1回製剤の取り違えに注意し、実際の製品名・規格を確認してください。", domain="bone"),
    Guide("zoledronate", "ゾレドロン酸", "zoledronate", "https://www.info.pmda.go.jp/downfiles/ph/GUI/100898_3999423A5023_1_00G.pdf", domain="bone"),
    Guide("denosumab", "デノスマブ", "denosumab", "https://www.pmda.go.jp/PmdaSearch/rdDetail/iyaku/3999435G1023_1?user=1", domain="bone"),
    Guide("romosozumab_alendronate", "ロモソズマブ（12か月）", "romosozumab", "https://www.info.pmda.go.jp/downfiles/guide/ph/112292_3999449G1025_2_00G.pdf", domain="bone"),
    Guide("teriparatide", "テリパラチド", "teriparatide", "https://www.info.pmda.go.jp/downfiles/ph/GUI/530471_2439400G1020_1_17G.pdf", "参照資料は毎日注射のフォルテオです。週単位の製剤ではその製品の説明書も確認してください。", domain="bone"),
    Guide("raloxifene", "ラロキシフェン（SERM）", "serm", "https://www.info.pmda.go.jp/downfiles/ph/GUI/530471_3999021F1023_1_01G.pdf", domain="bone"),
)
BY_ID = {g.id: g for g in GUIDES}
BY_NAME = {g.name: g for g in GUIDES}
DIABETES_GROUPS = {"metformin", "sglt2", "dpp4", "glp1", "imeglimin", "tzd", "su"}
BP_GROUPS = {"ccb", "arb", "ace", "beta", "arni", "thiazide", "mra"}


def candidate_ids(medications: Iterable[Mapping], bone_key: str = "none") -> tuple[list[str], list[str]]:
    """Candidates only; never mark an actual prescription as confirmed."""
    ids, missing = [], []
    for medication in medications:
        name = medication.get("drug_name", "")
        guide = BY_NAME.get(name)
        if guide is None:
            missing.append(str(medication.get("key", name)))
        elif guide.id not in ids:
            ids.append(guide.id)
    if bone_key != "none":
        if bone_key in BY_ID and BY_ID[bone_key].domain == "bone":
            ids.append(bone_key)
        else:
            missing.append(bone_key)
    return ids, missing


def selection_alerts(ids: Iterable[str]) -> list[tuple[str, str]]:
    """Limited counseling checks, NOT a comprehensive interaction checker."""
    chosen = [BY_ID[key] for key in dict.fromkeys(ids)]
    groups = {g.group for g in chosen}
    keys = {g.id for g in chosen}
    alerts = []
    if {"ace", "arni"} <= groups:
        alerts.append(("block", "ACE阻害薬とARNIが同時に選ばれています。併用禁忌です。処方医へ確認し、現在の薬と切替前の薬を整理してください。切替には少なくとも36時間必要です。"))
    if {"spironolactone", "esaxerenone"} <= keys:
        alerts.append(("block", "スピロノラクトンとミネブロは併用禁忌です。処方医へ確認し、実際の服用薬を整理してください。"))
    if {"arni", "arb"} <= groups:
        alerts.append(("warning", "ARNIはARB成分を含みます。別のARBとの重複を処方医へ確認してください。"))
    if "glp1" in groups and ("dpp4" in groups or sum(g.group == "glp1" for g in chosen) > 1):
        alerts.append(("warning", "GLP-1/GIP関連薬とDPP-4阻害薬、またはGLP-1/GIP関連薬同士が選ばれています。重複や切替前の薬が混ざっていないか、処方医へ確認してください。"))
    if "sglt2" in groups and groups & {"thiazide", "mra"}:
        alerts.append(("warning", "SGLT2阻害薬と利尿作用のある薬の併用です。脱水時の連絡・休薬計画を個別に確認してください。"))
    if "su" in groups and len(groups & DIABETES_GROUPS) > 1:
        alerts.append(("warning", "SU薬を含む糖尿病薬の併用です。低血糖と、食事がとれない日の具体的な対応を確認してください。"))
    if "acl" in groups and "statin" in groups:
        alerts.append(("warning", "ネクセトールとスタチンの併用です。筋肉症状とCKなどの確認をお願いします。"))
    for group in sorted(groups - {"glp1", "oral_bone"}):
        if sum(g.group == group for g in chosen) > 1:
            alerts.append(("warning", "同じクラスの薬が複数選ばれています：" + "、".join(g.name for g in chosen if g.group == group) + "。意図した併用か、切替前後の重複か確認してください。"))
    return alerts


def export_ready(ids: Iterable[str], regimens: Mapping[str, str], *, actual_confirmed: bool,
                 reviewed: bool) -> bool:
    keys = tuple(dict.fromkeys(ids))
    return bool(keys and all(key in BY_ID for key in keys) and actual_confirmed and reviewed
                and all(regimens.get(key, "").strip() for key in keys)
                and not any(level == "block" for level, _ in selection_alerts(keys)))


def handout_html(ids: Iterable[str], regimens: Mapping[str, str], notes: Mapping[str, str],
                 contact: str, *, actual_confirmed: bool, reviewed: bool) -> str:
    keys = tuple(dict.fromkeys(ids))
    if not export_ready(keys, regimens, actual_confirmed=actual_confirmed, reviewed=reviewed):
        raise ValueError("実薬・用法と指導内容の確認が必要です。禁忌の組合せは解消してください。")
    def paragraphs(items):
        return "".join(f"<p>{escape(item)}</p>" for item in items)
    sections = [f"<h1>お薬の注意点・体調が悪い日の対応</h1><p>資料確認日：{REVIEWED_ON}</p>",
                f"<aside>{escape(EMERGENCY)}</aside>", paragraphs(GENERAL),
                f"<h2>相談先</h2><p>{escape(contact.strip() or '未記入：かかりつけ医療機関・薬局の連絡先を確認してください。')}</p>"]
    if any(BY_ID[key].group in DIABETES_GROUPS for key in keys):
        sections += ["<h2>低血糖のとき</h2>", paragraphs((LOW_GLUCOSE,)),
                     f'<a href="{LOW_GLUCOSE_URL}">糖尿病情報センター：低血糖</a>']
    for key in keys:
        guide, content = BY_ID[key], BY_ID[key].content
        sections += [f"<section><h2>{escape(guide.name)}</h2><p>確認した用法：{escape(regimens[key])}</p>",
                     "<h3>普段の注意</h3>", paragraphs(content.routine),
                     "<h3>体調が悪いとき</h3>", paragraphs(content.sick),
                     "<h3>すぐ相談・受診する症状</h3>", paragraphs(content.urgent),
                     "<h3>飲み忘れ・注射忘れ</h3>", paragraphs((content.missed,)),
                     "<h3>医療者が確認した個別指示</h3>",
                     paragraphs((notes.get(key, "").strip() or "個別の休薬・再開条件は未記入です。上記の注意に従い、不明なときは医療機関へ相談してください。",)),
                     f'<p><a href="{escape(guide.source_url, quote=True)}">根拠：PMDAの添付文書・患者向け情報</a></p></section>']
    if any(BY_ID[key].group in DIABETES_GROUPS for key in keys):
        sections.append(f'<p><a href="{SICK_DAY_URL}">糖尿病情報センター：シックデイ</a></p>')
    if any(BY_ID[key].group == "sglt2" for key in keys):
        sections.append(f'<p><a href="{SGLT2_URL}">日本糖尿病学会：SGLT2阻害薬の適正使用</a></p>')
    sections.append("<footer>服薬指導の補助資料です。すべての副作用・相互作用を網羅するものではありません。処方や休薬を自動で決定するものではありません。</footer>")
    return ('<!doctype html><html lang="ja"><meta charset="utf-8"><title>お薬の説明メモ</title>'
            '<style>body{font-family:system-ui,sans-serif;max-width:850px;margin:24px auto;padding:0 20px;line-height:1.7;color:#193b34}'
            'h1{font-size:24px}h2{font-size:20px}h3{font-size:16px;margin-bottom:4px}p{margin:6px 0;white-space:pre-wrap}'
            'aside{border:2px solid #b42318;padding:12px;color:#842318}section{border-top:1px solid #bbb;margin-top:24px;padding-top:8px}'
            'a{overflow-wrap:anywhere}footer{font-size:12px;border-top:1px solid #bbb;margin-top:24px}'
            '@media print{@page{size:A4;margin:16mm}body{margin:0;padding:0;font-size:11pt}h2,h3{break-after:avoid}p{orphans:3;widows:3}}</style>'
            '<body>' + "".join(sections) + '</body></html>')
