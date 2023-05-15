def order_dict(sql_id, key, values):
    d = values
    if sql_id == 16 and key == "personnes":
        d = {
          "chefVillage": None,
          "contactChefVillage": None,
          "presidentCVD": None,
          "contactPresidentCVD": None,
          "tresorierCVD": None,
          "contactTresorierCVD": None,
          "secretaireCVD": None,
          "contactSecretaireCVD": None,
          "responsableJeunes": None,
          "contactResponsableJeunes": None,
          "responsableFemmes": None,
          "contactResponsableFemmes": None,
          "asc": None,
          "contactasc": None,
          "infirmier": None,
          "contactInfirmier": None
        }
        for k, v in values.items():
            d[k] = v
        
    return d