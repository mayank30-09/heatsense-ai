import os

# 1. Patch ScenarioLab.tsx
path_slab = 'frontend/src/components/interventions/ScenarioLab.tsx'
with open(path_slab, 'r', encoding='utf-8') as f:
    slab_content = f.read()

old_prop = '  onSwitchToOptimization?: (budgetInr: number) => void;'
new_prop = '''  onSwitchToOptimization?: (config: number | {
    budgetInr: number;
    algorithm?: "exact" | "nsga2" | "greedy";
    strategy?: "hotspot_first" | "max_benefit" | "cost_effective";
    targetTypes?: Record<InterventionType, boolean>;
    scope?: string;
    autoRun?: boolean;
    source?: string;
  }) => void;'''

if old_prop in slab_content:
    slab_content = slab_content.replace(old_prop, new_prop)
elif old_prop.replace('\n', '\r\n') in slab_content:
    slab_content = slab_content.replace(old_prop.replace('\n', '\r\n'), new_prop.replace('\n', '\r\n'))

old_sim_click = 'onClick={() => onSwitchToOptimization(simBudget)}'
new_sim_click = '''onClick={() => onSwitchToOptimization({
                        budgetInr: simBudget,
                        algorithm: simFocus === "balanced" ? "nsga2" : "exact",
                        strategy: simFocus === "hotspots" ? "hotspot_first" : simFocus === "green" ? "cost_effective" : "max_benefit",
                        targetTypes: enabledTypes,
                        autoRun: true,
                        source: "Scenario Lab Custom Simulator",
                      })}'''

if old_sim_click in slab_content:
    slab_content = slab_content.replace(old_sim_click, new_sim_click)
elif old_sim_click.replace('\n', '\r\n') in slab_content:
    slab_content = slab_content.replace(old_sim_click.replace('\n', '\r\n'), new_sim_click.replace('\n', '\r\n'))

with open(path_slab, 'w', encoding='utf-8') as f:
    f.write(slab_content)
print('Updated ScenarioLab.tsx')


# 2. Patch App.tsx
path_app = 'frontend/src/App.tsx'
with open(path_app, 'r', encoding='utf-8') as f:
    app_content = f.read()

old_app_state = '  const [scenarioBudget, setScenarioBudget] = useState<number | undefined>(undefined);'
new_app_state = '''  const [scenarioBudget, setScenarioBudget] = useState<number | undefined>(undefined);
  const [scenarioConfig, setScenarioConfig] = useState<any>(undefined);'''

if old_app_state in app_content:
    app_content = app_content.replace(old_app_state, new_app_state)
elif old_app_state.replace('\n', '\r\n') in app_content:
    app_content = app_content.replace(old_app_state.replace('\n', '\r\n'), new_app_state.replace('\n', '\r\n'))

old_slab_jsx = '''                <ScenarioLab
                  onSwitchToMap={() => setActiveView("Heat Map")}
                  onSwitchToOptimization={(budget) => {
                    setScenarioBudget(budget);
                    setActiveView("Optimization");
                  }}
                />'''

new_slab_jsx = '''                <ScenarioLab
                  onSwitchToMap={() => setActiveView("Heat Map")}
                  onSwitchToOptimization={(cfg) => {
                    if (typeof cfg === "number") {
                      setScenarioConfig({ budgetInr: cfg, autoRun: true, source: "Scenario Lab" });
                      setScenarioBudget(cfg);
                    } else {
                      setScenarioConfig(cfg);
                      setScenarioBudget(cfg.budgetInr);
                    }
                    setActiveView("Optimization");
                  }}
                />'''

if old_slab_jsx in app_content:
    app_content = app_content.replace(old_slab_jsx, new_slab_jsx)
elif old_slab_jsx.replace('\n', '\r\n') in app_content:
    app_content = app_content.replace(old_slab_jsx.replace('\n', '\r\n'), new_slab_jsx.replace('\n', '\r\n'))

old_opt_jsx = '''                <Optimization
                  initialBudgetInr={scenarioBudget}
                  onSwitchToMap={() => setActiveView("Heat Map")}
                />'''

new_opt_jsx = '''                <Optimization
                  initialBudgetInr={scenarioBudget}
                  initialConfig={scenarioConfig}
                  onSwitchToMap={() => setActiveView("Heat Map")}
                />'''

if old_opt_jsx in app_content:
    app_content = app_content.replace(old_opt_jsx, new_opt_jsx)
elif old_opt_jsx.replace('\n', '\r\n') in app_content:
    app_content = app_content.replace(old_opt_jsx.replace('\n', '\r\n'), new_opt_jsx.replace('\n', '\r\n'))

with open(path_app, 'w', encoding='utf-8') as f:
    f.write(app_content)
print('Updated App.tsx')


# 3. Patch Optimization.tsx
path_opt = 'frontend/src/components/interventions/Optimization.tsx'
with open(path_opt, 'r', encoding='utf-8') as f:
    opt_content = f.read()

old_opt_props = '''interface OptimizationProps {
  initialBudgetInr?: number;
  onSwitchToMap?: () => void;
  onSelectCandidateOnMap?: (candidate: InterventionCandidateItem) => void;
}'''

new_opt_props = '''interface OptimizationProps {
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
  onSelectCandidateOnMap?: (candidate: InterventionCandidateItem) => void;
}'''

if old_opt_props in opt_content:
    opt_content = opt_content.replace(old_opt_props, new_opt_props)
elif old_opt_props.replace('\n', '\r\n') in opt_content:
    opt_content = opt_content.replace(old_opt_props.replace('\n', '\r\n'), new_opt_props.replace('\n', '\r\n'))

old_fn_head = '''export default function Optimization({
  initialBudgetInr = 25000000,
  onSwitchToMap,
  onSelectCandidateOnMap,
}: OptimizationProps) {'''

new_fn_head = '''export default function Optimization({
  initialBudgetInr = 25000000,
  initialConfig,
  onSwitchToMap,
  onSelectCandidateOnMap,
}: OptimizationProps) {'''

if old_fn_head in opt_content:
    opt_content = opt_content.replace(old_fn_head, new_fn_head)
elif old_fn_head.replace('\n', '\r\n') in opt_content:
    opt_content = opt_content.replace(old_fn_head.replace('\n', '\r\n'), new_fn_head.replace('\n', '\r\n'))

old_init_state = '''  // Configuration State
  const [budget, setBudget] = useState<number>(initialBudgetInr);
  const [algorithm, setAlgorithm] = useState<"exact" | "nsga2" | "greedy">("exact");
  const [strategy, setStrategy] = useState<"hotspot_first" | "max_benefit" | "cost_effective">("hotspot_first");
  const [generations, setGenerations] = useState<number>(20);
  const [allowedTypes, setAllowedTypes] = useState<Record<InterventionType, boolean>>({'''

new_init_state = '''  // Configuration State
  const [budget, setBudget] = useState<number>(initialConfig?.budgetInr ?? initialBudgetInr);
  const [algorithm, setAlgorithm] = useState<"exact" | "nsga2" | "greedy">(initialConfig?.algorithm ?? "exact");
  const [strategy, setStrategy] = useState<"hotspot_first" | "max_benefit" | "cost_effective">(initialConfig?.strategy ?? "hotspot_first");
  const [generations, setGenerations] = useState<number>(20);
  const [allowedTypes, setAllowedTypes] = useState<Record<InterventionType, boolean>>(
    initialConfig?.targetTypes ?? {'''

if old_init_state in opt_content:
    opt_content = opt_content.replace(old_init_state, new_init_state)
elif old_init_state.replace('\n', '\r\n') in opt_content:
    opt_content = opt_content.replace(old_init_state.replace('\n', '\r\n'), new_init_state.replace('\n', '\r\n'))

# Add auto-run effect after handleRunOptimization
old_handle_run = '''  const handleRunOptimization = async () => {'''
new_handle_run = '''  const hasAutoRunRef = useRef(false);
  useEffect(() => {
    if (initialConfig?.autoRun && !hasAutoRunRef.current) {
      hasAutoRunRef.current = true;
      handleRunOptimization();
    }
  }, [initialConfig]);

  const handleRunOptimization = async () => {'''

if old_handle_run in opt_content:
    opt_content = opt_content.replace(old_handle_run, new_handle_run, 1)
elif old_handle_run.replace('\n', '\r\n') in opt_content:
    opt_content = opt_content.replace(old_handle_run.replace('\n', '\r\n'), new_handle_run.replace('\n', '\r\n'), 1)

# Ensure useRef is imported in Optimization.tsx
if 'import { useEffect, useMemo, useState }' in opt_content:
    opt_content = opt_content.replace(
        'import { useEffect, useMemo, useState }',
        'import { useEffect, useMemo, useRef, useState }'
    )
elif 'import { useEffect, useMemo, useState }'.replace('\n', '\r\n') in opt_content:
    opt_content = opt_content.replace(
        'import { useEffect, useMemo, useState }'.replace('\n', '\r\n'),
        'import { useEffect, useMemo, useRef, useState }'.replace('\n', '\r\n')
    )

with open(path_opt, 'w', encoding='utf-8') as f:
    f.write(opt_content)
print('Updated Optimization.tsx')
