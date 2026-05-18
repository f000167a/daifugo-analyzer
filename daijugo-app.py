import streamlit as st
from engine import run_montecarlo_analysis

st.set_page_config(page_title="大富豪 勝率シミュレータ", layout="centered")

st.title("🃏 大富豪 勝率シミュレータ")
st.caption("モンテカルロ法による初期手札のガチ分析アルゴリズム")

# ==========================================
# サイドバー：設定エリア
# ==========================================
st.sidebar.header("⚙️ 基本設定")
num_players = st.sidebar.number_input(
    "プレイヤー人数", min_value=3, max_value=5, value=3, step=1
)

my_position = st.sidebar.selectbox(
    "あなたの現在の役職", ["平民", "富豪", "貧民"]
)

st.sidebar.header("📜 ルール設定")
rule_8giri = st.sidebar.checkbox("8切りあり", value=True)
st.sidebar.checkbox("スペード3返しなし", value=True, disabled=True)
st.sidebar.checkbox("同マーク順列（階段）なし", value=True, disabled=True)

trials = st.sidebar.slider(
    "シミュレーション試行回数",
    min_value=100,
    max_value=1000,
    value=300,
    step=100,
)

# ==========================================
# メイン画面：手札入力エリア
# ==========================================
st.subheader("📥 あなたの初期手札を入力してください")
st.write("各数字の所持枚数（0〜4枚）、Joker（0〜2枚）を選択してください。")

# 見栄えを良くするため、数字の表示名マッピング
display_names = {
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    10: "10",
    11: "J (11)",
    12: "Q (12)",
    13: "K (13)",
    14: "A (14)",
    15: "2 (15)",
    16: "Joker",
}

player_hand = {}

# グリッド配置でUIをスッキリさせる（4列構成）
cols = st.columns(4)
for idx, (num, label) in enumerate(display_names.items()):
    with cols[idx % 4]:
        max_val = 2 if num == 16 else 4
        player_hand[num] = st.number_input(
            label, min_value=0, max_value=max_val, value=0, step=1, key=f"n_{num}"
        )

total_cards = sum(player_hand.values())
st.metric(label="📊 現在の合計手札枚数", value=f"{total_cards} 枚")

# ==========================================
# シミュレーション実行・結果表示
# ==========================================
if st.button("🚀 勝率シミュレーションを開始", type="primary"):
    if total_cards == 0:
        st.error("手札が空っぽです。カードを入力してください。")
    elif total_cards > (54 // num_players) + 5:
        st.warning(
            "手札の枚数が人数に対して多すぎます。正しい枚数か確認してください。"
        )
    else:
        with st.spinner("AIが仮想対戦を高速ぶん回し中..."):
            rates = run_montecarlo_analysis(
                player_hand, num_players, rule_8giri, trials
            )

        st.success("分析が完了しました！")

        # 結果表示エリア
        st.subheader("📊 順位確率結果")

        # 役職文字の定義
        rank_labels = {1: "1位 (富豪)", 2: "2位 (平民)", 3: "3位 (貧民)"}
        if num_players == 4:
            rank_labels = {
                1: "1位 (大富豪)",
                2: "2位 (富豪)",
                3: "3位 (貧民)",
                4: "4位 (大貧民)",
            }
        elif num_players == 5:
            rank_labels = {
                1: "1位 (大富豪)",
                2: "2位 (富豪)",
                3: "3位 (平民)",
                4: "4位 (貧民)",
                5: "5位 (大貧民)",
            }

        # プログレスバー風に確率を表示
        for rank, rate in rates.items():
            st.write(f"**{rank_labels[rank]}** : {rate}%")
            st.progress(int(rate))

        # 戦略アドバイス
        st.markdown("---")
        st.subheader("💡 あなたの役職に応じた生存戦略")

        p_1st = rates[1]
        p_2nd = rates.get(2, 0)
        p_3rd = rates.get(3, 0)

        if my_position == "富豪":
            st.info(f"**👑 富豪キープ率（都落ち回避率）: {p_1st}%**")
            if p_1st < 35.0:
                st.error(
                    "🚨 **危険状態：** 都落ちリスクが極めて高い手札です。温存は死を意味します。序盤から強札や8切りで主導権を奪い、最短上がりを目指してください。"
                )
            else:
                st.success(
                    "✅ **安定状態：** 順当に立ち回れば富豪をキープできるポテンシャルがあります。他プレイヤーの警戒を誘わないよう、中位手から丁寧に通していきましょう。"
                )

        elif my_position == "平民":
            survival_rate = round(p_1st + p_2nd, 1)
            st.info(f"**🛡️ 平民以上キープ率（現状維持）: {survival_rate}%**")
            if survival_rate < 55.0:
                st.error(
                    "🚨 **防衛警告：** 貧民以下に転落するリスクがあります。1位を狙いに行く色気は捨て、他人の大物手を削る『壁』になりつつ、手札のペアを確実に処理して2位に滑り込んでください。"
                )
            else:
                st.success(
                    "✅ **現状維持圏内：** 非常にバランスが良く、2位に残りやすい手札です。富豪に勝負を挑ませ、疲弊した隙に安全に上がりを確定させましょう。"
                )

        elif my_position == "貧民":
            # 3人、4人、5人いずれも上位2枠が脱出ライン
            escape_rate = round(p_1st + p_2nd, 1)
            st.info(f"**🚀 貧民脱出率（上位昇格率）: {escape_rate}%**")
            if escape_rate < 35.0:
                st.warning(
                    "☠️ **苦戦必至：** 普通に打っても這い上がるのは困難です。4枚組がある場合は、タイミングを見計らった『革命』による盤面破壊ワンチャンを狙いましょう。"
                )
            else:
                st.success(
                    "🔥 **下克上の好機：** 貧民にしてはかなり強い手札を掴んでいます。相手の手札交換で渡したカード以上のリターンを、中位コンボで回収して一気に平民以上へ這い上がれます。"
                )