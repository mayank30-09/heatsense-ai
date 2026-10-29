path_rules = 'gis/interventions/rules.py'
with open(path_rules, 'r', encoding='utf-8') as f:
    r_content = f.read()

# Update cool roof skin cooling delta in rules.py
old_cool_roof_param = '''        "cooling_skin_delta": RuleParameter(
            name="cooling_skin_delta",
            value=-2.2,
            unit="°C",
            param_type=RuleParameterType.SOURCED,
            source_citation="Santamouris (2017) Solar Energy 144: 730-749",
            notes="Local surface skin temperature drop under high SRI coatings (>104)",
        ),'''

new_cool_roof_param = '''        "cooling_skin_delta": RuleParameter(
            name="cooling_skin_delta",
            value=-8.59,
            unit="°C",
            param_type=RuleParameterType.SOURCED,
            source_citation="Linearized Albedo Energy Balance: Delta T_skin = (-0.45 * 870) / 45.6 = -8.59°C (Santamouris 2014; ASTM D7897 aged coating). Cell-diluted: -1.29°C to -2.20°C. 2m air temp is unmodeled.",
            notes="Surface skin temperature reduction on treated high-reflectance coating. Ambient 2m air temperature is unmodeled.",
        ),'''

if old_cool_roof_param in r_content:
    r_content = r_content.replace(old_cool_roof_param, new_cool_roof_param)
elif old_cool_roof_param.replace('\n', '\r\n') in r_content:
    r_content = r_content.replace(old_cool_roof_param.replace('\n', '\r\n'), new_cool_roof_param.replace('\n', '\r\n'))

with open(path_rules, 'w', encoding='utf-8') as f:
    f.write(r_content)
print('Updated rules.py')

# Update recommendations.py
path_rec = 'gis/interventions/recommendations.py'
with open(path_rec, 'r', encoding='utf-8') as f:
    rec_content = f.read()

old_cost_rollup = '''        cost_rollup = {
            "total_capital_spend_inr": round(tot_capital, 2),
            "total_capital_spend_formatted": format_inr(tot_capital),
            "total_direct_cost_inr": round(tot_direct, 2),
            "total_annual_maintenance_inr": round(tot_maint, 2),
            "total_treated_area_m2": round(tot_area_m2, 1),
            "total_treated_area_ha": round(tot_area_m2 / 10000.0, 3),
            "eligible_options_count": len(eligible_recs),
            "rejected_options_count": len(rec_list) - len(eligible_recs),
        }'''

new_cost_rollup = '''        phase1_fraction = 0.10
        phase1_capital = round(tot_capital * phase1_fraction, 2)
        phase1_area_m2 = round(tot_area_m2 * phase1_fraction, 1)

        cost_rollup = {
            "phase1_headline": {
                "title": "Phase 1 Municipal Pilot Implementation (Recommended)",
                "fraction": "10% of eligible spatial footprint",
                "capital_spend_inr": phase1_capital,
                "capital_spend_formatted": format_inr(phase1_capital),
                "treated_area_m2": phase1_area_m2,
                "treated_area_ha": round(phase1_area_m2 / 10000.0, 3),
                "description": "Recommended initial municipal pilot tranche for field validation before full deployment.",
            },
            "full_potential_upper_bound": {
                "title": "Theoretical 100% Spatial Build-Out (Upper Bound)",
                "fraction": "100% theoretical envelope",
                "capital_spend_inr": round(tot_capital, 2),
                "capital_spend_formatted": format_inr(tot_capital),
                "treated_area_m2": round(tot_area_m2, 1),
                "treated_area_ha": round(tot_area_m2 / 10000.0, 3),
                "description": "Theoretical maximum ceiling assuming complete structural eligibility and full tenure clearance across all parcels.",
            },
            "total_capital_spend_inr": round(tot_capital, 2),
            "total_capital_spend_formatted": format_inr(tot_capital),
            "total_direct_cost_inr": round(tot_direct, 2),
            "total_annual_maintenance_inr": round(tot_maint, 2),
            "total_treated_area_m2": round(tot_area_m2, 1),
            "total_treated_area_ha": round(tot_area_m2 / 10000.0, 3),
            "eligible_options_count": len(eligible_recs),
            "rejected_options_count": len(rec_list) - len(eligible_recs),
        }'''

if old_cost_rollup in rec_content:
    rec_content = rec_content.replace(old_cost_rollup, new_cost_rollup)
elif old_cost_rollup.replace('\n', '\r\n') in rec_content:
    rec_content = rec_content.replace(old_cost_rollup.replace('\n', '\r\n'), new_cost_rollup.replace('\n', '\r\n'))

with open(path_rec, 'w', encoding='utf-8') as f:
    f.write(rec_content)
print('Updated recommendations.py')
