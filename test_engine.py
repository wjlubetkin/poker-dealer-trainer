"""Sanity tests for the engine. Run: python test_engine.py (or pytest)."""
import random

import engine as e

C = lambda s: tuple(("23456789TJQKA".index(x[0]) + 2, "cdhs".index(x[1])) for x in s.split())


def test_eval_order():
    hands = ["Ah Kh Qh Jh Th", "9c 9d 9h 9s 2c", "8c 8d 8h 2s 2c", "Ah 9h 7h 3h 2h",
             "5c 4d 3h 2s Ac", "7c 7d 7h Ks 2c", "Kc Kd 3h 3s 2c", "Ac Ad 9h 3s 2c",
             "Ac Qd 9h 3s 2c"]
    scores = [e.eval5(C(h)) for h in hands]
    assert scores == sorted(scores, reverse=True)
    assert e.eval5(C("6c 5d 4h 3s 2c")) > e.eval5(C("5c 4d 3h 2s Ac"))


def test_omaha_must_use_two():
    # Four hearts on board, one heart in hand: no flush in Omaha.
    score, _ = e.best_high(C("Ah Kc Qd Js"), C("2h 5h 9h Th 3c"), True)
    assert score[0] != 5
    score, _ = e.best_high(C("Ah Kc"), C("2h 5h 9h Th 3c"), False)
    assert score[0] == 5


def test_low():
    score, _ = e.best_low(C("Ah 2c Kd Ks"), C("3h 4h 5d Kc Qc"))
    assert e.describe_low(score) == "5-4-3-2-A low"
    assert e.best_low(C("Ah 2c Kd Ks"), C("3h 4h 9d Kc Qc"))[0] is None
    # Counterfeited: board A-2 pairs the hand; must still play two from hand.
    score, _ = e.best_low(C("Ah 2c 9d Ks"), C("As 2h 5d Kc Qc"))
    assert score is None


def test_pots_with_dead_money():
    players = [e.Player(1, True, 50, True), e.Player(2, True, 120, True),
               e.Player(3, True, 300), e.Player(4, True, 300), e.Player(5, False, 80)]
    pots = e.build_pots(players)
    assert [(p.amount, p.eligible) for p in pots] == [
        (250, [1, 2, 3, 4]), (240, [2, 3, 4]), (360, [3, 4])]


def test_odd_chip_and_low_side_pot():
    # Seat 2 (short) has the only low; side pot has no low -> high scoops it.
    players = [e.Player(2, True, 5, True, C("Ac 2d 7h 7s")),
               e.Player(5, True, 20, False, C("Kc Kd Qh Js")),
               e.Player(7, True, 20, False, C("Ks Kh Qd Jc"))]
    boards = [C("3c 4d 8h Td 9s")]
    scn = e.Scenario("PLO8", 5, players, boards, e.evaluate_sides("PLO8", players, boards),
                     e.build_pots(players))
    e.award(scn)
    main, side = scn.pots
    assert main.amount == 15 and side.amount == 30
    # Main: high 8 chips split 5/7 (Q-high straight chop), low 7 to seat 2.
    assert main.payouts == {2: 7, 5: 4, 7: 4}
    assert side.payouts == {5: 15, 7: 15} and side.note
    # Odd chip: 3-chip portion between seats 5 (button) and 7 -> seat 7 gets it.
    side.amount = 31
    e.award(scn)
    assert side.payouts == {5: 15, 7: 16}


def test_random_invariants():
    rng = random.Random(1)
    for game in e.GAMES:
        for i in range(150):
            scn = e.generate(game, (2, 9), (0, 6), 3, force_chop=i % 3 == 0, rng=rng)
            assert sum(p.wagered for p in scn.players) == scn.total_pot
            assert sum(scn.total_payouts().values()) == scn.total_pot
            cards = [c for p in scn.live for c in p.hole] + [c for b in scn.boards for c in b]
            assert len(cards) == len(set(cards))
            for pot in scn.pots:
                assert len(pot.eligible) >= 2
                assert sum(pot.payouts.values()) == pot.amount


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
