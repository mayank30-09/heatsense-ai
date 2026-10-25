"""Engineering-Grounded Intervention Cost Models for Surat, Gujarat (Stage D).

CRITICAL ENGINEERING REALISM PRINCIPLES:
1. Replaces flat rates with an itemized, transparent cost breakdown:
   - Materials Procurement
   - Labour & Surface Preparation
   - Design & Supervision (5-8%)
   - GST (18% statutory tax)
   - Contingency (10-15%, expected 12%)
   - Fixed Site Setup (scaled non-linearly by site size)
   - Water Supply / Municipal Tanker Provision
   - 3-Year and 10-Year Maintenance Horizons
   - Plant Mortality Replacement Provision (based on survival rate)
2. All rates are explicitly marked as "INDICATIVE".
3. Every rate specifies the exact official benchmark to be replaced at procurement:
   - CPWD Delhi Schedule of Rates (DSR 2023-2024)
   - SMC Parks and Gardens Annual Rate Contract
   - Or explicitly tagged as "TO BE CONFIRMED" (no fabricated item numbers).
4. Calculates Whole-Life Cost (WLC) and WLC per degree-cell-area (INR / (°C·m²)).
"""

from __future__ import annotations

import math
from typing import Any
from gis.interventions import InterventionType

GST_RATE = 0.18
CONTINGENCY_RATE_EXPECTED = 0.12
CONTINGENCY_RATE_LOW = 0.10
CONTINGENCY_RATE_HIGH = 0.15
DESIGN_SUPERVISION_RATE = 0.06

# Water tanker cost: 5,000L municipal non-potable tanker in Surat ~ ₹600 / tanker
WATER_TANKER_COST_PER_KL_INR = 120.0  # ₹120 per 1,000 L (m³)


def scale_fixed_setup(base_setup_inr: float, area_m2: float, reference_area_m2: float = 500.0) -> float:
    """Scale fixed setup and mobilization cost by site size."""
    if area_m2 <= 0:
        return base_setup_inr
    scale = max(1.0, math.sqrt(area_m2 / reference_area_m2))
    return round(base_setup_inr * scale, 2)


def estimate_intervention_cost(
    intervention_type: InterventionType,
    usable_area_m2: float,
    tree_count: int = 0,
    expected_cooling_c: float = 1.0,
) -> tuple[float, float, float, dict[str, Any]]:
    """
    Calculate realistic, itemized engineering cost in INR with explicit uncertainty interval.

    Returns
    -------
    tuple[float, float, float, dict[str, Any]]
        (expected_cost_inr, min_cost_inr, max_cost_inr, breakdown_metadata)
    """
    area = max(25.0, usable_area_m2)

    # ---------------------------------------------------------------------------
    # 1. Native Tree Canopy Planting
    # ---------------------------------------------------------------------------
    if intervention_type == InterventionType.TREE_CANOPY:
        count = max(1, tree_count)
        mat_per_unit = 600.0   # Containerized healthy native sapling (6-8 ft)
        lab_per_unit = 1400.0  # Excavation, tree guard, compost, planting
        base_setup = 2500.0
        scaled_setup = scale_fixed_setup(base_setup, count * 50.3, reference_area_m2=500.0)

        materials = count * mat_per_unit
        labour = count * lab_per_unit
        direct_cost = materials + labour

        design_supervision = direct_cost * DESIGN_SUPERVISION_RATE
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * CONTINGENCY_RATE_EXPECTED

        # Water tanker cost: ~40 L/tree/week for 40 active hot weeks over 3 years
        # Total water ~ 4.8 m³ / tree = ₹576 / tree
        water_cost = count * 600.0

        # Survival rate = 85% -> 15% mortality replacement provision
        survival_rate = 0.85
        mortality_fraction = 1.0 - survival_rate
        plant_replacement = mortality_fraction * count * (mat_per_unit + lab_per_unit)

        # 3-year municipal maintenance: weeding, pruning, tanker routing
        maint_3yr = count * 1500.0
        # 10-year maintenance: post-establishment pruning, arborist inspection
        maint_10yr = maint_3yr + count * 2200.0

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup + water_cost
        wlc_3yr = capital_cost + maint_3yr + plant_replacement
        wlc_10yr = capital_cost + maint_10yr + plant_replacement

        # Uncertainty bounds: ±20% market variance
        unc_frac = 0.20
        source = "SMC Parks & Gardens Dept Annual Rate Contract for Plantation"
        unit_str = "INR per tree"
        quantity = count

    # ---------------------------------------------------------------------------
    # 2. Cool Roof Coating (High-SRI Elastomeric Acrylic)
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.COOL_ROOF:
        mat_per_m2 = 220.0  # High-SRI elastomeric acrylic coating (SRI >= 104)
        lab_per_m2 = 80.0   # High-pressure wash, primer, 2 topcoats
        base_setup = 5000.0 # Scaffolding, perimeter harness, surface test
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=500.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * DESIGN_SUPERVISION_RATE
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * CONTINGENCY_RATE_EXPECTED
        water_cost = 0.0
        plant_replacement = 0.0

        maint_3yr = area * 50.0   # 3-year warranty recoat provision
        maint_10yr = area * 180.0 # Full recoat cycle at Year 5-6

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup
        wlc_3yr = capital_cost + maint_3yr
        wlc_10yr = capital_cost + maint_10yr

        unc_frac = 0.15
        source = "CPWD DSR 2023 Item 12.58 / SMC Waterproofing & Painting Schedule"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 3. Extensive Green Roof (Structural RCC Slab)
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.GREEN_ROOF:
        mat_per_m2 = 2200.0 # Modular drainage cells, filter fleece, lightweight media
        lab_per_m2 = 800.0  # Root-barrier membrane, waterproofing tie-in, planting
        base_setup = 15000.0 # Structural engineer load assessment & permit
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=300.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * 0.08
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * 0.15
        water_cost = area * 150.0 # Automated drip tie-in & supplementary water

        survival_rate = 0.80
        plant_replacement = (1.0 - survival_rate) * area * 350.0

        maint_3yr = area * 600.0   # Drip lines, weeding, nutrient replenishment
        maint_10yr = area * 1800.0 # Substrate replenishment, membrane testing

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup + water_cost
        wlc_3yr = capital_cost + maint_3yr + plant_replacement
        wlc_10yr = capital_cost + maint_10yr + plant_replacement

        unc_frac = 0.25
        source = "Specialized Vendor Quotes (e.g. Indian Green Building Council rate cards) [TO BE CONFIRMED]"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 4. Cool Permeable Pavement (Reflective Interlocking Blocks)
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.COOL_PAVEMENT:
        mat_per_m2 = 280.0 # High-albedo porous interlocking concrete pavers (60mm)
        lab_per_m2 = 120.0 # Sub-base grading, compaction, joint sand filling
        base_setup = 8000.0 # Equipment mobilization and traffic control
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=500.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * DESIGN_SUPERVISION_RATE
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * CONTINGENCY_RATE_EXPECTED
        water_cost = 0.0
        plant_replacement = 0.0

        maint_3yr = area * 50.0   # Joint sand replenishment, pressure cleaning
        maint_10yr = area * 150.0 # Interlocking resetting, joint seal

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup
        wlc_3yr = capital_cost + maint_3yr
        wlc_10yr = capital_cost + maint_10yr

        unc_frac = 0.18
        source = "CPWD DSR 2023 Item 16.68 / SMC Road Works Schedule"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 5. Public Park or Garden with Native Trees
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.PUBLIC_PARK_NATIVE_TREES:
        mat_per_m2 = 350.0 # Native tree saplings, lawn turf, ornamental border shrubs
        lab_per_m2 = 250.0 # Site earthwork, soil conditioning, irrigation piping, planting
        base_setup = 15000.0
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=1000.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * 0.07
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * 0.12
        water_cost = area * 120.0 # Initial establishment watering

        survival_rate = 0.85
        plant_replacement = (1.0 - survival_rate) * area * 100.0

        maint_3yr = area * 300.0
        maint_10yr = area * 950.0

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup + water_cost
        wlc_3yr = capital_cost + maint_3yr + plant_replacement
        wlc_10yr = capital_cost + maint_10yr + plant_replacement

        unc_frac = 0.22
        source = "SMC Parks & Gardens Schedule / CPWD DSR 2023 Horticulture Works"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 6. Dense Native Plantation (Miyawaki-Style)
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.DENSE_MIYAWAKI_PLANTATION:
        # 3-5 saplings/m² = ~4 saplings/m² * ₹120 = ₹480/m² + thick organic mulch ₹150/m²
        mat_per_m2 = 630.0
        lab_per_m2 = 320.0 # Deep 1m soil excavation, organic manure mixing, high-density planting
        base_setup = 10000.0
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=500.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * 0.06
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * 0.12
        water_cost = area * 250.0 # Intensive initial watering in Years 1-2

        survival_rate = 0.90
        plant_replacement = (1.0 - survival_rate) * area * 150.0

        maint_3yr = area * 400.0  # Intensive weeding in Years 1-2, self-sustaining Year 3
        maint_10yr = area * 600.0 # Minimal post-establishment intervention

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup + water_cost
        wlc_3yr = capital_cost + maint_3yr + plant_replacement
        wlc_10yr = capital_cost + maint_10yr + plant_replacement

        unc_frac = 0.25
        source = "SMC CSR Plantation Rate Benchmarks [TO BE CONFIRMED]"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 7. Bioswale / Rain Garden
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.BIOSWALE_RAIN_GARDEN:
        mat_per_m2 = 450.0 # Engineered sand-gravel filter media, perforated pipe, native sedges
        lab_per_m2 = 350.0 # Trench grading, sub-base installation, planting
        base_setup = 8000.0
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=500.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * 0.06
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * 0.12
        water_cost = area * 50.0 # Minimal dry-spell supplemental watering

        survival_rate = 0.85
        plant_replacement = (1.0 - survival_rate) * area * 80.0

        maint_3yr = area * 180.0
        maint_10yr = area * 500.0

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup + water_cost
        wlc_3yr = capital_cost + maint_3yr + plant_replacement
        wlc_10yr = capital_cost + maint_10yr + plant_replacement

        unc_frac = 0.20
        source = "CPWD DSR 2023 Roadside Drainage Works [TO BE CONFIRMED]"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 8. Rainwater-Fed Retention Pond
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.RAINWATER_FED_POND:
        mat_per_m2 = 650.0 # Bentonite clay / EPDM liner, inlet silt trap, overflow weir, aerator
        lab_per_m2 = 550.0 # Deep basin excavation, slope stabilization, embankment compaction
        base_setup = 25000.0 # Hydrogeological survey & municipal drainage connection
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=1000.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * 0.08
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * 0.15
        water_cost = area * 200.0 # Initial reservoir filling & treated water pipeline tie-in

        survival_rate = 1.00 # Civil structure
        plant_replacement = 0.0

        maint_3yr = area * 450.0  # Desilting, aeration power, aquatic weed harvesting
        maint_10yr = area * 1400.0 # Liner inspection, dredging, embankment repair

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup + water_cost
        wlc_3yr = capital_cost + maint_3yr
        wlc_10yr = capital_cost + maint_10yr

        unc_frac = 0.25
        source = "SMC Water Works / Stormwater Drainage Schedule [TO BE CONFIRMED]"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 9. Shaded Parking Structure (High-SRI Tensile / Solar Canopy)
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.SHADED_PARKING_STRUCTURE:
        mat_per_m2 = 1800.0 # Tubular steel truss, high-SRI PVDF tensile fabric (SRI >= 85)
        lab_per_m2 = 600.0  # Foundation concrete footings, structural erection, tensioning
        base_setup = 12000.0
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=500.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * 0.06
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * 0.10
        water_cost = 0.0
        plant_replacement = 0.0

        maint_3yr = area * 120.0
        maint_10yr = area * 450.0

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup
        wlc_3yr = capital_cost + maint_3yr
        wlc_10yr = capital_cost + maint_10yr

        unc_frac = 0.15
        source = "CPWD DSR 2023 Structural Steel & Fabric Works Item 10.25"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 10. Vertical Green Wall (Exterior Facade Trellis)
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.GREEN_WALL:
        mat_per_m2 = 2400.0 # Stainless steel cable trellis, lightweight planters, drip line
        lab_per_m2 = 900.0  # Wall anchor drilling, structural mounting, climbing plant installation
        base_setup = 10000.0
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=200.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * 0.07
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * 0.12
        water_cost = area * 180.0

        survival_rate = 0.80
        plant_replacement = (1.0 - survival_rate) * area * 300.0

        maint_3yr = area * 550.0
        maint_10yr = area * 1600.0

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup + water_cost
        wlc_3yr = capital_cost + maint_3yr + plant_replacement
        wlc_10yr = capital_cost + maint_10yr + plant_replacement

        unc_frac = 0.22
        source = "Commercial Vendor Quotations (IGBC / LEED India) [TO BE CONFIRMED]"
        unit_str = "INR per m²"
        quantity = area

    # ---------------------------------------------------------------------------
    # 11. Permeable Ground Cover (Gravel Turf / Crushed Aggregate)
    # ---------------------------------------------------------------------------
    elif intervention_type == InterventionType.PERMEABLE_GROUND_COVER:
        mat_per_m2 = 180.0 # Graded crushed basalt aggregate, porous geotextile underlayment
        lab_per_m2 = 90.0  # Excavation, edging, sub-grade compaction, spreading
        base_setup = 5000.0
        scaled_setup = scale_fixed_setup(base_setup, area, reference_area_m2=500.0)

        materials = area * mat_per_m2
        labour = area * lab_per_m2
        direct_cost = materials + labour

        design_supervision = direct_cost * 0.05
        gst = (direct_cost + design_supervision) * GST_RATE
        contingency = (direct_cost + design_supervision) * 0.10
        water_cost = 0.0
        plant_replacement = 0.0

        maint_3yr = area * 40.0
        maint_10yr = area * 120.0

        capital_cost = direct_cost + design_supervision + gst + contingency + scaled_setup
        wlc_3yr = capital_cost + maint_3yr
        wlc_10yr = capital_cost + maint_10yr

        unc_frac = 0.15
        source = "CPWD DSR 2023 Item 16.12 Gravel and Aggregate Pathways"
        unit_str = "INR per m²"
        quantity = area

    else:
        raise ValueError(f"Unsupported intervention type: {intervention_type}")

    # Calculate whole-life cost per degree-cell-area (INR / (°C·m²))
    extensive_cooling_degree_m2 = max(1.0, area * max(0.1, expected_cooling_c))
    wlc_per_c_m2 = round(wlc_3yr / extensive_cooling_degree_m2, 2)

    expected_cost = round(capital_cost, 2)
    min_cost = round(capital_cost * (1.0 - unc_frac), 2)
    max_cost = round(capital_cost * (1.0 + unc_frac), 2)

    metadata: dict[str, Any] = {
        "rate_status": "INDICATIVE",
        "unit": unit_str,
        "quantity": quantity,
        "materials_cost": round(materials, 2),
        "labour_cost": round(labour, 2),
        "direct_cost": round(direct_cost, 2),
        "design_and_supervision_cost": round(design_supervision, 2),
        "gst_18_pct": round(gst, 2),
        "contingency_cost": round(contingency, 2),
        "site_setup_scaled_cost": round(scaled_setup, 2),
        "water_tanker_cost": round(water_cost, 2),
        "plant_replacement_cost": round(plant_replacement, 2),
        "capital_cost_inr": expected_cost,
        "maintenance_3yr_cost": round(maint_3yr, 2),
        "maintenance_10yr_cost": round(maint_10yr, 2),
        "whole_life_cost_3yr_inr": round(wlc_3yr, 2),
        "whole_life_cost_10yr_inr": round(wlc_10yr, 2),
        "whole_life_cost_per_c_m2": wlc_per_c_m2,
        "uncertainty_fraction": unc_frac,
        "source_to_be_replaced": source,
    }

    return expected_cost, min_cost, max_cost, metadata
