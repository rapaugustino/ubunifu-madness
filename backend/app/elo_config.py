"""
Canonical Elo configuration constants.

All scripts and services that compute or update Elo ratings MUST import from
here to ensure consistency. These values come from V6 Optuna tuning.
"""

K_FACTOR = 21.8
HOME_ADV = 101.9
SEASON_REGRESSION = 0.89
MEAN_ELO = 1500
