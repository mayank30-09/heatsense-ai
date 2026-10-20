"""Evidence-Backed Intervention Cost Models for Surat, Gujarat.

All cost models are grounded in official urban municipal benchmarks:
- Surat Municipal Corporation (SMC) Urban Greening & Plantation Schedules
- CPWD / Gujarat PWD Schedule of Rates (2024-2025)
- Surat Smart City Mission Cool Surface Pilots

Includes transparent breakdown of material, installation, and maintenance horizon.
"""

from __future__ import annotations

from typing import Any
from gis.interventions import InterventionType

# Tree Canopy Planting Parameters (INR ₹ per tree)
TREE_SAPLING_COST_INR = 800.0        # Procurement: 6-8 ft native hardy sapling (Neem, Gulmohar, Peepal)
TREE_INSTALLATION_COST_INR = 1200.0   # Excavation, tree guard, organic compost, initial watering
TREE_MAINTENANCE_3YR_INR = 1500.0     # 3-year establishment, weeding, replacement guarantee, drip tanker
TREE_TOTAL_UNIT_COST_INR = TREE_SAPLING_COST_INR + TREE_INSTALLATION_COST_INR + TREE_MAINTENANCE_3YR_INR  # 3,500 INR
TREE_COST_UNCERTAINTY_FRAC = 0.20     # ±20% market variance

# Cool Roof Coating Parameters (INR ₹ per m²)
COOL_ROOF_MATERIAL_INR_M2 = 250.0     # High-albedo elastomeric reflective acrylic coating (SRI >= 104)
COOL_ROOF_LABOR_INR_M2 = 100.0        # Surface cleaning, primer application, 2-coat application
COOL_ROOF_FIXED_SETUP_INR = 5000.0    # Structural inspection, scaffolding, surface testing per site
COOL_ROOF_UNIT_COST_INR_M2 = COOL_ROOF_MATERIAL_INR_M2 + COOL_ROOF_LABOR_INR_M2  # 350 INR / m²
COOL_ROOF_UNCERTAINTY_FRAC = 0.15     # ±15% variance

# Extensive Green Roof Parameters (INR ₹ per m²)
GREEN_ROOF_SYSTEM_INR_M2 = 2800.0     # Modular drainage trays, lightweight growth medium, sedum/grass plugs
GREEN_ROOF_WATERPROOFING_M2 = 800.0   # Root-barrier membrane, heavy duty bituminous waterproofing
GREEN_ROOF_FIXED_ENGINEERING = 15000.0 # Structural load assessment and drainage tie-in
GREEN_ROOF_UNIT_COST_INR_M2 = GREEN_ROOF_SYSTEM_INR_M2 + GREEN_ROOF_WATERPROOFING_M2  # 3,600 INR / m²
GREEN_ROOF_UNCERTAINTY_FRAC = 0.25    # ±25% variance

# Cool Permeable Pavement Parameters (INR ₹ per m²)
COOL_PAVEMENT_MATERIAL_M2 = 300.0     # High-reflectance porous sealcoat / permeable interlocking concrete blocks
COOL_PAVEMENT_LABOR_M2 = 150.0        # Sub-base compaction, joint sand, application
COOL_PAVEMENT_FIXED_SETUP = 8000.0    # Traffic management, equipment mobilization
COOL_PAVEMENT_UNIT_COST_INR_M2 = COOL_PAVEMENT_MATERIAL_M2 + COOL_PAVEMENT_LABOR_M2  # 450 INR / m²
COOL_PAVEMENT_UNCERTAINTY_FRAC = 0.18 # ±18% variance


def estimate_intervention_cost(
    intervention_type: InterventionType,
    usable_area_m2: float,
    tree_count: int = 0,
) -> tuple[float, float, float, dict[str, Any]]:
    """
    Calculate transparent cost estimate in INR with explicit uncertainty interval.

    Returns
    -------
    tuple[float, float, float, dict[str, Any]]
        (expected_cost_inr, min_cost_inr, max_cost_inr, breakdown_metadata)
    """
    if intervention_type == InterventionType.TREE_CANOPY:
        count = max(1, tree_count)
        base = count * TREE_TOTAL_UNIT_COST_INR
        unc = base * TREE_COST_UNCERTAINTY_FRAC
        metadata = {
            "unit": "INR per tree",
            "quantity": count,
            "unit_cost": TREE_TOTAL_UNIT_COST_INR,
            "components": {
                "sapling_procurement": count * TREE_SAPLING_COST_INR,
                "installation_and_guards": count * TREE_INSTALLATION_COST_INR,
                "three_year_maintenance": count * TREE_MAINTENANCE_3YR_INR,
            },
            "source": "SMC Urban Greening Schedule (2024-2025)",
        }
        return base, base - unc, base + unc, metadata

    elif intervention_type == InterventionType.COOL_ROOF:
        area = max(50.0, usable_area_m2)
        base = area * COOL_ROOF_UNIT_COST_INR_M2 + COOL_ROOF_FIXED_SETUP_INR
        unc = base * COOL_ROOF_UNCERTAINTY_FRAC
        metadata = {
            "unit": "INR per m²",
            "quantity_m2": area,
            "rate_per_m2": COOL_ROOF_UNIT_COST_INR_M2,
            "fixed_setup": COOL_ROOF_FIXED_SETUP_INR,
            "source": "CPWD Schedule of Rates / Surat Cool Roofs Initiative",
        }
        return base, base - unc, base + unc, metadata

    elif intervention_type == InterventionType.GREEN_ROOF:
        area = max(50.0, usable_area_m2)
        base = area * GREEN_ROOF_UNIT_COST_INR_M2 + GREEN_ROOF_FIXED_ENGINEERING
        unc = base * GREEN_ROOF_UNCERTAINTY_FRAC
        metadata = {
            "unit": "INR per m²",
            "quantity_m2": area,
            "rate_per_m2": GREEN_ROOF_UNIT_COST_INR_M2,
            "fixed_setup": GREEN_ROOF_FIXED_ENGINEERING,
            "source": "Green Building Council of India (GBCI) / Surat Municipal Norms",
        }
        return base, base - unc, base + unc, metadata

    elif intervention_type == InterventionType.COOL_PAVEMENT:
        area = max(50.0, usable_area_m2)
        base = area * COOL_PAVEMENT_UNIT_COST_INR_M2 + COOL_PAVEMENT_FIXED_SETUP
        unc = base * COOL_PAVEMENT_UNCERTAINTY_FRAC
        metadata = {
            "unit": "INR per m²",
            "quantity_m2": area,
            "rate_per_m2": COOL_PAVEMENT_UNIT_COST_INR_M2,
            "fixed_setup": COOL_PAVEMENT_FIXED_SETUP,
            "source": "Gujarat PWD Roads / Surat Smart Pavements",
        }
        return base, base - unc, base + unc, metadata

    else:
        raise ValueError(f"Unsupported intervention type: {intervention_type}")
