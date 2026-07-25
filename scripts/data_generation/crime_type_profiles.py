"""Per-crime-type metadata: IPC section, narrative templates, and flags
controlling which optional fields apply (weapon, property value)."""

IPC_SECTION = {
    "MURDER": "302 IPC",
    "ATTEMPT_TO_MURDER": "307 IPC",
    "CULPABLE_HOMICIDE": "304 IPC",
    "RAPE": "376 IPC",
    "KIDNAPPING_ABDUCTION": "363 IPC",
    "DACOITY": "395 IPC",
    "ROBBERY": "392 IPC",
    "BURGLARY": "457/380 IPC",
    "THEFT": "379 IPC",
    "AUTO_THEFT": "379 IPC (Motor Vehicle)",
    "OTHER_THEFT": "379 IPC",
    "RIOTS": "147/148 IPC",
    "CRIMINAL_BREACH_OF_TRUST": "406 IPC",
    "CHEATING": "420 IPC",
    "ARSON": "435 IPC",
    "HURT_GRIEVOUS_HURT": "323/325 IPC",
    "DOWRY_DEATH": "304B IPC",
    "ASSAULT_ON_WOMEN_MODESTY": "354 IPC",
    "CRUELTY_BY_HUSBAND_RELATIVES": "498A IPC",
    "DEATH_BY_NEGLIGENCE": "304A IPC",
    "OTHER_IPC_CRIMES": "Other IPC sections",
}

PROPERTY_CRIME_TYPES = {
    "THEFT", "AUTO_THEFT", "OTHER_THEFT", "BURGLARY", "ROBBERY", "DACOITY", "CRIMINAL_BREACH_OF_TRUST",
}

WEAPON_RELEVANT_TYPES = {
    "MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "DACOITY", "ROBBERY", "RIOTS", "HURT_GRIEVOUS_HURT",
}

WEAPONS = ["Knife", "Country-made pistol", "Iron rod", "Sickle", "Blunt object", "Firearm", "Sharp weapon"]

# Crimes tracked as "against the person" get a relationship_to_victim field
# sampled from the calibrated offender_relationship_mix; pure property/financial
# crimes against strangers/institutions are left null.
RELATIONSHIP_APPLICABLE_TYPES = {
    "MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "RAPE", "KIDNAPPING_ABDUCTION",
    "HURT_GRIEVOUS_HURT", "DOWRY_DEATH", "ASSAULT_ON_WOMEN_MODESTY", "CRUELTY_BY_HUSBAND_RELATIVES",
}

DESCRIPTION_TEMPLATES = {
    "MURDER": "{victim} found dead with injuries consistent with homicide near {location}.",
    "ATTEMPT_TO_MURDER": "{victim} sustained life-threatening injuries in an attack near {location}.",
    "CULPABLE_HOMICIDE": "{victim} died following an altercation near {location}.",
    "RAPE": "{victim} reported sexual assault by {accused_desc} near {location}.",
    "KIDNAPPING_ABDUCTION": "{victim} reported as abducted from {location}.",
    "DACOITY": "Armed gang robbed {victim} of valuables near {location}.",
    "ROBBERY": "{victim} robbed at {location}, valuables taken by force.",
    "BURGLARY": "House belonging to {victim} broken into at {location}; property stolen.",
    "THEFT": "{victim} reported theft of personal property near {location}.",
    "AUTO_THEFT": "{victim}'s vehicle stolen from near {location}.",
    "OTHER_THEFT": "{victim} reported theft of property from {location}.",
    "RIOTS": "Unlawful assembly and rioting reported near {location}, {victim} among affected parties.",
    "CRIMINAL_BREACH_OF_TRUST": "{victim} alleges misappropriation of entrusted property by {accused_desc}.",
    "CHEATING": "{victim} reports being defrauded by {accused_desc} near {location}.",
    "ARSON": "Fire deliberately set to property belonging to {victim} at {location}.",
    "HURT_GRIEVOUS_HURT": "{victim} sustained injuries following assault by {accused_desc} near {location}.",
    "DOWRY_DEATH": "Unnatural death of {victim} reported, dowry harassment alleged against {accused_desc}.",
    "ASSAULT_ON_WOMEN_MODESTY": "{victim} reports assault with intent to outrage modesty by {accused_desc} near {location}.",
    "CRUELTY_BY_HUSBAND_RELATIVES": "{victim} alleges sustained cruelty by {accused_desc}.",
    "DEATH_BY_NEGLIGENCE": "{victim} died due to alleged negligence near {location}.",
    "OTHER_IPC_CRIMES": "{victim} filed a complaint regarding an incident near {location}.",
}

NARRATIVE_TEMPLATES = {
    "MURDER": (
        "On {date} at approximately {time}, a complaint was lodged at {police_station} regarding the death "
        "of {victim}, aged {victim_age}, whose body was discovered near {location}. Preliminary investigation "
        "indicates injuries consistent with assault. {accused_clause} The matter is registered under {ipc_section} "
        "and is {status_clause}."
    ),
    "THEFT": (
        "On {date} at approximately {time}, {victim}, aged {victim_age}, reported the theft of personal property "
        "near {location} within the jurisdiction of {police_station}. {accused_clause} The case is registered "
        "under {ipc_section} and is {status_clause}."
    ),
    "CHEATING": (
        "On {date}, {victim}, aged {victim_age}, filed a complaint at {police_station} alleging financial fraud "
        "amounting to approximately Rs. {property_value} near {location}. {accused_clause} Registered under "
        "{ipc_section}, the matter is {status_clause}."
    ),
    "DEFAULT": (
        "On {date} at approximately {time}, a complaint was registered at {police_station} by or on behalf of "
        "{victim}, aged {victim_age}, in connection with an incident near {location}. {accused_clause} "
        "The case is registered under {ipc_section} and is {status_clause}."
    ),
}

STATUS_CLAUSE = {
    "UNDER_INVESTIGATION": "currently under investigation",
    "CHARGESHEETED": "at the chargesheet stage",
    "TRIAL": "pending trial before the competent court",
    "CONVICTED": "concluded with a conviction",
    "ACQUITTED": "concluded with an acquittal",
    "CLOSED": "closed as untraced/unsubstantiated",
}
