
import math
# Table 1 per-arm age stats (n=30 each)
groups = {
    "G1": {"mean": 17.2, "sd": 5.2, "n": 30},
    "G2": {"mean": 18.1, "sd": 5.5, "n": 30},
    "G3": {"mean": 17.6, "sd": 5.1, "n": 30},
}
N = sum(g["n"] for g in groups.values())
grand_mean = sum(g["mean"] * g["n"] for g in groups.values()) / N

# Pool sum of squared deviations from grand mean using within-group variance (sample, n-1 denom) plus between-group term
total_ss = 0.0
for g in groups.values():
    within_ss = (g["n"] - 1) * g["sd"] ** 2
    between_ss = g["n"] * (g["mean"] - grand_mean) ** 2
    total_ss += within_ss + between_ss

pooled_var = total_ss / (N - 1)
pooled_sd = math.sqrt(pooled_var)

print("Grand mean (pooled experimental groups age): %.3f" % grand_mean)
print("Pooled SD (combining 3 arms, n=30 each): %.3f" % pooled_sd)
print("Paper prints: 17.6 +/- 5.4 years for experimental groups")
