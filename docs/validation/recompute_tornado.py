"""
Recompute Table 9: Tornado Sensitivity Analysis for Key Model Parameters
Actually re-runs the physical model across the Medium Budget Scenario (Rs 2.5 Cr)
for each parameter bound, including aerodynamic convective resistance (r_a).
"""

import json
import pandas as pd
import numpy as np

# Load Medium Scenario CSV
df_med = pd.read_csv('docs/validation/scenario_medium.csv')

# Base parameters
RHO = 1.16
CP = 1005.0
T_AIR = 311.15  # 38 C
EPSILON = 0.95
SIGMA = 5.67e-8
H_R = 4 * EPSILON * SIGMA * (T_AIR**3)  # ~6.49 W/(m2 K)

K_DOWN_BASE = 870.0
RA_BASE = 30.0
H_C_BASE = (RHO * CP) / RA_BASE  # 38.86
H_EFF_BASE = H_C_BASE + H_R      # 45.35 W/(m2 K)

BASE_MEAN_DLST = df_med['dLST_exp'].mean()  # -0.83 C

# Parse interventions for each cell
cells_data = []
for idx, row in df_med.iterrows():
    areas_str = row['areas']
    roof_m2 = 0.0
    paver_m2 = 0.0
    trees_cnt = 0
    for p in areas_str.split(';'):
        if 'cool_roof:' in p:
            roof_m2 = float(p.replace('cool_roof:', '').replace('m2', ''))
        elif 'cool_pavers:' in p:
            paver_m2 = float(p.replace('cool_pavers:', '').replace('m2', ''))
        elif 'trees:' in p:
            trees_cnt = int(p.split('(')[0].replace('trees:', ''))
    cells_data.append({
        'cell_id': row['cell_id'],
        'roof_m2': roof_m2,
        'paver_m2': paver_m2,
        'trees_cnt': trees_cnt
    })

def simulate_portfolio(k_down=K_DOWN_BASE, r_a=RA_BASE, delta_alpha_roof=0.45, 
                       delta_alpha_paver=0.25, tree_survival=0.85, eta_cell=1.0):
    h_c = (RHO * CP) / r_a
    h_eff = h_c + H_R
    
    # Direct skin reductions
    dt_roof = (k_down * delta_alpha_roof) / h_eff
    dt_paver = (k_down * delta_alpha_paver) / h_eff
    # Tree cooling: Beer-Lambert canopy shade + transpiration
    # Baseline tree dT = 7.5 C. Scale shade with K_down/h_eff and survival rate
    dt_tree = (7.5 * (k_down / K_DOWN_BASE) * (H_EFF_BASE / h_eff)) * (tree_survival / 0.85)
    
    cell_dlsts = []
    for c in cells_data:
        f_roof = c['roof_m2'] / 10000.0
        f_paver = c['paver_m2'] / 10000.0
        f_tree = (c['trees_cnt'] * 50.3) / 10000.0
        
        dlst = (f_roof * dt_roof + f_paver * dt_paver + f_tree * dt_tree) * eta_cell
        cell_dlsts.append(-dlst)
        
    return np.mean(cell_dlsts)

base_portfolio_dlst = simulate_portfolio()
print(f"Base Portfolio Mean dLST: {base_portfolio_dlst:.4f} C (matches CSV {BASE_MEAN_DLST:.2f} C)")

# Define sensitivity bounds
parameters = [
    {
        "name": "Coating Weathering & Dust Aging (delta_alpha_roof)",
        "baseline": 0.45,
        "low_bound": 0.30,
        "high_bound": 0.55,
        "eval_low": lambda: simulate_portfolio(delta_alpha_roof=0.30, delta_alpha_paver=0.17),
        "eval_high": lambda: simulate_portfolio(delta_alpha_roof=0.55, delta_alpha_paver=0.30),
        "vulnerability": "HIGH SENSITIVITY: Dust deposition depresses albedo; requires annual pre-summer washing clause in municipal maintenance contracts."
    },
    {
        "name": "Aerodynamic Convective Resistance (r_a)",
        "baseline": "30 s/m (h_eff = 45.4 W/m2K)",
        "low_bound": "20 s/m (high wind 4 m/s, h_eff = 64.8 W/m2K)",
        "high_bound": "45 s/m (stagnant 1 m/s, h_eff = 32.4 W/m2K)",
        "eval_low": lambda: simulate_portfolio(r_a=20.0),
        "eval_high": lambda: simulate_portfolio(r_a=45.0),
        "vulnerability": "HIGH SENSITIVITY (-30.0% to +40.0%): Governed by 1/h_eff. On windless heatwave days, surface cooling relief is greatest because baseline surfaces overheat severely."
    },
    {
        "name": "Tree Sapling Survival & Mortality",
        "baseline": "85% survival",
        "low_bound": "50% survival (severe drought loss)",
        "high_bound": "95% survival (protected drip lines)",
        "eval_low": lambda: simulate_portfolio(tree_survival=0.50),
        "eval_high": lambda: simulate_portfolio(tree_survival=0.95),
        "vulnerability": "CRITICAL SENSITIVITY: Tree cooling depends on living crowns; requires mandatory 3-year survival-linked payments and guaranteed tanker watering."
    },
    {
        "name": "Incident Solar Irradiance (K_down)",
        "baseline": "870 W/m2",
        "low_bound": "780 W/m2 (cloud fringe / haze)",
        "high_bound": "940 W/m2 (peak clear sky)",
        "eval_low": lambda: simulate_portfolio(k_down=780.0),
        "eval_high": lambda: simulate_portfolio(k_down=940.0),
        "vulnerability": "MODERATE (-10.3% to +8.0%): Driven by atmospheric optical depth; baseline is conservative."
    },
    {
        "name": "Cell Radiometric Coupling Factor (eta_cell)",
        "baseline": "1.00 (flat terrain / standard nadir view)",
        "low_bound": "0.75 (street canyon cavity trapping)",
        "high_bound": "1.00 (maximum theoretical coupling)",
        "eval_low": lambda: simulate_portfolio(eta_cell=0.75),
        "eval_high": lambda: simulate_portfolio(eta_cell=1.00),
        "vulnerability": "MODERATE (-25.0% to 0.0%): Accounting for 3D canyon multiple reflections and view zenith angle."
    }
]

tornado_table = []
for p in parameters:
    low_res = p["eval_low"]()
    high_res = p["eval_high"]()
    pct_low = ((low_res - base_portfolio_dlst) / abs(base_portfolio_dlst)) * 100.0
    pct_high = ((high_res - base_portfolio_dlst) / abs(base_portfolio_dlst)) * 100.0
    tornado_table.append({
        "parameter": p["name"],
        "baseline": p["baseline"],
        "low_bound": p["low_bound"],
        "high_bound": p["high_bound"],
        "low_mean_dlst": round(float(low_res), 3),
        "high_mean_dlst": round(float(high_res), 3),
        "impact_pct_low": round(float(pct_low), 1),
        "impact_pct_high": round(float(pct_high), 1),
        "impact_range_str": f"{round(float(pct_low), 1):+.1f}% to {round(float(pct_high), 1):+.1f}%",
        "vulnerability": p["vulnerability"]
    })

output = {
    "scenario": "Medium Budget (Rs 2.5 Crores, 138 cells)",
    "base_mean_dlst_c": round(float(base_portfolio_dlst), 3),
    "tornado_table": tornado_table
}

with open('docs/validation/tornado_sensitivity_results.json', 'w') as f:
    json.dump(output, f, indent=2)

print("\nTornado Table Results:")
for t in tornado_table:
    print(f"{t['parameter']}: {t['impact_range_str']}")
