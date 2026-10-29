path = 'frontend/src/components/interventions/Optimization.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'import { useState, useMemo, useEffect } from "react";',
    'import { useState, useMemo, useEffect, useRef } from "react";'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Added useRef to Optimization.tsx')

