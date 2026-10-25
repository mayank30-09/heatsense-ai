import pandas as pd
import numpy as np

df = pd.read_parquet('data/processed/sensitivity/policy_d/analysis.parquet')

# Apply unified threshold: ST_QA <= 3.0 K and LST_OBS_COUNT >= 2.0
filtered = df[(df['LST_QA_MEDIAN_K'] <= 3.0) & (df['LST_OBS_COUNT'] >= 2.0)].copy()

seasons_order = ['winter', 'summer', 'monsoon', 'post_monsoon']
years = [2022, 2023, 2024, 2025, 2026]

rows = []
for y in years:
    for s in seasons_order:
        sub = filtered[(filtered['year'] == y) & (filtered['season'] == s)]
        total_valid = len(sub)
        pct_valid = (total_valid / 49747) * 100.0
        
        if total_valid == 0:
            rows.append({
                'year': y, 'season': s.capitalize(), 'valid_cells': 0, 'pct_valid': 0.0,
                'min': None, 'p5': None, 'p50': None, 'mean': None, 'p95': None, 'p99': None, 'max': None,
                'gt45': 0.0, 'ge48': 0.0, 'ge50': 0.0, 'status': 'Excluded (0% pass filter)'
            })
            continue
            
        lst = sub['LST_C']
        min_v = lst.min()
        p5_v = np.percentile(lst, 5)
        p50_v = np.percentile(lst, 50)
        mean_v = lst.mean()
        p95_v = np.percentile(lst, 95)
        p99_v = np.percentile(lst, 99)
        max_v = lst.max()
        gt45 = (lst > 45.0).mean() * 100.0
        ge48 = (lst >= 48.0).mean() * 100.0
        ge50 = (lst >= 50.0).mean() * 100.0
        
        status = 'Approved Operational' if (y == 2026 and s == 'summer') else ('Approved Baseline' if s != 'monsoon' else 'Excluded (Monsoon)')
        if s == 'monsoon':
            status = 'Excluded (Unreliable)'
            
        rows.append({
            'year': y, 'season': s.capitalize(), 'valid_cells': total_valid, 'pct_valid': round(pct_valid, 1),
            'min': round(min_v, 2), 'p5': round(p5_v, 2), 'p50': round(p50_v, 2), 'mean': round(mean_v, 2),
            'p95': round(p95_v, 2), 'p99': round(p99_v, 2), 'max': round(max_v, 2),
            'gt45': round(gt45, 2), 'ge48': round(ge48, 2), 'ge50': round(ge50, 2),
            'status': status
        })

df_t1 = pd.DataFrame(rows)
lines = [
    "| Year | Season | Valid Cells | Min (°C) | P5 (°C) | P50 (Median) | Mean (°C) | P95 (°C) | P99 (°C) | Max (°C) | % > 45°C | % ≥ 48°C | % ≥ 50°C | Operational Status |",
    "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
]
for idx, r in df_t1.iterrows():
    if r['valid_cells'] == 0:
        lines.append(f"| **{r['year']}** | {r['season']}* | 0 (0.0%) | — | — | — | — | — | — | — | 0.00% | 0.00% | 0.00% | **CONTAMINATED — EXCLUDED (0% pass filter)** |")
    elif r['valid_cells'] < 100:
        lines.append(f"| **{r['year']}** | {r['season']}* | {r['valid_cells']} (<0.1%) | {r['min']} | {r['p5']} | **{r['p50']}** | {r['mean']} | **{r['p95']}** | **{r['p99']}** | **{r['max']}** | **{r['gt45']}%** | **{r['ge48']}%** | **{r['ge50']}%** | **CONTAMINATED — EXCLUDED (<0.1% pass)** |")
    else:
        op = r['status']
        if r['season'] == 'Summer' and r['year'] == 2026:
            op = '**OPERATIONAL TARGET**'
        s_star = r['season'] + ('*' if r['season'] == 'Monsoon' else '')
        lines.append(f"| **{r['year']}** | **{s_star}** | {r['valid_cells']:,} ({r['pct_valid']}%) | {r['min']} | {r['p5']} | **{r['p50']}** | {r['mean']} | **{r['p95']}** | **{r['p99']}** | **{r['max']}** | **{r['gt45']}%** | **{r['ge48']}%** | **{r['ge50']}%** | {op} |")

with open('docs/validation/table1_unified.md', 'w', encoding='utf-8') as f:
    f.write("\n".join(lines) + "\n")

print("Saved docs/validation/table1_unified.md successfully!")
