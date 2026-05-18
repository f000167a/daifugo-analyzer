import random
from copy import deepcopy

NORMAL_ORDER = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]  # 16はJoker
REV_ORDER = [16] + list(reversed(NORMAL_ORDER[:-1]))


def get_order(revolution=False):
    return REV_ORDER if revolution else NORMAL_ORDER


def stronger(a, b, revolution=False):
    order = get_order(revolution)
    return order.index(a) > order.index(b)


def get_groups(hand):
    groups = []
    for num, count in hand.items():
        for size in range(1, count + 1):
            groups.append((num, size))
    return groups


def can_play(group, field, revolution=False):
    if field is None:
        return True
    num, size = group
    field_num, field_size = field

    if size != field_size:
        return False
    return stronger(num, field_num, revolution)


def is_control_card(num, revolution=False):
    if num == 16:
        return True
    if not revolution:
        return num >= 14
    return num <= 4


def choose_play(hand, field, revolution, opponent_counts):
    groups = get_groups(hand)
    candidates = []
    danger = min(opponent_counts) <= 2 if opponent_counts else False
    total_cards = sum(hand.values())

    for g in groups:
        if not can_play(g, field, revolution):
            continue

        num, size = g
        score = 0

        score += size * 25
        remain = hand[num] - size
        if remain == 0:
            score += 20

        if total_cards <= 5:
            if is_control_card(num, revolution):
                score += 50

        if danger:
            if is_control_card(num, revolution):
                score += 80
            else:
                score -= 10
        else:
            if is_control_card(num, revolution):
                score -= 20

        if size == 4:
            if not revolution:
                if num <= 6:
                    score += 60
            else:
                if num >= 12:
                    score += 60
            if danger:
                score += 40

        if field is not None:
            field_num, field_size = field
            diff = abs(num - field_num)
            if diff <= 2:
                score += 15
            if diff >= 7:
                score -= 20

        original_count = hand[num]
        if original_count == 2 and size == 1:
            score -= 25
        if original_count == 3 and size < 3:
            score -= 30

        candidates.append((score, g))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def simulate_game_pure_montecarlo(player_hand, num_players=3, rule_8giri=True):
    # 1. デッキ全体の作成
    full_deck = []
    for n in range(3, 16):
        full_deck.extend([n] * 4)
    full_deck.extend([16] * 2)  # Joker 2枚

    # 2. 自分の手札を差し引く
    unseen_cards = full_deck.copy()
    for num, count in player_hand.items():
        for _ in range(count):
            if num in unseen_cards:
                unseen_cards.remove(num)

    # 3. 他のプレイヤーに均等に分配
    random.shuffle(unseen_cards)
    total_my_cards = sum(player_hand.values())
    cards_per_opponent = (54 - total_my_cards) // (num_players - 1)

    players = [deepcopy(player_hand)]
    for i in range(num_players - 1):
        opp_hand = {n: 0 for n in NORMAL_ORDER}
        start_idx = i * cards_per_opponent
        end_idx = start_idx + cards_per_opponent
        for card in unseen_cards[start_idx:end_idx]:
            opp_hand[card] += 1
        players.append(opp_hand)

    # 4. ゲームループ
    ranking = []
    field = None
    revolution = False
    current = 0
    passes = 0
    turn = 0

    while len(ranking) < num_players:
        hand = players[current]

        if sum(hand.values()) == 0:
            current = (current + 1) % num_players
            continue

        opponent_counts = [
            sum(players[i].values()) for i in range(num_players) if i != current
        ]

        play = choose_play(hand, field, revolution, opponent_counts)

        next_turn_same_player = False

        if play is None:
            passes += 1
            if passes >= (num_players - 1):
                field = None
                passes = 0
        else:
            passes = 0
            num, size = play
            hand[num] -= size
            field = play

            if size == 4:
                revolution = not revolution

            # 【追加】8切りルールの適用
            if rule_8giri and num == 8:
                field = None
                passes = 0
                if sum(hand.values()) > 0:
                    next_turn_same_player = True  # 上がっていなければ自分の手番から再開

            if sum(hand.values()) == 0:
                ranking.append(current)
                field = None

        if not next_turn_same_player:
            current = (current + 1) % num_players

        turn += 1
        if turn >= 1000:
            break

    return ranking


def run_montecarlo_analysis(
    player_hand, num_players=3, rule_8giri=True, trials=300
):
    result = {i + 1: 0 for i in range(num_players)}

    for _ in range(trials):
        ranking = simulate_game_pure_montecarlo(
            player_hand, num_players, rule_8giri
        )
        if 0 in ranking:
            rank = ranking.index(0) + 1
            result[rank] += 1
        else:
            result[num_players] += 1

    rates = {}
    for rank, count in result.items():
        rates[rank] = round(count / trials * 100, 1)
    return rates