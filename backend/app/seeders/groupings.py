"""
Hardcoded country groupings (ISO alpha-2 codes).
These change rarely — update manually when membership changes.
Sources: official org websites, verified Feb 2026.
"""

G7 = {"US", "CA", "GB", "FR", "DE", "IT", "JP"}

G20 = {
    "AR", "AU", "BR", "CA", "CN", "FR", "DE", "IN", "ID",
    "IT", "JP", "MX", "RU", "SA", "ZA", "KR", "TR", "GB", "US",
    # EU is the 20th member but represented by individual states above
}

EU = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
}

EUROZONE = {
    "AT", "BE", "HR", "CY", "EE", "FI", "FR", "DE", "GR", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PT", "SK", "SI", "ES",
}

NATO = {
    "AL", "BE", "BG", "CA", "HR", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IS", "IT", "LV", "LT", "LU", "ME", "NL",
    "MK", "NO", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "TR",
    "GB", "US",
}

# OPEC members as of 2026 (Iraq, Iran, Kuwait, Libya, Nigeria, Saudi Arabia,
# UAE, Venezuela, Gabon, Equatorial Guinea, Congo, Algeria)
OPEC = {"IQ", "IR", "KW", "LY", "NG", "SA", "AE", "VE", "GA", "GQ", "CG", "DZ"}

# BRICS + new members admitted 2024 (Egypt, Ethiopia, Iran, UAE, Saudi Arabia)
BRICS = {"BR", "RU", "IN", "CN", "ZA", "EG", "ET", "IR", "AE", "SA"}

ASEAN = {"BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "VN"}

OECD = {
    "AU", "AT", "BE", "CA", "CL", "CO", "CR", "CZ", "DK", "EE",
    "FI", "FR", "DE", "GR", "HU", "IS", "IE", "IL", "IT", "JP",
    "KR", "LV", "LT", "LU", "MX", "NL", "NZ", "NO", "PL", "PT",
    "SK", "SI", "ES", "SE", "CH", "TR", "GB", "US",
}

COMMONWEALTH = {
    "AG", "AU", "BS", "BD", "BB", "BZ", "BW", "BN", "CM", "CA",
    "CY", "DM", "SZ", "FJ", "GH", "GD", "GY", "IN", "JM", "KE",
    "KI", "LS", "MW", "MY", "MV", "MT", "MU", "MZ", "NA", "NR",
    "NZ", "NG", "PK", "PW", "PG", "RW", "KN", "LC", "VC", "WS",
    "SC", "SL", "SB", "ZA", "LK", "TZ", "TO", "TT", "TV", "UG",
    "GB", "VU", "ZM",
}

# G20 countries for MVP priority seeding
G20_PRIORITY = G20
