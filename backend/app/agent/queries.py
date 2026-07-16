# Requêtes orientées annonces de projets en amont (investissement, implantation,
# lancement) plutôt que livraisons / chantiers en cours (inauguration, ouverture).
SECTOR_QUERIES_FR = {
    "logistique": (
        "article annonce investissement implantation entrepôt logistique "
        "plateforme distribution {dept_name} département {dept_code} "
        "({dept_label}) France nouveau projet extension 2026 2027"
    ),
    "industriel": (
        "article annonce investissement implantation nouvelle usine "
        "site industriel {dept_name} département {dept_code} "
        "({dept_label}) France lancement projet extension 2026 2027"
    ),
    "retail": (
        "article annonce investissement implantation nouveau centre commercial "
        "retail {dept_name} département {dept_code} ({dept_label}) France"
        " projet extension 2026 2027"
    ),
}

SECTOR_QUERIES_DE = {
    "logistique": (
        "Artikel Investition Logistikzentrum Lagerhalle Distribution "
        "{dept_name} Bundesland {dept_code} ({dept_label}) Deutschland"
        " neues Projekt Erweiterung 2026 2027"
    ),
    "industriel": (
        "Artikel Investition neue Fabrik Industriestandort "
        "{dept_name} Bundesland {dept_code} ({dept_label}) Deutschland"
        " Projektstart Erweiterung 2026 2027"
    ),
    "retail": (
        "Artikel Investition neues Einkaufszentrum Retail "
        "{dept_name} Bundesland {dept_code} ({dept_label}) Deutschland"
        " Projekt Erweiterung 2026 2027"
    ),
}

SECTOR_QUERIES_BY_COUNTRY = {
    "FR": SECTOR_QUERIES_FR,
    "DE": SECTOR_QUERIES_DE,
    "GB": {
        "logistique": (
            "article announces investment logistics warehouse distribution centre "
            "{dept_name} region {dept_code} ({dept_label}) United Kingdom "
            "new project extension 2026 2027"
        ),
        "industriel": (
            "article announces investment new factory industrial site "
            "{dept_name} region {dept_code} ({dept_label}) United Kingdom "
            "project launch extension 2026 2027"
        ),
        "retail": (
            "article announces investment new retail park shopping centre "
            "{dept_name} region {dept_code} ({dept_label}) United Kingdom "
            "project extension 2026 2027"
        ),
    },
    "IE": {
        "logistique": (
            "article announces investment logistics warehouse distribution centre "
            "{dept_name} province {dept_code} ({dept_label}) Ireland "
            "new project extension 2026 2027"
        ),
        "industriel": (
            "article announces investment new factory industrial site "
            "{dept_name} province {dept_code} ({dept_label}) Ireland "
            "project launch extension 2026 2027"
        ),
        "retail": (
            "article announces investment new retail park shopping centre "
            "{dept_name} province {dept_code} ({dept_label}) Ireland "
            "project extension 2026 2027"
        ),
    },
}

# Backward compatibility
SECTOR_QUERIES = SECTOR_QUERIES_FR
