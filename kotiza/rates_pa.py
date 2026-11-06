"""Panama labor reference data: CAPAC-SUNTRACS convention wages and the
standard employer burden (cargas sociales y prestaciones).

STARTING POINT ONLY - verify every figure against the official signed
wage table (Tabla de Salarios, MITRADEL registration) and your company's
CSS statement before bidding. Edit this file, or the values in the app,
when the 2026-2029 convention is signed.
"""

CONVENTION = {
    "name": "Convención Colectiva CAPAC-SUNTRACS 2022-2025",
    "step": "Escala vigente desde el 1 de julio de 2025 (prorrogada mientras se negocia 2026-2029)",
}

# Hourly wage by convention category: (private investment, public investment).
# Source: published 2022-2025 agreement summaries, final step July 2025.
CATEGORY_RATES = {
    "Ayudante general": (4.51, 4.67),
    "Principiante": (5.09, 5.25),
    "Calificado": (6.10, 6.30),
}

# Trades loaded by "Load CAPAC-SUNTRACS rates". Codes match the sample data so
# existing crews keep pointing to the same rows.
# (code, trade, category, note)
TRADES = [
    ("HLP", "Ayudante general (helper)", "Ayudante general", ""),
    ("PRI", "Principiante (beginner)", "Principiante", ""),
    ("MAS", "Albañil (mason)", "Calificado", ""),
    ("CAR", "Carpintero (carpenter)", "Calificado", ""),
    ("IRW", "Armador (ironworker)", "Calificado", ""),
    ("PLU", "Plomero (plumber)", "Calificado", ""),
    ("ELE", "Electricista (electrician)", "Calificado", ""),
    ("WEL", "Soldador (welder)", "Calificado", ""),
    ("PNT", "Pintor (painter)", "Calificado", ""),
    ("OPR", "Operador de equipo (equipment operator)", "Calificado",
     "Check the official table: some equipment operators have their own line."),
]

# Burden components. kind:
#   'leave'  - paid time not worked, % of base wage
#   'charge' - contributions & benefits, % of (base wage + paid leave)
# Total burden % = L + (1 + L) x C, where L = sum(leave), C = sum(charges).
BURDEN_COMPONENTS = [
    # (sort, name, kind, percent, notes)
    (10, "Vacaciones", "leave", 9.09,
     "30 days paid per 11 months worked (Código de Trabajo): 1/11."),
    (20, "Feriados nacionales pagados", "leave", 4.00,
     "About 11 paid national holidays over ~275 working days. Adjust to your work calendar."),
    (30, "Incapacidades / licencias (estimate)", "leave", 0.00,
     "Optional allowance for paid sick days and other leave. Set from your own experience."),
    (110, "CSS cuota patronal", "charge", 13.25,
     "Ley 462 de 2025: 13.25% until Feb 2027, then 14.25% (Mar 2027 to Feb 2029)."),
    (120, "Seguro educativo patronal", "charge", 1.50, "1.5% of wages."),
    (130, "Riesgos profesionales", "charge", 5.64,
     "Varies by company risk class (0.56%-5.64%). Use the rate on your CSS statement."),
    (140, "Décimo tercer mes", "charge", 8.33, "1/12 of earnings."),
    (150, "CSS patronal sobre XIII mes", "charge", 0.90,
     "10.75% employer CSS applied to the XIII mes (10.75% x 8.33%)."),
    (160, "Prima de antigüedad", "charge", 1.92,
     "One week's pay per year worked (1/52)."),
    (170, "Beneficios de convención (herramientas, transporte, otros)", "charge", 0.00,
     "Convention benefits not covered above. Fill in from the convention text."),
]


def total_burden(components):
    """components: iterable of dicts with kind, percent, (active). Returns
    (leave_pct, charge_pct, total_pct)."""
    leave = sum(c["percent"] for c in components
                if c.get("active", 1) and c["kind"] == "leave")
    charge = sum(c["percent"] for c in components
                 if c.get("active", 1) and c["kind"] == "charge")
    total = leave + (1 + leave / 100) * charge
    return leave, charge, total
