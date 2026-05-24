"""
大富豪 pick()係数最適化スクリプト
=====================================
進化戦略（OpenAI-ES）でpick()内の係数ベクトルθを最適化する。

使い方:
    python train.py

完了後、出力されたW_OPT辞書をindex.htmlのpick()関数に貼り付ける。

係数ベクトルθ（18次元）の対応:
    0  sz_bonus          枚数消化ボーナス              (元: 12)
    1  block_bonus       ブロック消去ボーナス            (元: 35)
    2  eff_delta_w       効率デルタ重み                 (元: 20)
    3  abs_eff_w         絶対効率重み                   (元: 15)
    4  loose_penalty     バラ牌増加ペナルティ            (元: 35)
    5  late_nr_w         終盤/danger時ランク重み         (元: 35)
    6  late_bonus        終盤/danger時定数ボーナス       (元: 10)
    7  normal_weak_w     通常場なし 弱出し促進           (元: 18)
    8  normal_high_pen   通常場なし 高カード抑制          (元: 20)
    9  combo_low_w       通常場なし 低コンボ促進 (sz>=2, nr<0.65)  (元: 10)
   10  combo_high_w      通常場なし 高コンボ促進 (sz>=2, nr>=0.65) (元: 3)
   11  mid_nr_w          通常場なし 中盤ランク補正 (tot<=10)        (元: 8)
   12  rd1 / rd2 / rd3   場あり 差分1/2/3 ボーナス      (元: 28,20,12)
   13  rd1_bonus         差分1ボーナス                  (元: 28)
   14  rd2_bonus         差分2ボーナス                  (元: 20)
   15  rd_large_pen      差分8以上ペナルティ             (元: 18)
   16  danger_nr_w       danger/urgency時ランク重み      (元: 45)
   17  normal_nr_pen     通常場あり ランクペナルティ      (元: 8)
"""

import random
import numpy as np
from copy import deepcopy

# ── 定数 ──────────────────────────────────────────────────────
NUMS = list(range(3, 17))          # 3〜15 + 16(JKR)
NR   = {n: i for i, n in enumerate(NUMS)}          # 通常ランク
RR   = {n: i for i, n in enumerate([16] + list(reversed(NUMS[:-1])))}  # 革命ランク

def rk(n, rev):
    if n == 16:
        return len(NUMS) - 1
    return RR[n] if rev else NR[n]

MX = len(NUMS) - 1  # 13

# ── 初期係数（現行index.htmlの値） ────────────────────────────
W_INIT = np.array([
     5.612,  # 0  sz_bonus          （games=400 best=1.845）
    36.334,  # 1  block_bonus
    20.194,  # 2  eff_delta_w
    14.441,  # 3  abs_eff_w
    36.312,  # 4  loose_penalty
    34.250,  # 5  late_nr_w
    10.606,  # 6  late_bonus
    22.094,  # 7  normal_weak_w
    18.913,  # 8  normal_high_pen
     3.235,  # 9  combo_low_w
     1.068,  # 10 combo_high_w
     4.270,  # 11 mid_nr_w
    29.053,  # 12 rd1_bonus
    19.932,  # 13 rd2_bonus
    11.938,  # 14 rd3_bonus
    18.019,  # 15 rd_large_pen
    44.485,  # 16 danger_nr_w
     7.080,  # 17 normal_nr_pen
], dtype=float)

# ── ユーティリティ ────────────────────────────────────────────
def hand_sum(hand):
    return sum(hand.values())

def hand_efficiency(hand):
    tot   = hand_sum(hand)
    turns = sum(1 for n in NUMS if hand.get(n, 0) > 0)
    return tot / turns if turns > 0 else 0.0

def loose_ratio(hand):
    loose = total = 0
    for n in NUMS:
        c = hand.get(n, 0)
        if not c:
            continue
        total += c
        if c == 1:
            loose += 1
    return loose / total if total > 0 else 0.0

def eff_after_play(hand, num, sz, j_used):
    after = dict(hand)
    if num == 16:
        after[16] = after.get(16, 0) - sz
    else:
        after[num]  = after.get(num, 0)  - (sz - j_used)
        after[16]   = after.get(16, 0)   - j_used
    return hand_efficiency(after)

def cp_ok(n, sz, field, rev):
    if field is None:
        return True
    return sz == field[1] and rk(n, rev) > rk(field[0], rev)

def post_rev_str(hand, exclude_num, use_cnt, use_joker, rev):
    s = c = 0
    for n in NUMS:
        cnt = hand.get(n, 0)
        if n == exclude_num:
            cnt = max(0, cnt - use_cnt)
        if n == 16:
            cnt = max(0, cnt - use_joker)
        if not cnt:
            continue
        s += rk(n, not rev) / MX * cnt
        c += cnt
    return s / c if c > 0 else 0.0

# ── pick()のPython実装（係数ベクトルW使用） ───────────────────
def pick(hand, field, rev, opp, r_rev, W):
    tot      = hand_sum(hand)
    opp_min  = min(opp) if opp else 99
    danger   = opp_min <= 3
    urgency  = opp_min <= 5
    joker    = hand.get(16, 0)
    late     = tot <= 6
    ultra    = tot <= 3

    cur_eff   = hand_efficiency(hand)
    cur_loose = loose_ratio(hand)

    has_rev4  = r_rev and any(n != 16 and hand.get(n, 0) >= 4 for n in NUMS)
    has_rev3j = r_rev and joker >= 1 and any(n != 16 and hand.get(n, 0) >= 3 for n in NUMS)
    has_rev   = has_rev4 or has_rev3j

    cands = []

    for num in NUMS:
        if num == 16:
            continue
        cnt = hand.get(num, 0)
        if not cnt:
            continue

        sizes = []
        if field is not None:
            sz   = field[1]
            need = max(0, sz - cnt)
            if need <= joker:
                sizes.append((sz, need))
        else:
            for sz in range(1, cnt + 1):
                sizes.append((sz, 0))
            if r_rev and 2 <= cnt <= 3 and joker >= (4 - cnt):
                sizes.append((4, 4 - cnt))

        for sz, j_used in sizes:
            if not cp_ok(num, sz, field, rev):
                continue
            r  = rk(num, rev)
            nr = r / MX
            sc = 0.0

            # ① 枚数消化
            sc += sz * W[0]
            if cnt == sz and j_used == 0:
                sc += W[1]

            # ② 効率
            a_eff     = eff_after_play(hand, num, sz, j_used)
            eff_delta = a_eff - cur_eff
            sc += eff_delta * W[2]
            sc += a_eff     * W[3]

            # ③ バラ牌ペナルティ
            after = dict(hand)
            if num == 16:
                after[16] -= sz
            else:
                after[num]  -= sz - j_used
                after[16]   -= j_used
            a_loose     = loose_ratio(after)
            loose_delta = a_loose - cur_loose
            sc -= loose_delta * W[4]

            # ④ 場なし / 場あり
            if field is None:
                if tot <= 5 or danger:
                    sc += nr * W[5] + W[6]
                else:
                    sc += (1 - nr) * W[7]
                    if nr > 0.77:
                        sc -= W[8]
                    if sz >= 2 and nr < 0.65:
                        sc += sz * W[9]
                    if sz >= 2 and nr >= 0.65:
                        sc += sz * W[10]
                    if tot <= 10:
                        sc += nr * W[11]
            else:
                rd = rk(num, rev) - rk(field[0], rev)
                if   rd == 1: sc += W[12]
                elif rd == 2: sc += W[13]
                elif rd == 3: sc += W[14]
                elif rd >= 8: sc -= W[15]
                if danger or urgency:
                    sc += nr * W[16]
                else:
                    sc -= nr * W[17]

            # ⑤ 革命
            if sz == 4 and r_rev:
                ps = post_rev_str(hand, num, cnt - j_used, j_used, rev)
                sc += (ps - 0.5) * 60  # 革命スコアは固定（学習対象外）
                if j_used >= 2: sc -= 45
                elif j_used == 1: sc -= 12
                if danger: sc += 20

            # ⑥ コンボ崩しペナルティ（固定）
            if cnt >= 2 and sz == 1 and cnt <= 3 and j_used == 0: sc -= 32
            if cnt == 3 and sz == 2 and j_used == 0: sc -= 14
            if cnt == 4 and 1 <= sz <= 3 and j_used == 0: sc -= 22
            if num == 15 and late and sz < cnt: sc -= 2.0

            cands.append((sc, num, sz, j_used))

    # JKR単体
    if joker > 0 and field is not None and field[1] == 1:
        nr = rk(16, rev) / MX
        sc = nr * 50
        if ultra:           sc += 45
        elif tot <= 2:      sc += 45
        elif danger:        sc += 55
        elif late:          sc -= 10
        else:               sc -= 25
        if has_rev3j:       sc -= 20
        cands.append((sc, 16, 1, 0))
    elif joker > 0 and field is None and ultra and tot <= 2:
        cands.append((rk(16, rev) / MX * 45 + 35, 16, 1, 0))

    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    return cands[0][1], cands[0][2], cands[0][3]

# ── 1試合シミュレーション ─────────────────────────────────────
def sim_once(p_hand, np_, r8, r_rev, W):
    """W: 学習対象の係数ベクトル（pid=0のみ使用）"""
    full = [n for n in range(3, 16) for _ in range(4)] + [16, 16]
    un   = list(full)
    for n in NUMS:
        c = p_hand.get(n, 0)
        for _ in range(c):
            un.remove(n)
    random.shuffle(un)

    others = np_ - 1
    per_p  = len(un) // others
    players = [dict(p_hand)]
    for i in range(others):
        h     = {n: 0 for n in NUMS}
        start = i * per_p
        end   = len(un) if i == others - 1 else start + per_p
        for c in un[start:end]:
            h[c] += 1
        players.append(h)

    active = list(range(np_))
    rnk    = []
    field  = None
    rev    = False
    cp     = 0
    turn   = 0
    cur    = random.randint(0, np_ - 1)

    while len(active) > 1 and turn < 1500:
        turn += 1
        pid  = active[cur]
        h    = players[pid]
        opp  = [hand_sum(players[j]) for j in active if j != pid]

        # pid=0のみ学習係数W、他はW_INIT（固定ベースライン）
        w_use = W if pid == 0 else W_INIT
        play  = pick(h, field, rev, opp, r_rev, w_use)

        if play is None:
            cp += 1
            if cp >= len(active) - 1 and field:
                field = None
                cp    = 0
            cur = (cur + 1) % len(active)
            continue

        cp = 0
        n2, sz, j_used = play
        if n2 == 16:
            h[16] -= sz
        else:
            h[n2]  -= sz - j_used
            h[16]  -= j_used
        field = [n2, sz]

        if sz == 4 and r_rev:
            rev = not rev
        if r8 and n2 == 8:
            field = None
            cp    = 0
            if hand_sum(h) == 0:
                rnk.append(pid)
                active.remove(pid)
            if active:
                cur = random.randint(0, len(active) - 1)
            continue
        if hand_sum(h) == 0:
            rnk.append(pid)
            active.remove(pid)
            field = None
            cp    = 0
            if active:
                cur = random.randint(0, len(active) - 1)
            continue
        cur = (cur + 1) % len(active)

    for p in active:
        if p not in rnk:
            rnk.append(p)

    return rnk.index(0) + 1  # 1始まり着順

# ── 評価関数 ──────────────────────────────────────────────────
def evaluate(W, n_games=400, np_=3, r8=True, r_rev=True):
    """
    W の期待着順を返す（低いほど良い）。
    多様な手札で試合し、平均着順を計算。
    """
    total_rank = 0
    full_deck  = [n for n in range(3, 16) for _ in range(4)] + [16, 16]
    cards_per  = len(full_deck) // np_

    for _ in range(n_games):
        deck = list(full_deck)
        random.shuffle(deck)
        hand = {n: 0 for n in NUMS}
        for c in deck[:cards_per]:
            hand[c] += 1
        total_rank += sim_once(hand, np_, r8, r_rev, W)

    return total_rank / n_games

# ── 並列評価 ──────────────────────────────────────────────────
def _eval_worker(args):
    """multiprocessing用ワーカー（トップレベル関数である必要がある）"""
    W_list, n_games, np_, r8, r_rev = args
    W = np.array(W_list)
    return evaluate(W, n_games, np_, r8, r_rev)

def evaluate_parallel(W_candidates, n_games, np_, r8, r_rev, n_workers):
    """pop個の候補を並列評価して報酬リストを返す"""
    from multiprocessing import Pool, freeze_support
    freeze_support()  # Windows exe化対応（通常実行でも無害）
    args = [(W.tolist(), n_games, np_, r8, r_rev) for W in W_candidates]
    with Pool(processes=n_workers) as pool:
        rewards = pool.map(_eval_worker, args)
    return np.array(rewards)

# ── OpenAI-ES（進化戦略） ─────────────────────────────────────
def train(
    n_iter    = 200,    # 世代数
    pop_size  = 20,     # 1世代あたりのサンプル数
    sigma     = 3.0,    # 探索ノイズ
    lr        = 0.15,   # 学習率
    eval_games= 400,    # 評価ゲーム数
    np_       = 3,
    r8        = True,
    r_rev     = True,
    sigma_decay = 0.995,
    n_workers = None,   # 並列数（Noneで自動=CPUコア数）
):
    import os
    if n_workers is None:
        n_workers = os.cpu_count() or 1

    W    = W_INIT.copy()
    best_score = evaluate(W, eval_games, np_, r8, r_rev)
    best_W     = W.copy()

    print(f"初期スコア（平均着順）: {best_score:.4f}")
    print(f"係数次元数: {len(W)}, 世代数: {n_iter}, pop: {pop_size}, workers: {n_workers}\n")

    for gen in range(n_iter):
        noise = np.random.randn(pop_size, len(W))
        W_candidates = [np.clip(W + sigma * noise[i], 0.5, 120.0) for i in range(pop_size)]

        # pop個の候補を並列評価
        rewards = evaluate_parallel(W_candidates, eval_games, np_, r8, r_rev, n_workers)

        # 正規化（低着順=良い → 符号反転して最大化問題に変換）
        r_neg  = -rewards
        r_norm = (r_neg - r_neg.mean()) / (r_neg.std() + 1e-8)

        # 勾配推定・更新
        grad = (noise.T @ r_norm) / pop_size
        W    = W + lr * grad / sigma
        W    = np.clip(W, 0.5, 120.0)
        sigma *= sigma_decay

        # 評価
        score = evaluate(W, eval_games, np_, r8, r_rev)
        if score < best_score:
            best_score = score
            best_W     = W.copy()

        if gen % 10 == 0 or gen == n_iter - 1:
            print(f"Gen {gen+1:3d}/{n_iter}  avg_rank={score:.4f}  best={best_score:.4f}  σ={sigma:.3f}")

    return best_W, best_score

# ── 結果出力 ──────────────────────────────────────────────────
def print_result(W_opt, best_score):
    labels = [
        "sz_bonus", "block_bonus", "eff_delta_w", "abs_eff_w",
        "loose_penalty", "late_nr_w", "late_bonus",
        "normal_weak_w", "normal_high_pen",
        "combo_low_w", "combo_high_w", "mid_nr_w",
        "rd1_bonus", "rd2_bonus", "rd3_bonus",
        "rd_large_pen", "danger_nr_w", "normal_nr_pen",
    ]
    print("\n" + "="*60)
    print(f"最適化完了  最良平均着順: {best_score:.4f}")
    print("="*60)
    print("\n【係数比較】")
    print(f"{'係数名':<20} {'元の値':>8} {'最適値':>8} {'変化':>8}")
    print("-"*50)
    for i, (lbl, w0, wopt) in enumerate(zip(labels, W_INIT, W_opt)):
        diff = wopt - w0
        mark = " ←" if abs(diff) > 3 else ""
        print(f"{lbl:<20} {w0:>8.2f} {wopt:>8.2f} {diff:>+8.2f}{mark}")

    print("\n【index.html pick()への反映方法】")
    print("以下の値をpick()内の該当箇所に貼り替える:\n")
    mapping = [
        ("sz * 12",          f"sz * {W_opt[0]:.1f}"),
        ("sc += 35;",        f"sc += {W_opt[1]:.1f};  // block_bonus"),
        ("effDelta * 20",    f"effDelta * {W_opt[2]:.1f}"),
        ("afterEff * 15",    f"afterEff * {W_opt[3]:.1f}"),
        ("looseDelta * 35",  f"looseDelta * {W_opt[4]:.1f}"),
        ("nr*35+10",         f"nr*{W_opt[5]:.1f}+{W_opt[6]:.1f}"),
        ("(1-nr)*18",        f"(1-nr)*{W_opt[7]:.1f}"),
        ("nr>0.77) sc -= 20",f"nr>0.77) sc -= {W_opt[8]:.1f}"),
        ("sz*10",            f"sz*{W_opt[9]:.1f}"),
        ("sz*3",             f"sz*{W_opt[10]:.1f}"),
        ("nr*8",             f"nr*{W_opt[11]:.1f}"),
        ("sc+=28",           f"sc+={W_opt[12]:.1f}"),
        ("sc+=20",           f"sc+={W_opt[13]:.1f}"),
        ("sc+=12",           f"sc+={W_opt[14]:.1f}"),
        ("sc-=18",           f"sc-={W_opt[15]:.1f}"),
        ("nr*45",            f"nr*{W_opt[16]:.1f}"),
        ("sc-=nr*8",         f"sc-=nr*{W_opt[17]:.1f}"),
    ]
    for old, new in mapping:
        print(f"  {old:<28} →  {new}")

    print("\n【Wベクトル（numpy形式）】")
    print("W_OPT =", repr(W_opt.tolist()))

# ── 結果保存 ──────────────────────────────────────────────────
RESULTS_FILE = "results.jsonl"

def save_result(W_opt, best_score, n_iter, pop_size, eval_games, interrupted=False):
    """実行結果を results.jsonl に1行追記する"""
    import json, datetime, os

    record = {
        "timestamp"  : datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "interrupted": interrupted,
        "config": {
            "iter" : n_iter,
            "pop"  : pop_size,
            "games": eval_games,
        },
        "best_score" : round(best_score, 6),
        "W_init"     : W_INIT.tolist(),
        "W_opt"      : W_opt.tolist(),
        "W_diff"     : (W_opt - W_INIT).tolist(),
    }

    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 過去のbestと比較して改善したか表示
    all_scores = []
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                all_scores.append(json.loads(line)["best_score"])
            except Exception:
                pass

    overall_best = min(all_scores)
    is_new_best  = best_score <= overall_best
    print(f"\n結果を {RESULTS_FILE} に保存しました。")
    print(f"  今回: {best_score:.4f}  {'★ 過去最良を更新' if is_new_best else f'過去最良: {overall_best:.4f}'}")
    print(f"  累計実行回数: {len(all_scores)}")

def load_best():
    """results.jsonl から最良スコアのW_optを読み込む"""
    import json, os
    if not os.path.exists(RESULTS_FILE):
        return None, None
    best_score = float("inf")
    best_W     = None
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                if r["best_score"] < best_score:
                    best_score = r["best_score"]
                    best_W     = np.array(r["W_opt"])
            except Exception:
                pass
    return best_W, best_score

# ── evaluateHand()係数補正（sim_logベース） ──────────────────
# sim_log.jsonの各レコード: {features, rates, evalScore, evalRaw}
# features.hand: {3:0, 4:1, ...} の手札構成
# rates: {1: 40.7, 2: 35.0, 3: 24.3} の実際の勝率
# evalScore: evaluateHand()が出したスコア（0-100）
#
# 目標：evalScore と rates[1]（1位率）の相関を最大化するよう
#       evaluateHand()内の係数EW（8次元）を調整する

# evaluateHand係数の初期値（index.htmlの現行値と同期）
EW_LABELS = [
    "card_pen_w",    # 枚数超過ペナルティ係数（元:3）
    "joker_base",    # JKR基礎値（元:12）
    "joker_rev_b",   # JKR革命補完ボーナス（元:8）
    "joker_pair_b",  # JKRペア補完ボーナス（元:4）
    "joker_2x_b",    # JKR2枚持ちボーナス（元:8）
    "two_w",         # 2の係数（元:12）
    "ace_w",         # Aの係数（元:5）
    "combo_pair_w",  # ペアのコンボ係数（元:4）
    "combo_tri_w",   # トリプルのコンボ係数（元:5）
    "weak_iso_pen",  # 弱バラ牌ペナルティ（元:4）
    "eight_w",       # 8切り係数（元:5）
    "no_strong_pen", # 強カードなしペナルティ（元:10）
]
EW_INIT = np.array([3., 12., 8., 4., 8., 12., 5., 4., 5., 4., 5., 10.])

def eval_hand_score(hand, r8, r_rev, EW):
    """EWベクトルを使ってevaluateHandのスコアを計算（train.py内部用）"""
    total  = sum(hand.get(n,0) for n in NUMS)
    joker  = hand.get(16, 0)
    two    = hand.get(15, 0)
    ace    = hand.get(14, 0)
    fours3j = [n for n in NUMS if n!=16 and hand.get(n,0)==3] if r_rev else []
    fours4  = [n for n in NUMS if n!=16 and hand.get(n,0)>=4] if r_rev else []
    pairs   = sum(1 for n in NUMS if n!=16 and hand.get(n,0)>=2)
    triples = sum(1 for n in NUMS if n!=16 and hand.get(n,0)>=3)
    weakIso = sum(1 for n in NUMS if n!=16 and n<11 and n!=8 and hand.get(n,0)==1)
    eights  = hand.get(8, 0)

    s = 0.
    # 枚数ペナルティ
    s -= max(0, (total - 13)) * EW[0]
    # JKR
    if joker > 0:
        jv = joker * EW[1]
        if r_rev and fours3j: jv += EW[2]
        else:
            weak_singles = sum(1 for n in NUMS if n!=16 and hand.get(n,0)==1 and n<14)
            if weak_singles > 0: jv += EW[3]
        if joker == 2: jv += EW[4]
        s += jv
    # 2・A
    s += two  * EW[5]
    s += ace  * EW[6]
    # 革命スコアは固定（EW対象外）
    if r_rev:
        for r in fours4:
            rs = _revScore(hand, r, 0, joker, two, ace)
            s += rs['net']
        if joker >= 1 and fours3j:
            candidates = [_revScore(hand, r, 1, joker, two, ace) for r in fours3j]
            best = max(candidates, key=lambda x: x['net'])
            s += best['net']
    # コンボ
    s += pairs   * EW[7]
    s += triples * EW[8]
    # 弱バラ牌
    s -= weakIso * EW[9]
    # 8切り
    if r8: s += eights * EW[10]
    # 強カードなし
    if joker == 0 and two == 0 and ace == 0: s -= EW[11]

    score = max(0., min(100., (s + 30.) * 100. / 130.))
    return score

def _revScore(hand, revNum, jUsed, joker, two, ace):
    """革命スコア計算（Python版）"""
    pScore = pCount = 0
    for n in NUMS:
        cnt = hand.get(n, 0)
        if n == revNum: cnt = max(0, cnt - (4 - jUsed))
        if n == 16:     cnt = max(0, cnt - jUsed)
        if not cnt: continue
        pScore += rk(n, True) / MX * cnt
        pCount += cnt
    postStr = pScore / pCount if pCount > 0 else 0.
    strongPreRev = two + ace
    otherCards = sum(hand.get(n,0) for n in NUMS if n != revNum and n != 16)
    waste = max(0, strongPreRev - otherCards // 2)
    mult  = 0.5 + postStr
    base  = 20 if jUsed == 0 else 14
    return {'net': round(base * mult) - waste * 8, 'postStr': postStr, 'waste': waste}

def calibrate_eval(sim_log_path, n_iter=100, lr=0.05):
    """
    sim_log.jsonを読んでevaluateHand()係数EWを補正する。
    目標：evalScore（0-100）と実際の1位率の相関を最大化
    """
    import json
    with open(sim_log_path, encoding='utf-8') as f:
        records = json.load(f)

    if not records:
        print("sim_log.jsonが空です")
        return EW_INIT.copy()

    print(f"sim_log読み込み: {len(records)}件")

    # 手札と1位率のペアを抽出
    hands  = [r['features']['hand'] for r in records]
    rates1 = [r['rates'].get('1', r['rates'].get(1, 0)) / 100. for r in records]
    config = records[0].get('config', {})
    r8     = config.get('r8', True)
    r_rev  = config.get('rRev', True)

    EW = EW_INIT.copy()
    best_corr = _pearson_corr(
        [eval_hand_score(h, r8, r_rev, EW) for h in hands], rates1
    )
    best_EW = EW.copy()
    print(f"初期相関係数: {best_corr:.4f}")

    # 簡易ES（相関最大化）
    sigma = 1.5
    for gen in range(n_iter):
        noise   = np.random.randn(10, len(EW))
        scores_corr = []
        for i in range(10):
            EW_try = np.clip(EW + sigma * noise[i], 0.1, 50.)
            preds  = [eval_hand_score(h, r8, r_rev, EW_try) for h in hands]
            corr   = _pearson_corr(preds, rates1)
            scores_corr.append(corr)
        scores_arr = np.array(scores_corr)
        s_norm = (scores_arr - scores_arr.mean()) / (scores_arr.std() + 1e-8)
        grad   = (noise.T @ s_norm) / 10
        EW     = np.clip(EW + lr * grad, 0.1, 50.)
        sigma  *= 0.99

        corr = _pearson_corr([eval_hand_score(h, r8, r_rev, EW) for h in hands], rates1)
        if corr > best_corr:
            best_corr = corr
            best_EW   = EW.copy()

        if gen % 20 == 0 or gen == n_iter - 1:
            print(f"Gen {gen+1:3d}/{n_iter}  corr={corr:.4f}  best={best_corr:.4f}")

    print(f"\n最終相関係数: {best_corr:.4f}")
    print("\n【evaluateHand係数の補正結果】")
    print(f"{'係数名':<18} {'元の値':>8} {'補正値':>8} {'変化':>8}")
    print("-"*46)
    for lbl, w0, wopt in zip(EW_LABELS, EW_INIT, best_EW):
        diff = wopt - w0
        mark = " ←" if abs(diff) > 1 else ""
        print(f"{lbl:<18} {w0:>8.2f} {wopt:>8.2f} {diff:>+8.2f}{mark}")

    return best_EW

def _pearson_corr(x, y):
    """ピアソン相関係数"""
    x, y = np.array(x), np.array(y)
    if x.std() < 1e-8 or y.std() < 1e-8: return 0.
    return float(np.corrcoef(x, y)[0, 1])

# ── エントリポイント ──────────────────────────────────────────
if __name__ == "__main__":
    import sys, os
    from multiprocessing import freeze_support
    freeze_support()  # Windows必須

    # 引数で設定変更可能
    # 例: python train.py --iter 300 --pop 30 --games 600
    # 例: python train.py --resume  （過去最良の係数から再開）
    # 例: python train.py --sim-log sim_log.json  （手札評価係数を補正）
    n_iter    = 200
    pop_size  = 20
    eval_games= 400
    resume    = False
    sim_log   = None

    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--iter"    and i+1 < len(args): n_iter     = int(args[i+1])
        if a == "--pop"     and i+1 < len(args): pop_size   = int(args[i+1])
        if a == "--games"   and i+1 < len(args): eval_games = int(args[i+1])
        if a == "--resume":                       resume     = True
        if a == "--sim-log" and i+1 < len(args): sim_log    = args[i+1]

    # --sim-log モード：evaluateHand係数のみ補正して終了
    if sim_log:
        print("大富豪 手札評価係数補正モード")
        print(f"sim_log: {sim_log}\n")
        best_EW = calibrate_eval(sim_log)
        print("\n【index.html evaluateHand()への反映方法】")
        ew_mapping = [
            ("(total - 13) * 3",  f"(total - 13) * {best_EW[0]:.1f}"),
            ("joker * 12",        f"joker * {best_EW[1]:.1f}"),
            ("jv += 8;  // rev",  f"jv += {best_EW[2]:.1f};  // rev_bonus"),
            ("jv += 4;  // pair", f"jv += {best_EW[3]:.1f};  // pair_bonus"),
            ("jv += 8;  // 2x",   f"jv += {best_EW[4]:.1f};  // 2x_bonus"),
            ("two * 12",          f"two * {best_EW[5]:.1f}"),
            ("ace * 5",           f"ace * {best_EW[6]:.1f}"),
            ("pairs * 4",         f"pairs * {best_EW[7]:.1f}"),
            ("triples * 5",       f"triples * {best_EW[8]:.1f}"),
            ("weakIso * 4",       f"weakIso * {best_EW[9]:.1f}"),
            ("hand[8] * 5",       f"hand[8] * {best_EW[10]:.1f}"),
            ("s -= 10;  // nostr",f"s -= {best_EW[11]:.1f};  // no_strong"),
        ]
        for old, new in ew_mapping:
            print(f"  {old:<30} →  {new}")
        sys.exit(0)

    print("大富豪 pick()係数最適化")
    print(f"設定: iter={n_iter}, pop={pop_size}, eval_games={eval_games}")

    # --resume: 過去最良の係数をW_INITとして引き継ぐ
    if resume:
        prev_W, prev_score = load_best()
        if prev_W is not None:
            W_INIT[:] = prev_W
            print(f"過去最良から再開: score={prev_score:.4f}")
        else:
            print("results.jsonlが見つからないため初期値から開始")

    print("（Ctrl+C で中断可能。その時点のbestを保存する）\n")

    interrupted = False
    try:
        W_opt, best_score = train(
            n_iter    = n_iter,
            pop_size  = pop_size,
            eval_games= eval_games,
        )
    except KeyboardInterrupt:
        print("\n\n中断されました。直前のbest係数を保存します。")
        W_opt      = W_INIT.copy()
        best_score = float("inf")
        interrupted = True

    print_result(W_opt, best_score)
    save_result(W_opt, best_score, n_iter, pop_size, eval_games, interrupted)
