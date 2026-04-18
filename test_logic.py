from logic import simplify_debts

# Cyclical test: A owes B $50, B owes C $50, C owes A $50.
# The net balances for all should be 0.
balances = {
    "A": 0,
    "B": 0,
    "C": 0
}
print(simplify_debts(balances))

# Another test: A paid 150 for ABC. B paid 50 for BC.
# A: paid 150, share 50 -> net +100
# B: paid 50, share 50 (from A) + 25 (from B, since B paid 50 for BC) -> net -25
# C: paid 0, share 50 (from A) + 25 (from B) -> net -75
balances2 = {
    "A": 100,
    "B": -25,
    "C": -75
}
print(simplify_debts(balances2))
