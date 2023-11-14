from bs4 import BeautifulSoup
import csv, requests, urllib.request, json, progress
from progress.bar import *
from fnmatch import fnmatch
#принимает номер CVE yyyy-nnnn[n] (год - 4 знака, номер - 4-5 знаков)
#возвращает таблицу в формате json

def get_table(CVE):
    _url = f'https://api.msrc.microsoft.com/sug/v2.0/en-US/affectedProduct?$orderBy=releaseDate%20desc&$filter=cveNumber%20eq%20%27{CVE}%27'
    with urllib.request.urlopen(_url) as url:
        data = json.load(url)
        return data


def link_getter(chunk, index):
    try:
        return chunk['kbArticles'][ind]['downloadUrl']

    except KeyError:
        return None


def get_link(CVE, platform, product):
    data = get_table(CVE)

    for chunk in data['value']:
        if chunk['product'] == product and chunk['platform'] == platform:
            if chunk['kbArticles'][0]['downloadName'] == "Monthly Rollup":
                return link_getter(chunk, 0)
           
            else:
                return link_getter(chunk, 1)


# foramt : nnnnnnn [7]
def get_kb(KB):
    _url = f'https://catalog.update.microsoft.com/Search.aspx?q=KB{KB}'
    response = requests.get(_url)
    return response.text

def markup(product: str) -> dict:
    '''
    Размечает строку по шаблону для дальнейшего сравнения.
    Позволяет определить, что за продукт перед нами.
    '''
    marked_up = {
        'product' : None, #Тип, когда определен - list
        'spec' : None, #str
        'family' : None, #str
        'version' : None, #str
        'architect': None #str
        }
        
    product = product.split(' - ')
    #Microsoft Windows - Windows 10 version 21H1 ProfessionalWorkstation (x64)
    #->
    #['Microsoft Windows',
    #'Windows 10 version 21H1 ProfessionalWorkstation (x64)']
    for i in range(len(product)):
        product[i] = product[i].replace('\\', '*')
        product[i] = product[i].replace(' ', '*')            
        product[i] = product[i].replace(')', '')
        product[i] = product[i].replace('(', '')
        product[i] = product[i].split('*')
    #['Microsoft Windows',
    #'Windows 10 version 21H1 ProfessionalWorkstation (x64)']
    #->
    #[['Microsoft', 'Windows'],
    #['Windows', '10', 'version', '21H1', 'ProfessionalWorkstation',
    #'x64']]
    for i in range(len(product)):
        match product[i]:
            case ['Microsoft', *prod]:
                marked_up['product'] = prod
                    
                match product[i+1]:
                    case ['Windows', '7', _, architect, *trash]:
                        marked_up['family'] = '7'
                        marked_up['architect'] = architect[:2]

                    case ['Windows', family, spec, version, _, architect, *trash]:
                        marked_up['spec'] = spec
                        marked_up['family'] = family
                        marked_up['version'] = version

                        for i in range(len(architect)):
                            if architect[i] == 'x':
                                marked_up['architect'] = architect[i:i+3]

                    case [*version]:
                        marked_up['version'] = version
            case _:
                raise NotImplementedError('Non-Microsoft Product')

    for key in marked_up.keys()
        try:
            marked_up[key] = marked_up[key].lower()


    return marked_up


def compare(product1: str, product2: str) -> bool:
    '''
    Устанавливает, являются ли две строки разными
    названиями одного продукта
    '''
    pass
     
    



def main():
    with open('obraz.csv', 'r', encoding='utf-8', newline='') as file:
        bar = ChargingBar("Просчитано: ", max=1142)
        reader = csv.DictReader(file)
        counter = 0

        for row in reader:
            for cve in row['CVE'].split(','):            
                cve = cve.lstrip().rstrip()
           
                try:
                    link = get_link(cve, row['OS'], row['PO'])
                    if link != None:
                        counter += 1

                except:
                    print('Err')

            bar.next()

        print(counter, f'{(counter/1142 * 100)} %')

            

if __name__ == '__main__':
    main()
