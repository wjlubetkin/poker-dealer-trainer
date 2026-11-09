# Dealer Pot Trainer

A Streamlit app for practising pot awards: main pots, side pots, dead money,
chops, odd chips, hi/lo splits and double boards.

Games: Hold'em, PLO, PLO5, PLO8, PLO Double Board.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Share it

Push this folder to a GitHub repository, then at share.streamlit.io choose
"Create app", pick the repo and set the main file to `app.py`. Anyone with the
link can use it; each visitor gets their own hands and score.

## Files

- `app.py` - the UI
- `engine.py` - hand evaluation, pot building, awards, scenario generation
- `test_engine.py` - `python test_engine.py`

## House rules assumed

- Odd chip in a hi/lo pot goes to high; in a double-board pot, to the top board.
- Odd chips among tied hands go to the first tied player left of the button.
- No qualifying low among a pot's eligible players: high takes that whole pot.
