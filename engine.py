"""Game logic for the dealer pot-assignment trainer.

No Streamlit imports here, so this module can be unit-tested on its own.
All chip amounts are held in *units* of the smallest chip in play; the UI
multiplies by the chip denomination for display.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import combinations

MAX_SEATS = 9

GAMES = {
    "Hold'em": dict(hole=2, omaha=False, boards=1, hilo=False),
    "PLO": dict(hole=4, omaha=True, boards=1, hilo=False),
    "PLO5": dict(hole=5, omaha=True, boards=1, hilo=False),
    "PLO8": dict(hole=4, omaha=True, boards=1, hilo=True),
    "PLO Double Board": dict(hole=4, omaha=True, boards=2, hilo=False),
}

RANK_CHAR = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T", 1: "A"}
RANK_CHAR.update({r: str(r) for r in range(2, 10)})
RANK_NAME = {
    14: "Ace", 13: "King", 12: "Queen", 11: "Jack", 10: "Ten", 9: "Nine",
    8: "Eight", 7: "Seven", 6: "Six", 5: "Five", 4: "Four", 3: "Three",
    2: "Two", 1: "Ace",
}


def plural(rank: int) -> str:
    name = RANK_NAME[rank]
    return name + ("es" if name == "Six" else "s")


# --------------------------------------------------------------------------
# Hand evaluation.  A card is (rank 2..14, suit 0..3).
# --------------------------------------------------------------------------
_SHAPES = {(4, 1): 7, (3, 2): 6, (3, 1, 1): 3, (2, 2, 1): 2, (2, 1, 1, 1): 1}


def eval5(cards) -> tuple:
    """Score a 5-card high hand. Bigger tuple = better hand."""
    ranks = sorted((c[0] for c in cards), reverse=True)
    if len(set(ranks)) == 5:
        s = cards[0][1]
        flush = all(c[1] == s for c in cards)
        if ranks[0] - ranks[4] == 4:
            straight = True
        elif ranks == [14, 5, 4, 3, 2]:
            straight = True
            ranks = [5, 4, 3, 2, 1]
        else:
            straight = False
        cat = 8 if (straight and flush) else 5 if flush else 4 if straight else 0
        return (cat, *ranks)
    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    groups = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    return (_SHAPES[tuple(c for _, c in groups)], *(r for r, _ in groups))


def _candidates(hole, board, omaha):
    if omaha:  # exactly two from the hand, three from the board
        for h in combinations(hole, 2):
            for b in combinations(board, 3):
                yield h + b
    else:
        yield from combinations(tuple(hole) + tuple(board), 5)


def best_high(hole, board, omaha):
    best, best_cards = None, None
    for five in _candidates(hole, board, omaha):
        score = eval5(five)
        if best is None or score > best:
            best, best_cards = score, five
    return best, best_cards


def best_low(hole, board):
    """8-or-better low, Omaha rules. Returns (score, cards) or (None, None).

    Score is the negated ranks (ace = 1) sorted high to low, so that a
    bigger tuple is a better low, the same direction as high scores.
    """
    lo_hole = [c for c in hole if c[0] <= 8 or c[0] == 14]
    lo_board = [c for c in board if c[0] <= 8 or c[0] == 14]
    best, best_cards = None, None
    for h in combinations(lo_hole, 2):
        for b in combinations(lo_board, 3):
            ranks = sorted((1 if c[0] == 14 else c[0] for c in h + b), reverse=True)
            if len(set(ranks)) < 5:
                continue
            score = tuple(-r for r in ranks)
            if best is None or score > best:
                best, best_cards = score, h + b
    return best, best_cards


def describe_high(score) -> str:
    cat, t = score[0], score[1:]
    if cat == 8:
        return "Royal flush" if t[0] == 14 else f"Straight flush, {RANK_NAME[t[0]]}-high"
    if cat == 7:
        return f"Quad {plural(t[0])}, {RANK_NAME[t[1]]} kicker"
    if cat == 6:
        return f"Full house, {plural(t[0])} full of {plural(t[1])}"
    if cat == 5:
        return "Flush, " + "-".join(RANK_CHAR[r] for r in t)
    if cat == 4:
        return f"Straight, {RANK_NAME[t[0]]}-high"
    if cat == 3:
        return f"Three {plural(t[0])}, {RANK_CHAR[t[1]]}-{RANK_CHAR[t[2]]} kickers"
    if cat == 2:
        return f"Two pair, {plural(t[0])} and {plural(t[1])}, {RANK_NAME[t[2]]} kicker"
    if cat == 1:
        return f"Pair of {plural(t[0])}, " + "-".join(RANK_CHAR[r] for r in t[1:]) + " kickers"
    return "High card, " + "-".join(RANK_CHAR[r] for r in t)


def describe_low(score) -> str:
    return "-".join(RANK_CHAR[-r] for r in score) + " low"


# --------------------------------------------------------------------------
# Scenario model
# --------------------------------------------------------------------------
@dataclass
class Player:
    seat: int
    live: bool
    wagered: int  # units
    all_in: bool = False
    hole: tuple = ()


@dataclass
class HandResult:
    score: tuple | None
    cards: tuple | None
    desc: str


@dataclass
class Side:
    """One half of the pot: 'High', 'Low', 'Top board' or 'Bottom board'."""
    name: str
    board_index: int
    results: dict  # seat -> HandResult


@dataclass
class Portion:
    side: str
    amount: int
    winners: list  # seats, in odd-chip order
    payouts: dict  # seat -> units
    odd_chips: int


@dataclass
class Pot:
    name: str
    amount: int
    eligible: list  # seats
    portions: list = field(default_factory=list)
    payouts: dict = field(default_factory=dict)  # seat -> units
    note: str = ""


@dataclass
class Scenario:
    game: str
    button: int
    players: list
    boards: list
    sides: list
    pots: list

    @property
    def live(self):
        return [p for p in self.players if p.live]

    @property
    def total_pot(self):
        return sum(p.amount for p in self.pots)

    def odd_chip_rank(self, seat: int) -> int:
        """0 = first seat left of the button; the button itself is last."""
        return (seat - self.button - 1) % MAX_SEATS

    def total_payouts(self) -> dict:
        out = {p.seat: 0 for p in self.live}
        for pot in self.pots:
            for seat, amt in pot.payouts.items():
                out[seat] += amt
        return out

    def has_chop(self) -> bool:
        return any(len(por.winners) > 1 for pot in self.pots for por in pot.portions)


def build_pots(players) -> list:
    """Main pot + side pots from each player's total wager.

    Folded players' chips are dead money: they fill each layer up to the
    amount they put in but are never eligible to win.
    """
    levels = sorted({p.wagered for p in players if p.live})
    pots, prev = [], 0
    for i, level in enumerate(levels):
        amount = sum(min(p.wagered, level) - min(p.wagered, prev) for p in players)
        eligible = sorted(p.seat for p in players if p.live and p.wagered >= level)
        pots.append(Pot("Main pot" if i == 0 else f"Side pot {i}", amount, eligible))
        prev = level
    return pots


def evaluate_sides(game: str, players, boards) -> list:
    cfg = GAMES[game]
    live = [p for p in players if p.live]
    sides = []
    for bi, board in enumerate(boards):
        res = {}
        for p in live:
            score, cards = best_high(p.hole, board, cfg["omaha"])
            res[p.seat] = HandResult(score, cards, describe_high(score))
        name = ("Top board", "Bottom board")[bi] if cfg["boards"] == 2 else "High"
        sides.append(Side(name, bi, res))
    if cfg["hilo"]:
        res = {}
        for p in live:
            score, cards = best_low(p.hole, boards[0])
            res[p.seat] = HandResult(score, cards, describe_low(score) if score else "No qualifying low")
        sides.append(Side("Low", 0, res))
    return sides


def award(scn: Scenario) -> None:
    """Fill in pot.portions / pot.payouts for every pot.

    House rules:
      * Each pot is awarded on its own, among its eligible players only.
      * Two-way pots (hi/lo, double board) are halved; an odd chip goes to
        the high hand / the top board.
      * If no eligible player has a qualifying low, high takes the whole pot.
      * Tied hands split their portion evenly; leftover odd chips go one at
        a time starting with the first tied player left of the button.
    """
    for pot in scn.pots:
        active = [s for s in scn.sides
                  if any(s.results[seat].score is not None for seat in pot.eligible)]
        if len(active) == 2:
            amounts = [pot.amount - pot.amount // 2, pot.amount // 2]
        else:
            amounts = [pot.amount]
            if len(scn.sides) == 2:
                pot.note = "No qualifying low among eligible players - high takes the whole pot."
        pot.portions, pot.payouts = [], {seat: 0 for seat in pot.eligible}
        for side, amt in zip(active, amounts):
            scores = {seat: side.results[seat].score for seat in pot.eligible
                      if side.results[seat].score is not None}
            top = max(scores.values())
            winners = sorted((s for s, sc in scores.items() if sc == top), key=scn.odd_chip_rank)
            share, rem = divmod(amt, len(winners))
            pay = {seat: share + (1 if i < rem else 0) for i, seat in enumerate(winners)}
            for seat, v in pay.items():
                pot.payouts[seat] += v
            pot.portions.append(Portion(side.name, amt, winners, pay, rem))


# --------------------------------------------------------------------------
# Scenario generation
# --------------------------------------------------------------------------
def _deal(game, n_live, n_folded, n_side, rng, twin) -> Scenario:
    cfg = GAMES[game]
    seats = sorted(rng.sample(range(1, MAX_SEATS + 1), n_live + n_folded))
    live_seats = sorted(rng.sample(seats, n_live))
    button = rng.choice(seats)

    # Betting: n_side + 1 distinct all-in levels; at least two players at the
    # top level so the final bet is called (no uncalled bet to return).
    levels = sorted(rng.sample(range(4, 301), n_side + 1))
    assign = levels + [levels[-1]] + [rng.choice(levels) for _ in range(n_live - len(levels) - 1)]
    rng.shuffle(assign)
    top = levels[-1]

    deck = [(r, s) for r in range(2, 15) for s in range(4)]
    rng.shuffle(deck)
    players = []
    for seat in seats:
        if seat in live_seats:
            w = assign.pop()
            hole = tuple(deck.pop() for _ in range(cfg["hole"]))
            players.append(Player(seat, True, w, all_in=w < top, hole=hole))
        else:
            players.append(Player(seat, False, rng.randint(1, max(1, min(top, 60)))))

    if twin:
        # Nudge towards a chop: give one player the same ranks as another.
        a, b = rng.sample([p for p in players if p.live], 2)
        deck.extend(b.hole)
        new = []
        for card in a.hole:
            same = [c for c in deck if c[0] == card[0]]
            pick = rng.choice(same) if same else rng.choice(deck)
            deck.remove(pick)
            new.append(pick)
        b.hole = tuple(new)
        rng.shuffle(deck)

    for p in players:
        if p.live:
            p.hole = tuple(sorted(p.hole, reverse=True))
    boards = [tuple(deck.pop() for _ in range(5)) for _ in range(cfg["boards"])]
    scn = Scenario(game, button, players, boards, evaluate_sides(game, players, boards),
                   build_pots(players))
    award(scn)
    return scn


def generate(game: str, players_range=(2, 6), side_range=(0, 2), max_folded=1,
             force_chop=False, rng: random.Random | None = None) -> Scenario:
    rng = rng or random.Random()
    p_lo, p_hi = players_range
    s_lo, s_hi = side_range
    scn = None
    for _ in range(150 if force_chop else 1):
        # Need n_live >= side pots + 2, so bump the player count if required.
        n_live = rng.randint(max(p_lo, min(p_hi, s_lo + 2)), p_hi)
        cap = max(0, n_live - 2)
        n_side = rng.randint(min(s_lo, cap), min(s_hi, cap))
        n_folded = rng.randint(0, min(max_folded, MAX_SEATS - n_live))
        scn = _deal(game, n_live, n_folded, n_side, rng, twin=force_chop)
        if not force_chop or scn.has_chop():
            break
    return scn
