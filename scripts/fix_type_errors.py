# 1. Fix Optimization.tsx
path_opt = 'frontend/src/components/interventions/Optimization.tsx'
with open(path_opt, 'r', encoding='utf-8') as f:
    opt_content = f.read()

target_props = '''interface OptimizationProps {
  initialBudgetInr?: number;
  onSwitchToMap?: () => void;
  onSelectCandidateOnMap?: (candidateId: string) => void;
}'''

new_props = '''interface OptimizationProps {
  initialBudgetInr?: number;
  initialConfig?: {
    budgetInr?: number;
    algorithm?: "exact" | "nsga2" | "greedy";
    strategy?: "hotspot_first" | "max_benefit" | "cost_effective";
    targetTypes?: Record<InterventionType, boolean>;
    scope?: string;
    autoRun?: boolean;
    source?: string;
  };
  onSwitchToMap?: () => void;
  onSelectCandidateOnMap?: (candidateId: string) => void;
}'''

if target_props in opt_content:
    opt_content = opt_content.replace(target_props, new_props)
elif target_props.replace('\n', '\r\n') in opt_content:
    opt_content = opt_content.replace(target_props.replace('\n', '\r\n'), new_props.replace('\n', '\r\n'))

with open(path_opt, 'w', encoding='utf-8') as f:
    f.write(opt_content)
print('Fixed Optimization.tsx')

# 2. Fix InterventionExplorer.tsx
path_exp = 'frontend/src/components/interventions/InterventionExplorer.tsx'
with open(path_exp, 'r', encoding='utf-8') as f:
    exp_content = f.read()

target_exp = '''          {(Object.keys(TYPE_CONFIG) as InterventionType[]).filter((t) => t !== "rainwater_fed_pond" && t !== "green_wall").map((itype) => {
            const cfg = TYPE_CONFIG[itype];
            const isSelected = selectedType === itype;'''

new_exp = '''          {(Object.keys(TYPE_CONFIG) as (keyof typeof TYPE_CONFIG)[]).map((itype) => {
            const cfg = TYPE_CONFIG[itype];
            if (!cfg) return null;
            const isSelected = selectedType === itype;'''

if target_exp in exp_content:
    exp_content = exp_content.replace(target_exp, new_exp)
elif target_exp.replace('\n', '\r\n') in exp_content:
    exp_content = exp_content.replace(target_exp.replace('\n', '\r\n'), new_exp.replace('\n', '\r\n'))

with open(path_exp, 'w', encoding='utf-8') as f:
    f.write(exp_content)
print('Fixed InterventionExplorer.tsx')

# 3. Fix MapShell.tsx
path_ms = 'frontend/src/components/map/MapShell.tsx'
with open(path_ms, 'r', encoding='utf-8') as f:
    ms_content = f.read()

target_ms = 'Baseline: Summer 2026 HPI composite · Area: {fullReportArea.result.area_km2?.toFixed(3)} km² · {fullReportArea.result.statistics?.mean_c?.toFixed(1) ?? fullReportArea.result.statistics?.mean?.toFixed(1) ?? "N/A"}°C Mean LST'
new_ms = 'Baseline: Summer 2026 HPI composite · Area: {fullReportArea.result.area_km2?.toFixed(3)} km² · {fullReportArea.result.statistics?.mean_c?.toFixed(1) ?? "N/A"}°C Mean LST'

if target_ms in ms_content:
    ms_content = ms_content.replace(target_ms, new_ms)

with open(path_ms, 'w', encoding='utf-8') as f:
    f.write(ms_content)
print('Fixed MapShell.tsx')

