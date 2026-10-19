
from scipy import stats

groups = {
 "G1": {"weight": (79.0, 27.1), "height": (157.4, 20.1)},
 "G2": {"weight": (79.3, 28.5), "height": (158.6, 22.2)},
 "G3": {"weight": (77.2, 27.2), "height": (157.1, 20.8)},
 "G4": {"weight": (79.1, 28.6), "height": (156.9, 21.4)},
}

for g, d in groups.items():
    for var, (m, sd) in d.items():
        z0 = (0 - m) / sd
        p_below0 = stats.norm.cdf(z0)
        cv = sd / m
        print(f"{g} {var}: mean={m}, sd={sd}, CV={cv:.2%}, P(X<0)={p_below0:.4%}, z_to_0={z0:.2f}")
