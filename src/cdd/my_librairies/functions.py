import unicodedata

def strip_accents(s):
   return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')
   
   
def get_datas_dict(reponses_datas, key, level: int = 1):
   for i in range(len(reponses_datas)):
      elt = reponses_datas[i]
      if level == 1:
         for k,v in elt.items():
            if k == key:
               return v