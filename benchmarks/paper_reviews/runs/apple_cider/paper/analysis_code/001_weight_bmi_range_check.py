
# Verify the weight-loss and BMI-drop ranges claimed in the Discussion
# against the group means printed in Table 2 (week 0 -> week 12).

weight_w0 = {"G1": 79.0, "G2": 79.3, "G3": 77.2}
weight_w12 = {"G1": 73.9, "G2": 71.9, "G3": 70.2}

bmi_w0 = {"G1": 30.6, "G2": 30.2, "G3": 30.0}
bmi_w12 = {"G1": 28.8, "G2": 27.3, "G3": 27.2}

print("Weight loss (kg), week0 - week12, per group:")
for g in weight_w0:
    print(f"  {g}: {weight_w0[g] - weight_w12[g]:.1f}")

print("\nBMI drop, week0 - week12, per group:")
for g in bmi_w0:
    print(f"  {g}: {bmi_w0[g] - bmi_w12[g]:.1f}")

print("\nDiscussion claims: weight loss 6-8 kg; BMI drop 2.7-3.0 points")
