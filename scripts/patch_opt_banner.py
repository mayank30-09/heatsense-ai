path = 'frontend/src/components/interventions/Optimization.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '      {/* Configuration & Controls */}'
banner = '''      {initialConfig?.source && (
        <div className="flex items-center justify-between rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-xs text-teal-900 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="text-base">⚡</span>
            <span>
              <strong>Running with settings from {initialConfig.source}:</strong> Budget {formatINR(budget)}, Strategy {strategy.replace("_", " ")}, Algorithm {algorithm.toUpperCase()}.
            </span>
          </div>
          <span className="font-mono text-[10px] text-teal-700 font-bold bg-teal-100/70 px-2 py-0.5 rounded">
            AUTO-CONFIGURED
          </span>
        </div>
      )}

      {/* Configuration & Controls */}'''

if target in content:
    content = content.replace(target, banner, 1)
elif target.replace('\n', '\r\n') in content:
    content = content.replace(target.replace('\n', '\r\n'), banner.replace('\n', '\r\n'), 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Added scenario banner to Optimization.tsx')
