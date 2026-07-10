"""Skill: convert a value between common units (length, weight, temperature)."""

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "convert_units",
        "description": (
            "Convert a numeric value between units of length, weight, or "
            "temperature. Supported length: m, km, cm, mm, mile, ft, in. "
            "Supported weight: kg, g, lb, oz. Supported temperature: c, f, k."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "value": {"type": "number", "description": "The numeric value to convert"},
                "from_unit": {"type": "string", "description": "Unit to convert from, e.g. 'km'"},
                "to_unit": {"type": "string", "description": "Unit to convert to, e.g. 'mile'"},
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    },
}

# All length factors relative to meters
_LENGTH_TO_METERS = {
    "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
    "mile": 1609.344, "ft": 0.3048, "in": 0.0254,
}

# All weight factors relative to kilograms
_WEIGHT_TO_KG = {
    "kg": 1.0, "g": 0.001, "lb": 0.45359237, "oz": 0.028349523125,
}


def _convert_temperature(value, from_unit, to_unit):
    # Normalize to Celsius first, then to target
    if from_unit == "c":
        celsius = value
    elif from_unit == "f":
        celsius = (value - 32) * 5 / 9
    elif from_unit == "k":
        celsius = value - 273.15
    else:
        return None

    if to_unit == "c":
        return celsius
    elif to_unit == "f":
        return celsius * 9 / 5 + 32
    elif to_unit == "k":
        return celsius + 273.15
    return None


def run(value: float, from_unit: str, to_unit: str) -> str:
    from_unit = from_unit.strip().lower()
    to_unit = to_unit.strip().lower()

    if from_unit == to_unit:
        return f"{value} {from_unit} = {value} {to_unit} (same unit)"

    # Temperature
    if from_unit in ("c", "f", "k") and to_unit in ("c", "f", "k"):
        result = _convert_temperature(value, from_unit, to_unit)
        return f"{value} {from_unit.upper()} = {round(result, 2)} {to_unit.upper()}"

    # Length
    if from_unit in _LENGTH_TO_METERS and to_unit in _LENGTH_TO_METERS:
        meters = value * _LENGTH_TO_METERS[from_unit]
        result = meters / _LENGTH_TO_METERS[to_unit]
        return f"{value} {from_unit} = {round(result, 4)} {to_unit}"

    # Weight
    if from_unit in _WEIGHT_TO_KG and to_unit in _WEIGHT_TO_KG:
        kg = value * _WEIGHT_TO_KG[from_unit]
        result = kg / _WEIGHT_TO_KG[to_unit]
        return f"{value} {from_unit} = {round(result, 4)} {to_unit}"

    return (
        f"Error: cannot convert between '{from_unit}' and '{to_unit}' -- "
        f"unsupported unit or mismatched category (length/weight/temperature)."
    )
