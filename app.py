"""Dealer Pot Trainer - practise awarding main pots, side pots and chops.

Run with:  streamlit run app.py
"""
import random

import pandas as pd
import streamlit as st

import engine

st.set_page_config(page_title="Dealer Pot Trainer", page_icon="🃏", layout="wide")

SUITS = "♣♦♥♠"
TWO_COLOR = ["#111", "#c62828", "#c62828", "#111"]
FOUR_COLOR = ["#1b7f3b", "#1565c0", "#c62828", "#111"]


# ----------------------------------------------------------------- rendering
def card_html(card, four_color):
    color = (FOUR_COLOR if four_color else TWO_COLOR)[card[1]]
    return (
        f'<span style="display:inline-block;background:#fff;color:{color};'
        "border:1px solid #9a9a9a;border-radius:6px;padding:1px 6px;margin:1px 2px;"
        'font:700 1.15rem ui-monospace,Menlo,Consolas,monospace;white-space:nowrap">'
        f"{engine.RANK_CHAR[card[0]]}{SUITS[card[1]]}</span>"
    )


def cards_html(cards, four_color):
    return "".join(card_html(c, four_color) for c in cards)


def seat_label(scn, seat):
    return f"Seat {seat}" + (" (BTN)" if seat == scn.button else "")


def seats_text(seats):
    return ", ".join(f"Seat {s}" for s in seats)


def html_table(headers, rows):
    th = "".join(f'<th style="text-align:left;padding:4px 14px 4px 0">{h}</th>' for h in headers)
    body = "".join(
        "<tr>" + "".join(f'<td style="padding:4px 14px 4px 0">{c}</td>' for c in r) + "</tr>"
        for r in rows
    )
    return (f'<div style="overflow-x:auto"><table style="border-collapse:collapse">'
            f"<tr>{th}</tr>{body}</table></div>")


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Settings")
    game = st.selectbox("Game", list(engine.GAMES))
    st.subheader("Difficulty")
    players_range = st.slider("Players at showdown", 2, 9, (3, 5))
    side_range = st.slider("Side pots", 0, 6, (1, 2),
                           help="Needs at least (side pots + 2) players at showdown; "
                                "the player count is raised or the side pots trimmed to fit.")
    max_folded = st.slider("Max folded players (dead money)", 0, 3, 1)
    chop_pct = st.slider("Chance of a guaranteed tie", 0, 100, 30, step=5, format="%d%%",
                         help="How often a hand is rigged so at least one pot (or half-pot) "
                              "is tied. Natural ties can still happen on other hands.")
    denom = st.select_slider("Smallest chip", [1, 5, 25, 100], value=5,
                             help="All bets are multiples of this, and pots that don't "
                                  "split evenly leave odd chips of this size.")
    show_pots = st.toggle("Show pots pre-built", value=True,
                          help="Off = you only see what each player put in, and must "
                               "work out the pots yourself. You then enter each player's "
                               "total payout.")
    st.subheader("Display")
    four_color = st.toggle("Four-colour deck", value=True)
    deal_clicked = st.button("Deal new hand", width='stretch')

ss = st.session_state
ss.setdefault("stats", dict(hands=0, correct=0, streak=0, best=0))
signature = (game, players_range, side_range, max_folded, chop_pct, show_pots)


def new_hand():
    ss.scn = engine.generate(game, players_range, side_range, max_folded,
                             force_chop=random.random() * 100 < chop_pct)
    ss.hand_no = ss.get("hand_no", 0) + 1
    ss.answer = None
    ss.signature = signature


if deal_clicked or "scn" not in ss or ss.signature != signature:
    new_hand()

scn = ss.scn


def money(units):
    return f"{units * denom:,}"


# ------------------------------------------------------------------- header
st.title("🃏 Dealer Pot Trainer")
stats = ss.stats
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hands", stats["hands"])
c2.metric("Correct", stats["correct"])
c3.metric("Accuracy", f"{100 * stats['correct'] / stats['hands']:.0f}%" if stats["hands"] else "-")
c4.metric("Streak", stats["streak"], help=f"Best: {stats['best']}")

# ----------------------------------------------------------------- the hand
st.subheader(f"Hand #{ss.hand_no} · {scn.game}")
left, right = st.columns([3, 2])

with left:
    board_names = ["Top board", "Bottom board"] if len(scn.boards) == 2 else ["Board"]
    st.markdown(
        html_table([], [[f"<b>{n}</b>", cards_html(b, four_color)]
                        for n, b in zip(board_names, scn.boards)]),
        unsafe_allow_html=True)
    rows = []
    for p in scn.players:
        if p.live:
            cards = cards_html(p.hole, four_color)
            status = "All-in" if p.all_in else "Covers"
        else:
            cards = '<span style="opacity:.55">mucked</span>'
            status = '<span style="opacity:.55">Folded</span>'
        rows.append([f"<b>{seat_label(scn, p.seat)}</b>", cards, money(p.wagered), status])
    st.markdown(html_table(["Player", "Hole cards", "Put in", "Status"], rows),
                unsafe_allow_html=True)

with right:
    if show_pots:
        st.markdown("**Pots**")
        st.markdown(html_table(
            ["Pot", "Amount", "Eligible"],
            [[f"<b>{pot.name}</b>", money(pot.amount), seats_text(pot.eligible)]
             for pot in scn.pots]), unsafe_allow_html=True)
    st.markdown(f"**Total in the middle:** {money(scn.total_pot)}")
    with st.expander("House rules used here"):
        st.markdown(
            "- Each pot is awarded separately, among its eligible players only.\n"
            "- Folded players' chips are dead money in the pots they reached.\n"
            "- Omaha games: exactly two hole cards plus three board cards.\n"
            "- PLO8: low must be 8-or-better; if no eligible player qualifies, "
            "high takes that whole pot.\n"
            "- Hi/lo and double board: each pot is halved. An odd chip goes to "
            "the **high** hand / the **top board**.\n"
            "- Ties split their share evenly. Leftover odd chips go one at a time, "
            "starting with the tied player closest to the **left of the button**.\n"
            f"- The smallest chip is {denom:,}; nothing is broken down further.")

# ------------------------------------------------------------------- answer
live = scn.live
row_labels = [seat_label(scn, p.seat) for p in live]
if show_pots:
    columns = [f"{pot.name} ({money(pot.amount)})" for pot in scn.pots]
    correct = [[pot.payouts.get(p.seat, 0) * denom for pot in scn.pots] for p in live]
else:
    columns = ["Total payout"]
    totals = scn.total_payouts()
    correct = [[totals[p.seat] * denom] for p in live]

st.subheader("Award the chips")
st.caption("Enter how many chips each player receives" +
           (" from each pot." if show_pots else " in total."))
with st.form(f"answer_{ss.hand_no}"):
    blank = pd.DataFrame(0, index=pd.Index(row_labels, name="Player"), columns=columns)
    edited = st.data_editor(
        blank, key=f"editor_{ss.hand_no}_{show_pots}", width='stretch',
        column_config={c: st.column_config.NumberColumn(c, min_value=0, step=denom, format="%d")
                       for c in columns})
    submitted = st.form_submit_button("Check payouts", type="primary",
                                      disabled=ss.answer is not None)

if submitted and ss.answer is None:
    ss.answer = edited.fillna(0).astype(int).values.tolist()
    ok = ss.answer == correct
    stats["hands"] += 1
    stats["correct"] += ok
    stats["streak"] = stats["streak"] + 1 if ok else 0
    stats["best"] = max(stats["best"], stats["streak"])
    st.rerun()

# ------------------------------------------------------------------ results
if ss.answer is not None:
    if ss.answer == correct:
        st.success("Correct - every chip is in the right place.")
    else:
        st.error("Not quite. Cells marked ❌ show your entry → the correct amount.")
    rows = []
    for label, mine, right_row in zip(row_labels, ss.answer, correct):
        cells = [f"✅ {r:,}" if m == r else f"❌ {m:,} → <b>{r:,}</b>"
                 for m, r in zip(mine, right_row)]
        rows.append([f"<b>{label}</b>", *cells])
    st.markdown(html_table(["Player", *columns], rows), unsafe_allow_html=True)

    with st.expander("Explanation", expanded=True):
        for side in scn.sides:
            st.markdown(f"**{side.name} hands**")
            ranked = sorted(live, key=lambda p: (side.results[p.seat].score is None,
                                                 tuple(-x for x in side.results[p.seat].score or ())))
            st.markdown(html_table(
                ["Player", "Best five", "Hand"],
                [[seat_label(scn, p.seat),
                  cards_html(side.results[p.seat].cards, four_color)
                  if side.results[p.seat].cards else "-",
                  side.results[p.seat].desc] for p in ranked]), unsafe_allow_html=True)
        st.markdown("**Pot by pot**")
        for pot in scn.pots:
            lines = [f"**{pot.name} - {money(pot.amount)}** · eligible: {seats_text(pot.eligible)}"]
            if pot.note:
                lines.append(f"- _{pot.note}_")
            for por in pot.portions:
                side = next(s for s in scn.sides if s.name == por.side)
                hand = side.results[por.winners[0]].desc
                prefix = f"{por.side} ({money(por.amount)})" if len(pot.portions) > 1 else por.side
                if len(por.winners) == 1:
                    lines.append(f"- {prefix}: Seat {por.winners[0]} wins with {hand}.")
                else:
                    pay = ", ".join(f"Seat {s} {money(v)}" for s, v in por.payouts.items())
                    odd = ""
                    if por.odd_chips:
                        odd = (f" {por.odd_chips} odd chip{'s' if por.odd_chips > 1 else ''} "
                               f"to {seats_text(por.winners[:por.odd_chips])} "
                               "(first left of the button).")
                    lines.append(f"- {prefix}: {len(por.winners)}-way tie with {hand} → {pay}.{odd}")
            st.markdown("\n".join(lines))

    if st.button("Next hand ▶", type="primary"):
        new_hand()
        st.rerun()
