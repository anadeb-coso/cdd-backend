import unicodedata
import re


def safe_get(lst, index, default={}):
    try:
        return {k: v for k, v in lst[index].items() if v is not None}
    except IndexError:
        return default
    


def normaliser_chaine(chaine):
    chaine = chaine.upper() # Mettre en majuscule
    
    chaine = ''.join(
        c for c in unicodedata.normalize('NFD', chaine)
        if unicodedata.category(c) != 'Mn'
    ) # Suppression des accents
    
    chaine = re.sub(r'[^A-Z0-9]', '', chaine) # Suppression de tous les caractères sauf les lettres et chiffres
    
    return chaine

def comparer_chaines(str1, str2):
    return normaliser_chaine(str1) == normaliser_chaine(str2)