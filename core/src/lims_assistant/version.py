"""Zentrale Versionskonstanten."""

APP_VERSION = "0.4.0"

# Version der JSON-Jobvertraege (request/progress/response).
SCHEMA_VERSION = "1.0"

# Version des SQLite-Schemas (siehe store/db.py MIGRATIONS).
DB_SCHEMA_VERSION = 1

# Version der Normalisierungsregeln; wird in FieldProposals protokolliert,
# damit Aenderungen an Vokabular/Regeln nachvollziehbar bleiben.
NORMALIZER_VERSION = "norm-1.0"

# Version des leichten Lernkerns (TF-IDF-Index + Zeilendetektor).
LEARNER_VERSION = "learn-1.0"
