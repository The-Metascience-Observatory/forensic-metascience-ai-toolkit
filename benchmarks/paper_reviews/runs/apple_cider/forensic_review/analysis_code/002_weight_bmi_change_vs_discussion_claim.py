
# Table 2 printed means, Week 0 vs Week 12, for the three ACV arms
weight_w0 = {"G1": 79.0, "G2": 79.3, "G3": 77.2}
weight_w12 = {"G1": 73.9, "G2": 71.9, "G3": 70.2}
bmi_w0 = {"G1": 30.6, "G2": 30.2, "G3": 30.0}
bmi_w12 = {"G1": 28.8, "G2": 27.3, "G3": 27.2}

weight_change = {g: round(weight_w0[g] - weight_w12[g], 1) for g in weight_w0}
bmi_change = {g: round(bmi_w0[g] - bmi_w12[g], 1) for g in bmi_w0}

print("Weight loss per arm (kg):", weight_change)
print("Weight loss range (kg): %.1f to %.1f" % (min(weight_change.values()), max(weight_change.values())))
print("BMI reduction per arm (points):", bmi_change)
print("BMI reduction range (points): %.1f to %.1f" % (min(bmi_change.values()), max(bmi_change.values())))
print()
print("Discussion claims: weight loss 6-8 kg; BMI reduction 2.7-3.0 points")
