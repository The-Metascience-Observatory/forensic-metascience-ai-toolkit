cere_mg_per_ml = 215.2  # manufacturer: 215.2 mg/mL concentrate
dose_mg_per_kg = 5.0
vol_ml_per_kg_if_5mg = dose_mg_per_kg / cere_mg_per_ml
print('ml_per_kg_if_5mg_per_kg', round(vol_ml_per_kg_if_5mg, 5))
print('ul_per_kg_if_5mg_per_kg', round(vol_ml_per_kg_if_5mg*1000, 2))

for wt_g in (220, 250, 280):
    wt_kg = wt_g/1000
    print(f'wt_g={wt_g}')
    print('  volume_ml_if_5mg_per_kg', round(vol_ml_per_kg_if_5mg*wt_kg, 4))
    print('  ml_per_kg_if_25ml', round(25/wt_kg, 2))
    print('  mg_if_25ml_of_cere', round(25*cere_mg_per_ml, 1))
    print('  mg_per_kg_if_25ml', round(25*cere_mg_per_ml/wt_kg, 1))
    print('  volume_ml_if_5ml_per_kg', round(5*wt_kg, 3))
    print('  volume_ml_if_2p5ml_per_kg', round(2.5*wt_kg, 3))

print('vecuronium_table_mg_per_kg', 0.04, 0.05)
print('vecuronium_fig5_ug_per_kg', 80)
print('vecuronium_fig5_as_mg_per_kg', 80/1000)
print('kcl_1mg_vs_1meq_mg', 1, 74.55)  # KCl MW 74.55; 1 mEq = 1 mmol = 74.55 mg
print('avma_kcl_mg_per_kg_low', 75)
print('avma_kcl_mg_per_kg_high', 150)
print('fold_1mg_vs_75mg', 75/1)
print('scandicain_2pct_mg_per_ml', 20)
print('paper_mepivacaine_mg_per_ml', 2)
print('fold_20_vs_2', 20/2)
