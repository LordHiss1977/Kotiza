"""Panama labor reference data from the Convención Colectiva CAPAC-SUNTRACS
2022-2025 (copy in the repository: capac-convenio-colectiva-2022-2025.pdf).

  * TRADES        - Cláusulas 125, 126 and 127 wage tables, step of 1 July 2025
  * BURDEN_*      - employer burden: Código de Trabajo, CSS (Ley 462 de 2025)
                    and the convention's own cost clauses
  * RENDIMIENTOS  - Anexo IA, Tabla de Rendimientos Mínimos de Mano de Obra

Update this file when the 2026-2029 convention is signed. Verify figures with
your accountant / CSS statement before bidding.
"""

CONVENTION = {
    "name": "Convención Colectiva CAPAC-SUNTRACS 2022-2025",
    "step": "Salarios a partir del 1 de julio de 2025 (Cl. 125-127), vigentes mientras se negocia 2026-2029",
}

SPECIAL_PROJECT_UPLIFT = 11.0   # Cl. 127: special projects = private-works wage + 11%

# --------------------------------------------------------------------------
# Wages, B/. per hour from 1 July 2025: (code, occupation, group,
# private works Cl.125, public works Cl.126, special projects Cl.127)
# Codes HLP, PRI, MAS, CAR, IRW, PLU, ELE, WEL, PNT, OPR are kept from the
# sample data so existing crews stay linked.
# --------------------------------------------------------------------------
TRADES = [
    # A. Albañil, mosaiquero, azulejero, carpintero y reforzador
    ("HLP", "Peón o ayudante general", "A. Albañil/Carpintero/Reforzador", 4.51, 4.67, 5.01),
    ("PRI", "Principiante (albañil, carpintero, reforzador, electricista, plomero, vidriero, armador de taller)",
     "A. Albañil/Carpintero/Reforzador", 5.09, 5.25, 5.65),
    ("MAS", "Albañil calificado", "A. Albañil/Carpintero/Reforzador", 6.10, 6.30, 6.77),
    ("MOS", "Mosaiquero / azulejero calificado", "A. Albañil/Carpintero/Reforzador", 6.10, 6.30, 6.77),
    ("CAR", "Carpintero calificado", "A. Albañil/Carpintero/Reforzador", 6.10, 6.30, 6.77),
    ("IRW", "Reforzador (acero de refuerzo) calificado", "A. Albañil/Carpintero/Reforzador", 6.10, 6.30, 6.77),
    # B. Cimbrero / gypsero
    ("CIM-P", "Cimbrero / gypsero principiante", "B. Cimbrero/Gypsero", 5.02, 5.18, 5.57),
    ("CIM", "Cimbrero / gypsero calificado", "B. Cimbrero/Gypsero", 5.71, 5.90, 6.34),
    # C-D. Electricista, plomero
    ("ELE", "Electricista calificado", "C. Electricista", 6.17, 6.37, 6.85),
    ("PLU", "Plomero calificado", "D. Plomero", 6.17, 6.37, 6.85),
    # E-G
    ("PNT-P", "Pintor principiante", "E. Pintor", 5.02, 5.18, 5.57),
    ("PNT", "Pintor calificado", "E. Pintor", 5.78, 5.97, 6.42),
    ("PAS", "Pastero", "F. Pastero", 5.17, 5.33, 5.74),
    ("GUA", "Celador o guardián", "G. Celador", 3.86, 3.99, 4.28),
    # H. Agrimensura
    ("TOP", "Instrumentista de 1ra (agrimensura)", "H. Agrimensura", 6.70, 6.93, 7.44),
    ("CAD", "Cadenero", "H. Agrimensura", 4.90, 5.06, 5.44),
    ("PMI", "Porta mira", "H. Agrimensura", 4.76, 4.91, 5.28),
    # I. Operadores
    ("OMZ1", "Operador de mezcladora hasta 7.5 p3 (0.21 m3)", "I. Operadores", 5.46, 5.64, 6.06),
    ("OMZ2", "Operador de mezcladora de más de 7.5 p3", "I. Operadores", 5.54, 5.72, 6.15),
    ("OMC", "Operador de montacarga", "I. Operadores", 5.54, 5.72, 6.15),
    ("OBG", "Operador de carretón motorizado (buggy)", "I. Operadores", 5.39, 5.57, 5.98),
    ("OGR", "Operador de grúa fija", "I. Operadores", 6.32, 6.52, 7.02),
    ("RIG", "Aparejador de carga (rigger)", "I. Operadores", 5.33, 5.50, 5.92),
    ("OP1", "Operador de equipo pesado de 1ra", "I. Operadores", 7.66, 7.92, 8.50),
    ("OPR", "Operador de equipo pesado de 2da (retroexcavadora, cargador, tractor…)", "I. Operadores", 7.01, 7.24, 7.78),
    ("OPL", "Operador de equipo liviano (rodillo, manitou, tractor liviano…)", "I. Operadores", 6.32, 6.52, 7.02),
    # J. Choferes
    ("CHP", "Chofer de camiones pesados", "J. Choferes", 6.33, 6.54, 7.03),
    ("CHL", "Chofer de camiones livianos", "J. Choferes", 5.80, 5.99, 6.44),
    ("CHV", "Chofer de vehículos livianos", "J. Choferes", 5.39, 5.57, 5.98),
    # K. Mecánicos
    ("MEC1", "Mecánico de 1ra", "K. Mecánicos", 7.01, 7.24, 7.78),
    ("MEC2", "Mecánico de 2da", "K. Mecánicos", 5.84, 6.03, 6.48),
    ("LLA", "Llantero", "K. Mecánicos", 5.17, 5.33, 5.74),
    ("ENG", "Engrasador", "K. Mecánicos", 4.84, 4.99, 5.37),
    # L-N. Obras industriales en el campo (*)
    ("ARM1", "Armador de 1ra (obra industrial en campo)", "L. Armadores (industrial)", 7.69, 7.94, 8.54),
    ("ARM2", "Armador de 2da (obra industrial en campo)", "L. Armadores (industrial)", 6.89, 7.11, 7.65),
    ("SOI1", "Soldador de 1ra (obra industrial en campo)", "M. Soldadores (industrial)", 9.65, 9.97, 10.71),
    ("SOI2", "Soldador de 2da (obra industrial en campo)", "M. Soldadores (industrial)", 8.07, 8.34, 8.96),
    ("TUB1", "Tubero de 1ra (obra industrial en campo)", "N. Tuberos (industrial)", 8.68, 8.98, 9.63),
    ("TUB2", "Tubero de 2da (obra industrial en campo)", "N. Tuberos (industrial)", 7.48, 7.73, 8.30),
    # O-P. Taller, estructuras metálicas y mantenimiento (&)
    ("WEL", "Soldador de 1ra (taller / estructuras metálicas)", "O. Soldadores (taller)", 6.44, 6.65, 7.15),
    ("WEL2", "Soldador de 2da (taller / estructuras metálicas)", "O. Soldadores (taller)", 6.10, 6.30, 6.77),
    ("ART", "Armador calificado (taller / estructuras metálicas)", "P. Armadores (taller)", 5.88, 6.08, 6.53),
    # Q. Vidrio y aluminio
    ("VID", "Instalador de vidrios y aluminio calificado", "Q. Vidrio y aluminio", 6.10, 6.30, 6.77),
    # Cl. 115: crew leader gets +14% while acting as jefe de cuadrilla
    ("JCQ", "Jefe de cuadrilla (calificado + 14%, Cl. 115)", "Bonificaciones", 6.95, 7.18, 7.72),
]

# --------------------------------------------------------------------------
# Burden. kind:
#   'leave'  - paid but not worked, % of base wage (L)
#   'charge' - % of (wage + paid leave) (C)
#   'fixed'  - B/. per hour worked, added after the percentages (F)
# Loaded rate = wage x (1 + L + (1 + L) x C) + F
# --------------------------------------------------------------------------
BURDEN_COMPONENTS = [
    # (sort, name, kind, value, notes)
    (10, "Vacaciones", "leave", 9.09,
     "30 days per 11 months worked (Código de Trabajo; Cl. 38): 1/11."),
    (20, "Feriados pagados + Día del Trabajador de la Construcción", "leave", 4.36,
     "11 national holidays + 25 October (Cl. 124) = 12 paid days over ~275 working days."),
    (25, "Bonificación por asistencia (Cl. 114)", "leave", 5.77,
     "12 hours per 26 days worked = 12/(26 x 8). Use 5.13% for 9-hour days. Lost if absent >6 h in a month."),
    (30, "Incapacidades y permisos pagados", "leave", 0.00,
     "Optional: paid sick days, bereavement (Cl. 121), paternity (Cl. 122). Set from experience."),
    (110, "CSS cuota patronal", "charge", 13.25,
     "Ley 462 de 2025: 13.25% until Feb 2027, then 14.25% (Mar 2027 to Feb 2029)."),
    (120, "Seguro educativo patronal", "charge", 1.50, "1.5% of wages."),
    (130, "Riesgos profesionales", "charge", 5.64,
     "Varies by company risk class (0.56%-5.64%). Use the rate on your CSS statement."),
    (140, "Décimo tercer mes", "charge", 8.33, "1/12 of earnings."),
    (150, "CSS patronal sobre XIII mes", "charge", 0.90, "10.75% x 8.33%."),
    (160, "Provisión prima de antigüedad / cesantía", "charge", 1.92,
     "1 week per year (1/52). Cl. 123: obra-determinada workers only qualify after 5+ years ending in "
     "retirement or invalidity; Cl. 21: 6% cesantía only if a tribunal rules a dismissal unjust. "
     "Set to 0 for project crews if you accept that risk."),
    (210, "Póliza colectiva de vida (Cl. 81)", "fixed", 0.02,
     "Employer pays half of up to B/.8.20/month = B/.4.10 / ~208 h per month."),
    (220, "Uniformes: 5 suéteres + 3 pantalones al año (Cl. 43)", "fixed", 0.03,
     "About B/.75 per worker per year / ~2,500 h. Set from your supplier price."),
]


def total_burden(components):
    """components: dicts with kind, percent, active.
    Returns (leave_pct, charge_pct, total_pct, fixed_per_hour)."""
    act = [c for c in components if c.get("active", 1)]
    leave = sum(c["percent"] for c in act if c["kind"] == "leave")
    charge = sum(c["percent"] for c in act if c["kind"] == "charge")
    fixed = sum(c["percent"] for c in act if c["kind"] == "fixed")
    return leave, charge, leave + (1 + leave / 100) * charge, fixed


# Convention costs that belong in other parts of an estimate (shown as guidance).
OTHER_CONVENTION_COSTS = [
    "Herramientas (Cl. 70-71): the company supplies tools, or rents the worker's own at the monthly rates in Cl. 70. Covered by the 'Small tools & PPE' indirect.",
    "Aporte educacional SUNTRACS (Cl. 119): B/.80-310 per month per company depending on headcount. Added to the indirect library.",
    "Agua fría o hielo (Cl. 42), equipo de seguridad (Cl. 99): site indirects.",
    "Condiciones especiales (Cl. 48-53): work at height +16% (up to 125 m) / +20% (above), excavation, tunnels, jackhammer. Apply to the affected tasks.",
    "Lluvia (Cl. 39): +50% while working in rain over 30 minutes. Paid stoppages per Art. 280 of the Código de Trabajo.",
    "Trabajadores permanentes (Cl. 129): at least 6% above the convention minimum.",
    "Proyectos especiales (Cl. 127): Metro lines, 4th bridge over the Canal, Costanera Sur, Changuinola II, Panamá-David train = private wage + 11%.",
]

INDIRECT_ITEMS = [
    # (description, category, method, unit, rate, percent)
    ("Aporte educacional SUNTRACS (Cl. 119)", "Convención", "lump", "month", 80.0, 0.0),
]

# --------------------------------------------------------------------------
# Anexo IA - Rendimientos mínimos (per 8-hour day for the skilled worker and
# their helpers). Values are the contractual MINIMUM ("rendimiento vigente");
# the second figure is the threshold agreed for production bonuses.
# --------------------------------------------------------------------------
LB_TO_KG = 0.45359

# Crews matching the convention's "personal base": (code, name, [(labor code, qty)])
RENDIMIENTO_CREWS = [
    ("CV-PEON", "Peón (rendimiento)", [("HLP", 1)]),
    ("CV-REF", "Reforzador + 1 peón", [("IRW", 1), ("HLP", 1)]),
    ("CV-CAR1", "Carpintero + 1 peón", [("CAR", 1), ("HLP", 1)]),
    ("CV-CAR", "Carpintero solo", [("CAR", 1)]),
    ("CV-ALB100", "Albañil + 1.00 peón", [("MAS", 1), ("HLP", 1)]),
    ("CV-ALB50", "Albañil + 0.50 peón", [("MAS", 1), ("HLP", 0.5)]),
    ("CV-ALB40", "Albañil + 0.40 peón", [("MAS", 1), ("HLP", 0.4)]),
    ("CV-ALB33", "Albañil + 0.33 peón", [("MAS", 1), ("HLP", 0.33)]),
    ("CV-ALB25", "Albañil + 0.25 peón", [("MAS", 1), ("HLP", 0.25)]),
    ("CV-MOS50", "Mosaiquero-azulejero + 0.50 peón", [("MOS", 1), ("HLP", 0.5)]),
    ("CV-MOS33", "Mosaiquero-azulejero + 0.33 peón", [("MOS", 1), ("HLP", 0.33)]),
    ("CV-MOS25", "Mosaiquero-azulejero + 0.25 peón", [("MOS", 1), ("HLP", 0.25)]),
]

# (code, category, description, condition, crew, unit, minimum/day, bonus threshold/day)
RENDIMIENTOS = [
    ("RM-A1", "A. Movimiento de tierra", "Excavación a mano (pico y pala) de zanjas y fundaciones, en arcilla",
     "Hasta 1.60 m de profundidad. Tabla: 2.567 m3 ó 14.26 ml de zanja 30x60 cm", "CV-PEON", "m3", 2.567, 2.723),
    ("RM-A2", "A. Movimiento de tierra", "Excavación a mano (pico y pala) de zanjas y fundaciones, en tosca suave",
     "Hasta 1.60 m de profundidad. Tabla: 1.643 m3 ó 9.13 ml de zanja 30x60 cm", "CV-PEON", "m3", 1.643, 1.742),
    ("RM-B1.1", "B. Refuerzo", "Acero de refuerzo, corte y doblado (cualquier diámetro)",
     "40% de la operación completa. Tabla: 1,828.4 lb/día", "CV-REF", "kg", 1828.4 * LB_TO_KG, 1913.01 * LB_TO_KG),
    ("RM-B1.2", "B. Refuerzo", "Acero de refuerzo, colocación incl. estribos (cualquier diámetro)",
     "60% de la operación completa. Tabla: 1,218.90 lb/día", "CV-REF", "kg", 1218.90 * LB_TO_KG, 1275.34 * LB_TO_KG),
    ("RM-B1.3", "B. Refuerzo", "Acero de refuerzo, corte, doblado y colocación (cualquier diámetro)",
     "100% de la operación. Tabla: 732.06 lb/día", "CV-REF", "kg", 732.06 * LB_TO_KG, 765.93 * LB_TO_KG),
    ("RM-C1.1", "C. Carpintería", "Formaleta de vigas hasta 50 cm de ancho y 80 cm de alto (madera)",
     "Fondo y costados de madera, 3.00 m piso a fondo de viga, muletillas ≥45 cm", "CV-CAR1", "m2", 12.72, 13.31),
    ("RM-C1.2", "C. Carpintería", "Formaleta de vigas de más de 50 cm de ancho y 80 cm de alto (madera)",
     "Fondo y costados de madera, 3.00 m piso a fondo de viga, muletillas ≤45 cm", "CV-CAR1", "m2", 11.56, 12.10),
    ("RM-C2.1", "C. Carpintería", "Formaleta de columnas hasta 60x60 cm (madera)",
     "Escuadras a ≥50 cm con arriostramiento", "CV-CAR1", "m2", 15.03, 15.73),
    ("RM-C2.2", "C. Carpintería", "Formaleta de columnas de más de 60x60 cm (madera)",
     "Escuadras a ≤40 cm con arriostramiento", "CV-CAR1", "m2", 16.19, 16.94),
    ("RM-C3.1", "C. Carpintería", "Formaleta de losa sólida sobre pares y puntales de madera",
     "Forro de madera, tablero prefabricado o plywood", "CV-CAR1", "m2", 16.54, 17.30),
    ("RM-C3.2", "C. Carpintería", "Formaleta de losa sólida sobre pares de madera y puntales metálicos",
     "Forro de madera, tablero prefabricado o plywood", "CV-CAR1", "m2", 17.87, 18.70),
    ("RM-C3.3", "C. Carpintería", "Formaleta de losa sólida sobre vigas y puntales metálicos",
     "Forro de madera, tablero prefabricado o plywood", "CV-CAR1", "m2", 18.40, 19.25),
    ("RM-C4.1", "C. Carpintería", "Entablado discontinuo, pares y puntales de madera (losa de viguetas)",
     "Losa con viguetas vaciadas en obra", "CV-CAR1", "m2", 18.92, 19.80),
    ("RM-C4.2", "C. Carpintería", "Entablado discontinuo, pares de madera y puntales metálicos (losa de viguetas)",
     "Losa con viguetas vaciadas en obra", "CV-CAR1", "m2", 20.50, 21.45),
    ("RM-C4.3", "C. Carpintería", "Entablado discontinuo, pares y puntales metálicos (losa de viguetas)",
     "Losa con viguetas vaciadas en obra", "CV-CAR1", "m2", 21.03, 22.00),
    ("RM-C5.1", "C. Carpintería", "Techo de lámina metálica corrugada sobre pares de madera",
     "Lámina clavada sobre pares de madera", "CV-CAR1", "m2", 22.08, 23.10),
    ("RM-C5.2", "C. Carpintería", "Techo de lámina de asbesto-cemento sobre pares de madera",
     "Láminas onduladas clavadas o con ganchos", "CV-CAR1", "m2", 15.73, 16.46),
    ("RM-C5.3", "C. Carpintería", "Techo con forro de madera machimbrada sobre pares de madera",
     "Machimbre 1\" x 6\" clavado a pares", "CV-CAR1", "m2", 14.34, 15.00),
    ("RM-C6.1", "C. Carpintería", "Cielorraso de celotex en pares de madera, siguiendo la inclinación",
     "Clavado a la parte inferior de los pares", "CV-CAR1", "m2", 21.03, 22.00),
    ("RM-C6.2", "C. Carpintería", "Cielorraso de madera machimbrada en pares, siguiendo la inclinación",
     "Clavado a la parte inferior de los pares", "CV-CAR1", "m2", 15.03, 15.73),
    ("RM-C6.3", "C. Carpintería", "Cielorraso de plywood en pares, siguiendo la inclinación",
     "Clavado a la parte inferior de los pares", "CV-CAR1", "m2", 36.80, 38.50),
    ("RM-C7.1", "C. Carpintería", "Cielorraso de celotex sobre entramado horizontal de madera",
     "Clavado, horizontal y a nivel", "CV-CAR1", "m2", 12.09, 12.65),
    ("RM-C7.2", "C. Carpintería", "Cielorraso de plywood sobre entramado horizontal de madera",
     "Clavado, horizontal y a nivel", "CV-CAR1", "m2", 12.09, 12.65),
    ("RM-C7.3", "C. Carpintería", "Cielorraso machimbrado sobre entramado horizontal de 2\"",
     "Clavado, horizontal y a nivel", "CV-CAR1", "m2", 10.51, 11.00),
    ("RM-C7.4", "C. Carpintería", "Cielorraso machimbrado sobre entramado horizontal de 6\"",
     "Clavado, horizontal y a nivel", "CV-CAR1", "m2", 14.72, 15.40),
    ("RM-C8.1", "C. Carpintería", "Colocación de puerta de madera o plywood en marco de madera",
     "Incluye batientes, molduras, bisagras y cerradura simple", "CV-CAR", "und", 3.15, 3.30),
    ("RM-C8.2", "C. Carpintería", "Colocación de marco de madera o metal (vano de puerta)",
     "", "CV-CAR", "und", 9.46, 9.90),
    ("RM-D1.1", "D. Albañilería", "Muro de bloque de concreto 4\" relleno, sin refuerzo",
     "En fundaciones, sin repello ni juntas cogidas", "CV-ALB100", "m2", 9.46, 9.90),
    ("RM-D1.2", "D. Albañilería", "Muro de bloque de concreto 6\" relleno, sin refuerzo",
     "En fundaciones, sin repello ni juntas cogidas", "CV-ALB100", "m2", 8.41, 8.80),
    ("RM-D1.3", "D. Albañilería", "Muro de bloque de concreto 8\" relleno, sin refuerzo",
     "En fundaciones, sin repello ni juntas cogidas", "CV-ALB100", "m2", 8.41, 8.80),
    ("RM-D1.4", "D. Albañilería", "Muro de bloque de arcilla 4\" relleno, sin refuerzo",
     "En fundaciones, sin repello ni juntas cogidas", "CV-ALB100", "m2", 10.51, 11.00),
    ("RM-D1.5", "D. Albañilería", "Muro de bloque de arcilla 6\" relleno, sin refuerzo",
     "En fundaciones, sin repello ni juntas cogidas", "CV-ALB100", "m2", 9.46, 9.90),
    ("RM-D1.6", "D. Albañilería", "Muro de bloque de arcilla 8\" relleno, sin refuerzo",
     "En fundaciones, sin repello ni juntas cogidas", "CV-ALB100", "m2", 8.41, 8.80),
    ("RM-D2.1", "D. Albañilería", "Muro de bloque de concreto 6\" relleno, reforzado",
     "En fundaciones, sin repello ni juntas cogidas", "CV-ALB100", "m2", 6.31, 6.60),
    ("RM-D2.2", "D. Albañilería", "Muro de bloque de concreto 8\" relleno, reforzado",
     "En fundaciones, sin repello ni juntas cogidas", "CV-ALB100", "m2", 5.26, 5.50),
    ("RM-D3.1", "D. Albañilería", "Pared de bloque de concreto 3\", 4\" o 6\"",
     "Paredes de cualquier tipo", "CV-ALB50", "m2", 14.46, 15.13),
    ("RM-D3.4", "D. Albañilería", "Pared de bloque de concreto 8\"",
     "Paredes de cualquier tipo", "CV-ALB50", "m2", 11.56, 12.10),
    ("RM-D3.5", "D. Albañilería", "Pared de bloque de arcilla 3\", 4\" o 6\"",
     "Paredes de cualquier tipo", "CV-ALB50", "m2", 17.87, 18.70),
    ("RM-D3.8", "D. Albañilería", "Pared de bloque de arcilla 8\"",
     "Paredes de cualquier tipo", "CV-ALB50", "m2", 13.88, 14.52),
    ("RM-D4.1", "D. Albañilería", "Pared de bloque de concreto 4\", una cara limpia (junta cogida lisa)",
     "Habitaciones, cercas, muros", "CV-ALB50", "m2", 12.62, 13.20),
    ("RM-D4.2", "D. Albañilería", "Pared de bloque de concreto 6\", una cara limpia (junta cogida lisa)",
     "Habitaciones, cercas, muros", "CV-ALB50", "m2", 11.56, 12.10),
    ("RM-D5.1", "D. Albañilería", "Pared de bloque de concreto 4\", dos caras limpias",
     "Habitaciones, cercas, muros", "CV-ALB50", "m2", 9.46, 9.90),
    ("RM-D5.2", "D. Albañilería", "Pared de bloque de concreto 6\", dos caras limpias",
     "Habitaciones, cercas, muros", "CV-ALB50", "m2", 9.20, 9.63),
    ("RM-D6.1", "D. Albañilería", "Repello liso de cielorraso sobre bloque de arcilla",
     "Altura de trabajo 3.05 m sobre losa", "CV-ALB40", "m2", 13.30, 13.92),
    ("RM-D6.2", "D. Albañilería", "Repello liso de cielorraso sobre bloque de concreto o losa sólida",
     "Altura de trabajo 3.05 m sobre losa", "CV-ALB40", "m2", 15.03, 15.73),
    ("RM-D7.1", "D. Albañilería", "Gotero repellado", "En losa de cualquier tipo", "CV-ALB25", "ml", 21.03, 22.00),
    ("RM-D7.2", "D. Albañilería", "Repello de fascia", "Incluye los bordes", "CV-ALB25", "ml", 21.03, 22.00),
    ("RM-D8.1", "D. Albañilería", "Repello rayado o liso de paredes interiores y exteriores",
     "Incluye andamios ligeros hasta 3.05 m", "CV-ALB50", "m2", 18.50, 19.36),
    ("RM-D9.1", "D. Albañilería", "Repello de mochetas sin marco colocado",
     "Incluye las dos esquinas de vanos y bordes de machones", "CV-ALB33", "ml", 19.66, 20.57),
    ("RM-D9.2", "D. Albañilería", "Repello de mochetas con marco colocado",
     "", "CV-ALB33", "ml", 25.23, 26.40),
    ("RM-D10.1", "D. Albañilería", "Repello de vigas hasta 30x30 cm", "Alturas hasta 3.05 m, acabado con flota o llana",
     "CV-ALB33", "m2", 9.99, 10.45),
    ("RM-D10.2", "D. Albañilería", "Repello de vigas de más de 30x30 cm", "Alturas hasta 3.05 m, acabado con flota o llana",
     "CV-ALB33", "m2", 12.09, 12.65),
    ("RM-D10.3", "D. Albañilería", "Repello de columnas hasta 30x30 cm", "Altura de trabajo 3.05 m",
     "CV-ALB33", "m2", 9.99, 10.45),
    ("RM-D10.4", "D. Albañilería", "Repello de columnas de más de 30x30 cm", "Altura de trabajo 3.05 m",
     "CV-ALB33", "m2", 11.56, 12.10),
    ("RM-D11", "D. Albañilería", "Piso de azulejo y cerámica",
     "Sobre piso de concreto o losa, ambientes mayores de 1.25 m2", "CV-MOS33", "m2", 7.52, 7.87),
    ("RM-D13", "D. Albañilería", "Piso de cemento pulido gris o coloreado (llana de metal)",
     "Mezcla preparada y transportada por otros", "CV-ALB33", "m2", 18.92, 19.80),
    ("RM-D14", "D. Albañilería", "Piso de baldosa de pasta o granito (no incluye 50x50 cm)",
     "Sobre piso de concreto o losa", "CV-MOS50", "m2", 19.34, 20.24),
    ("RM-D15", "D. Albañilería", "Paso y espejo de escalera con baldosa de pasta o granito",
     "Con mezcla de cemento", "CV-MOS50", "ml", 4.63, 4.84),
    ("RM-D16.1", "D. Albañilería", "Base de baldosa en escalera, solo en el paso", "Colocación corriente",
     "CV-MOS25", "ml", 20.81, 21.78),
    ("RM-D16.2", "D. Albañilería", "Base de baldosa en escalera, paso y espejo", "Colocación corriente",
     "CV-MOS25", "ml", 20.81, 21.78),
    ("RM-D16.3", "D. Albañilería", "Base de baldosa en escalera siguiendo la pendiente, con cartabón",
     "Colocación corriente", "CV-MOS50", "ml", 11.56, 12.10),
    ("RM-D17", "D. Albañilería", "Revestimiento con azulejo", "Zócalos, paredes y superficies en general",
     "CV-MOS33", "m2", 11.04, 11.55),
    ("RM-D18", "D. Albañilería", "Revestimiento con cerámica", "Zócalos, paredes y superficies en general",
     "CV-MOS33", "m2", 11.04, 11.55),
    ("RM-D19", "D. Albañilería", "Base de baldosa de pasta o granito", "", "CV-MOS25", "ml", 24.29, 25.41),
    ("RM-D20.1", "D. Albañilería", "Colocación de ventana de 0.50 a 1.50 m2",
     "Con anclajes, a nivel y aplomo, cuñas de mortero o madera", "CV-ALB33", "und", 12.62, 13.20),
    ("RM-D20.2", "D. Albañilería", "Colocación de ventana de 1.50 a 3.00 m2",
     "Con anclajes, a nivel y aplomo, cuñas de mortero o madera", "CV-ALB33", "und", 10.51, 11.00),
]
