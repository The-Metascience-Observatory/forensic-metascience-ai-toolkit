
alpha = 0.05
m_table2 = 36
m_table3 = 21
m_total = m_table2 + m_table3
# Family-wise error rate under a (conservative, independence) assumption -- pure combinatorics,
# not derived from any individual p-value (all of which are printed only as "p<0.05" thresholds).
fwer_table2 = 1 - (1 - alpha) ** m_table2
fwer_table3 = 1 - (1 - alpha) ** m_table3
fwer_total = 1 - (1 - alpha) ** m_total
bonf_alpha_table2 = alpha / m_table2
bonf_alpha_table3 = alpha / m_table3
bonf_alpha_total = alpha / m_total
print("m_table2 (anthropometric vs-baseline tests) =", m_table2)
print("m_table3 (biochemical vs-baseline tests) =", m_table3)
print("m_total =", m_total)
print("FWER (independence-assumed) table2 = %.4f" % fwer_table2)
print("FWER (independence-assumed) table3 = %.4f" % fwer_table3)
print("FWER (independence-assumed) total = %.4f" % fwer_total)
print("Bonferroni-corrected alpha table2 = %.5f" % bonf_alpha_table2)
print("Bonferroni-corrected alpha table3 = %.5f" % bonf_alpha_table3)
print("Bonferroni-corrected alpha total = %.6f" % bonf_alpha_total)
