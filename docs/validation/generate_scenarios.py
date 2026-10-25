"""
Generate Municipal Cooling Scenarios (Low / Medium / High Budgets)
Strictly enforces total cost <= budget including fixed per-site fees.
Outputs per-cell CSV files and scenario summary metrics for Table 8.
"""

import os
import json
import psycopg
import pandas as pd
import numpy as np

# Database connection
conn = psycopg.connect('host=127.0.0.1 port=5433 dbname=heatsense user=heatsense password=mAyanklb07')
cur = conn.cursor()

# Query priority cells with biophysical attributes
query = """
SELECT p.pixel_id, c.latitude, c.longitude, p.heat_priority_score, 
       o.observed_lst_c, o.ndbi, o.ndvi, p.is_chronic_hotspot
FROM stage_c_heat_priority_scores p
JOIN stage_c_grid_observations o ON p.pixel_id = o.pixel_id
JOIN stage_c_grid_cells c ON p.pixel_id = c.pixel_id
WHERE o.year = 2026 AND o.season = 'summer'
ORDER BY p.heat_priority_score DESC
"""
cur.execute(query)
rows = cur.fetchall()
columns = ['pixel_id', 'latitude', 'longitude', 'hpi', 'lst_c', 'ndbi', 'ndvi', 'is_chronic']
df_priority = pd.DataFrame(rows, columns=columns)

# Engineering Unit Rates & Fixed Fees (Table 7)
# Cool Roof: Rs 350 / m2 + Rs 5,000 setup per site
# Cool Paver: Rs 450 / m2 + Rs 8,000 setup per site
# Tree Canopy (Neem mature crown 50.3 m2): Rs 3,500 / tree
# Green Roof: Rs 3,600 / m2 + Rs 15,000 setup per site

# Direct Skin Temperature Reductions (|dT_s,skin|) [Low, Exp, High]
COOL_ROOF_DT = (6.5, 8.6, 11.0)
COOL_PAVER_DT = (3.0, 4.8, 6.5)
TREE_DT_MATURE = (5.0, 7.5, 10.5)  # Year 7-10 maturity
GREEN_ROOF_DT = (4.0, 6.2, 8.5)

ETA_CELL = 1.0  # Cell coupling efficiency baseline (sensitivity range 0.75 - 1.0)
TOTAL_CITY_CELLS = 49747
TOTAL_CITY_AREA_M2 = TOTAL_CITY_CELLS * 10000.0  # 497.47 km2 (100m grid)

def optimize_scenario(budget_limit, scenario_name, mix_rules):
    """
    Greedily selects top priority cells and allocates interventions matching scenario mix.
    Enforces total cost <= budget_limit including fixed fees.
    """
    selected_cells = []
    current_cost = 0.0
    
    for idx, row in df_priority.iterrows():
        cell_id = row['pixel_id']
        ndbi = row['ndbi']
        ndvi = row['ndvi']
        
        # Determine cell intervention archetype based on biophysical profile and scenario mix rules
        interventions_list = []
        areas_desc = []
        total_cell_area = 0.0
        cell_cost = 0.0
        
        # dLST accumulators [low, exp, high]
        dlst_low = 0.0
        dlst_exp = 0.0
        dlst_high = 0.0
        
        sites_count = 0
        
        # 1. Cool Roofs (feasible if built-up NDBI >= 0.02)
        if mix_rules.get('allow_cool_roof', True) and ndbi >= 0.02:
            roof_area = mix_rules['cool_roof_area_per_cell']
            num_roof_sites = mix_rules.get('roof_sites_per_cell', 2)
            c_roof = roof_area * 350.0 + (num_roof_sites * 5000.0)
            
            interventions_list.append("cool_roof")
            areas_desc.append(f"cool_roof:{roof_area:.0f}m2")
            total_cell_area += roof_area
            cell_cost += c_roof
            sites_count += num_roof_sites
            
            f_r = roof_area / 10000.0
            dlst_low += f_r * COOL_ROOF_DT[0] * ETA_CELL
            dlst_exp += f_r * COOL_ROOF_DT[1] * ETA_CELL
            dlst_high += f_r * COOL_ROOF_DT[2] * ETA_CELL

        # 2. Native Trees (roadside verges / pocket greenery, feasible if NDVI < 0.35)
        if mix_rules.get('allow_trees', True) and ndvi < 0.35:
            tree_count = mix_rules['trees_per_cell']
            tree_area = tree_count * 50.3  # 50.3 m2 per mature Neem crown
            c_trees = tree_count * 3500.0
            
            interventions_list.append(f"trees_{tree_count}")
            areas_desc.append(f"trees:{tree_count}({tree_area:.1f}m2)")
            total_cell_area += tree_area
            cell_cost += c_trees
            
            f_t = tree_area / 10000.0
            dlst_low += f_t * TREE_DT_MATURE[0] * ETA_CELL
            dlst_exp += f_t * TREE_DT_MATURE[1] * ETA_CELL
            dlst_high += f_t * TREE_DT_MATURE[2] * ETA_CELL

        # 3. Cool Permeable Pavers (high built-up walkways / parking, feasible in medium/high)
        if mix_rules.get('allow_pavers', False) and ndbi >= 0.05:
            paver_area = mix_rules['paver_area_per_cell']
            num_paver_sites = mix_rules.get('paver_sites_per_cell', 1)
            c_paver = paver_area * 450.0 + (num_paver_sites * 8000.0)
            
            interventions_list.append("cool_pavers")
            areas_desc.append(f"cool_pavers:{paver_area:.0f}m2")
            total_cell_area += paver_area
            cell_cost += c_paver
            sites_count += num_paver_sites
            
            f_p = paver_area / 10000.0
            dlst_low += f_p * COOL_PAVER_DT[0] * ETA_CELL
            dlst_exp += f_p * COOL_PAVER_DT[1] * ETA_CELL
            dlst_high += f_p * COOL_PAVER_DT[2] * ETA_CELL

        # 4. Pilot Green Roofs (only in High budget for selected institutional RCC slabs)
        if mix_rules.get('allow_green_roof', False) and (idx % 8 == 0) and ndbi >= 0.04:
            gr_area = mix_rules['green_roof_area_per_cell']
            c_gr = gr_area * 3600.0 + 15000.0
            
            interventions_list.append("green_roof")
            areas_desc.append(f"green_roof:{gr_area:.0f}m2")
            total_cell_area += gr_area
            cell_cost += c_gr
            sites_count += 1
            
            f_g = gr_area / 10000.0
            dlst_low += f_g * GREEN_ROOF_DT[0] * ETA_CELL
            dlst_exp += f_g * GREEN_ROOF_DT[1] * ETA_CELL
            dlst_high += f_g * GREEN_ROOF_DT[2] * ETA_CELL

        if cell_cost == 0:
            continue
            
        # Check budget constraint strictly
        if current_cost + cell_cost <= budget_limit:
            current_cost += cell_cost
            f_treated = total_cell_area / 10000.0
            selected_cells.append({
                'cell_id': cell_id,
                'interventions': ";".join(interventions_list),
                'areas': ";".join(areas_desc),
                'f_treated': round(f_treated, 4),
                'cost': round(cell_cost, 2),
                'dLST_low': round(-dlst_low, 3),
                'dLST_exp': round(-dlst_exp, 3),
                'dLST_high': round(-dlst_high, 3),
                'treated_area_m2': round(total_cell_area, 2),
                'sites_count': sites_count
            })
        else:
            # If a smaller alternative doesn't fit, stop
            if len(selected_cells) > 0 and (budget_limit - current_cost) < 50000:
                break
                
    df_out = pd.DataFrame(selected_cells)
    return df_out, current_cost

# Define Mix Rules for Scenarios
low_rules = {
    'allow_cool_roof': True,
    'cool_roof_area_per_cell': 250.0,
    'roof_sites_per_cell': 2,
    'allow_trees': True,
    'trees_per_cell': 15,
    'allow_pavers': False,
    'allow_green_roof': False
}

med_rules = {
    'allow_cool_roof': True,
    'cool_roof_area_per_cell': 280.0,
    'roof_sites_per_cell': 2,
    'allow_trees': True,
    'trees_per_cell': 16,
    'allow_pavers': True,
    'paver_area_per_cell': 120.0,
    'paver_sites_per_cell': 1,
    'allow_green_roof': False
}

high_rules = {
    'allow_cool_roof': True,
    'cool_roof_area_per_cell': 280.0,
    'roof_sites_per_cell': 2,
    'allow_trees': True,
    'trees_per_cell': 18,
    'allow_pavers': True,
    'paver_area_per_cell': 150.0,
    'paver_sites_per_cell': 1,
    'allow_green_roof': True,
    'green_roof_area_per_cell': 200.0
}

# Run optimizations
df_low, cost_low = optimize_scenario(5000000.0, 'Low', low_rules)
df_med, cost_med = optimize_scenario(25000000.0, 'Medium', med_rules)
df_high, cost_high = optimize_scenario(100000000.0, 'High', high_rules)

# Save CSV files
os.makedirs('docs/validation', exist_ok=True)
cols_to_save = ['cell_id', 'interventions', 'areas', 'f_treated', 'cost', 'dLST_low', 'dLST_exp', 'dLST_high']
df_low[cols_to_save].to_csv('docs/validation/scenario_low.csv', index=False)
df_med[cols_to_save].to_csv('docs/validation/scenario_medium.csv', index=False)
df_high[cols_to_save].to_csv('docs/validation/scenario_high.csv', index=False)

print(f"Saved scenario CSVs:")
print(f"Low: {len(df_low)} cells, Cost: Rs {cost_low:,.2f} <= Rs 50,00,000")
print(f"Med: {len(df_med)} cells, Cost: Rs {cost_med:,.2f} <= Rs 2,50,00,000")
print(f"High: {len(df_high)} cells, Cost: Rs {cost_high:,.2f} <= Rs 10,00,00,000")

# Function to compute exact Table 8 stats strictly from CSVs
def compute_table_stats(csv_path, total_budget):
    df = pd.read_csv(csv_path)
    n_cells = len(df)
    total_cost = df['cost'].sum()
    
    mean_dlst_low = df['dLST_low'].mean()
    mean_dlst_exp = df['dLST_exp'].mean()
    mean_dlst_high = df['dLST_high'].mean()
    
    peak_dlst_low = df['dLST_low'].min()
    peak_dlst_exp = df['dLST_exp'].min()
    peak_dlst_high = df['dLST_high'].min()
    
    # Citywide Mean dLST: sum(dLST_cell * 1 cell) / 49747 cells
    citywide_dlst_low = df['dLST_low'].sum() / TOTAL_CITY_CELLS
    citywide_dlst_exp = df['dLST_exp'].sum() / TOTAL_CITY_CELLS
    citywide_dlst_high = df['dLST_high'].sum() / TOTAL_CITY_CELLS
    
    # Area treated
    total_treated_m2 = (df['f_treated'] * 10000.0).sum()
    pct_city_treated = (total_treated_m2 / TOTAL_CITY_AREA_M2) * 100.0
    
    # Breakdown interventions
    cool_roof_m2 = 0.0
    paver_m2 = 0.0
    green_roof_m2 = 0.0
    trees_count = 0
    
    for area_str in df['areas']:
        parts = area_str.split(';')
        for p in parts:
            if 'cool_roof:' in p:
                cool_roof_m2 += float(p.replace('cool_roof:', '').replace('m2', ''))
            elif 'cool_pavers:' in p:
                paver_m2 += float(p.replace('cool_pavers:', '').replace('m2', ''))
            elif 'green_roof:' in p:
                green_roof_m2 += float(p.replace('green_roof:', '').replace('m2', ''))
            elif 'trees:' in p:
                t_cnt = int(p.split('(')[0].replace('trees:', ''))
                trees_count += t_cnt
                
    return {
        'treated_cells': int(n_cells),
        'total_cost': round(float(total_cost), 2),
        'budget_limit': float(total_budget),
        'cost_under_budget': bool(total_cost <= total_budget),
        'mean_dlst_treated': [round(float(mean_dlst_low), 2), round(float(mean_dlst_exp), 2), round(float(mean_dlst_high), 2)],
        'peak_hotspot_dlst': [round(float(peak_dlst_low), 2), round(float(peak_dlst_exp), 2), round(float(peak_dlst_high), 2)],
        'citywide_mean_dlst': [round(float(citywide_dlst_low), 4), round(float(citywide_dlst_exp), 4), round(float(citywide_dlst_high), 4)],
        'total_treated_m2': round(float(total_treated_m2), 1),
        'pct_city_area_treated': round(float(pct_city_treated), 3),
        'breakdown': {
            'cool_roof_m2': round(float(cool_roof_m2), 0),
            'cool_paver_m2': round(float(paver_m2), 0),
            'green_roof_m2': round(float(green_roof_m2), 0),
            'trees_count': int(trees_count)
        }
    }

summary = {
    'low': compute_table_stats('docs/validation/scenario_low.csv', 5000000.0),
    'medium': compute_table_stats('docs/validation/scenario_medium.csv', 25000000.0),
    'high': compute_table_stats('docs/validation/scenario_high.csv', 100000000.0),
    'notes': {
        'tree_maturity_state': 'Tree canopy cooling is evaluated at full maturity (Year 7-10, crown 50.3 m2 per tree). In Year 1 (sapling establishment), realizes 25% of canopy cooling. In Year 3 (semi-mature), realizes 65% of canopy cooling.',
        'fixed_fees_included': 'Cool roof Rs 5,000/site; Cool pavers Rs 8,000/site; Green roof Rs 15,000/site; Trees Rs 3,500/tree all inclusive.'
    }
}

with open('docs/validation/scenario_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print("\nSummary Results strictly from CSVs:")
print(json.dumps(summary, indent=2))
