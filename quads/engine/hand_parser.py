

def parse_hole_cards(hole_cards_str):
    # Example input: "Ah,Kd"
    card1, card2 = hole_cards_str.split(",")
    rank_map = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, 'T':10, 'J':11, 'Q':12, 'K':13, 'A':14}
    suit1, suit2 = card1[1], card2[1]
    rank1, rank2 = rank_map[card1[0]], rank_map[card2[0]]
    high_rank, low_rank = max(rank1, rank2), min(rank1, rank2)
    is_pair = int(rank1 == rank2)
    is_suited = int(suit1 == suit2)
    gap = abs(rank1 - rank2)
    is_connector = int(gap == 1)
    # Hand class: e.g. "AKs", "72o"
    hand_class = f"{card1[0]}{card2[0]}{'s' if is_suited else 'o'}" if rank1 >= rank2 else f"{card2[0]}{card1[0]}{'s' if is_suited else 'o'}"
    chen_score = compute_chen_score(rank1, rank2, is_pair, is_suited, gap)
    return {
        "hole_card1": card1,
        "hole_card2": card2,
        "hand_class": hand_class,
        "high_rank": high_rank,
        "low_rank": low_rank,
        "is_pair": is_pair,
        "is_suited": is_suited,
        "gap": gap,
        "chen_score": chen_score,
    }
    
def compute_chen_score(rank1, rank2, is_pair, is_suited, gap):
    # Chen formula simplified
    chen_values = {14:10, 13:8, 12:7, 11:6, 10:5, 9:4.5, 8:4, 7:3.5, 6:3, 5:2.5, 4:2, 3:1.5, 2:1}
    high = max(rank1, rank2)
    low = min(rank1, rank2)
    score = chen_values[high]
    if is_pair:
        score = max(score * 2, 5)
    if is_suited:
        score += 2
    if gap == 0:
        pass
    elif gap == 1:
        score += 1
    elif gap == 2:
        score += 0.5
    else:
        score -= (gap - 2)
    score = max(score, 0.5)
    return round((score * 2) / 2, 1)  # round up to nearest half

