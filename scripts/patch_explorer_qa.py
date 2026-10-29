path = 'frontend/src/components/interventions/__tests__/ClusterExplorer.test.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('expect(html).toContain("Phase 1 Funded Units");', 'expect(html).toContain("Phase 1 Funded Packages");')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated ClusterExplorer.test.tsx for Phase 1 Funded Packages')
