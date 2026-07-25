"""Crime-type groupings shared across the analytics engine. Mirrors the
categories used in scripts/data_generation/crime_type_profiles.py."""

VIOLENT_TYPES = {
    "MURDER", "ATTEMPT_TO_MURDER", "CULPABLE_HOMICIDE", "RAPE", "DACOITY",
    "ROBBERY", "RIOTS", "HURT_GRIEVOUS_HURT", "DOWRY_DEATH", "ASSAULT_ON_WOMEN_MODESTY",
}

PROPERTY_TYPES = {
    "THEFT", "AUTO_THEFT", "OTHER_THEFT", "BURGLARY", "ROBBERY", "DACOITY", "CRIMINAL_BREACH_OF_TRUST",
}

UNRESOLVED_STATUSES = {"UNDER_INVESTIGATION", "TRIAL"}
