# Requêtes orientées annonces de projets en amont (investissement, implantation,
# lancement) plutôt que livraisons / chantiers en cours (inauguration, ouverture).
SECTOR_QUERIES_FR = {
    "logistique": (
        "article annonce investissement implantation entrepôt logistique "
        "plateforme distribution {dept_name} département {dept_code} "
        "({dept_label}){anchor_segment} nouveau projet extension 2026 2027"
    ),
    "industriel": (
        "article annonce investissement implantation nouvelle usine "
        "site industriel {dept_name} département {dept_code} "
        "({dept_label}){anchor_segment} lancement projet extension 2026 2027"
    ),
    "retail": (
        "article annonce investissement implantation nouveau centre commercial "
        "retail {dept_name} département {dept_code} ({dept_label})"
        "{anchor_segment} projet extension 2026 2027"
    ),
}

SECTOR_QUERIES_DE = {
    "logistique": (
        "Artikel Investition Logistikzentrum Lagerhalle Distribution "
        "{dept_name} Bundesland {dept_code} ({dept_label})"
        "{anchor_segment} neues Projekt Erweiterung 2026 2027"
    ),
    "industriel": (
        "Artikel Investition neue Fabrik Industriestandort "
        "{dept_name} Bundesland {dept_code} ({dept_label})"
        "{anchor_segment} Projektstart Erweiterung 2026 2027"
    ),
    "retail": (
        "Artikel Investition neues Einkaufszentrum Retail "
        "{dept_name} Bundesland {dept_code} ({dept_label})"
        "{anchor_segment} Projekt Erweiterung 2026 2027"
    ),
}

SECTOR_QUERIES_BY_COUNTRY = {
    "FR": SECTOR_QUERIES_FR,
    "DE": SECTOR_QUERIES_DE,
}

# Backward compatibility
SECTOR_QUERIES = SECTOR_QUERIES_FR
