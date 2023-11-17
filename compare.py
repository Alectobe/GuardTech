import re, urllib.request, json
from clear import format_api, format_local
from exceptions import *

def markup(product: str) -> dict:
    '''
    Размечает строку по шаблону для дальнейшего сравнения.
    Позволяет определить, что за продукт перед нами.
    '''

    #дальнейшие функции проверяют принадлежность
    #слова из продукта к какому-то из атрибутов
    def is_razr(atribute: str) -> bool:
        #является ли разрядностью
        reg = r'^(x|arm)*(32|64)(-based|-bit)?$'

        if re.fullmatch(reg, atribute) != None:
            match = re.fullmatch(reg, atribute)[0]
            if 'arm' in match:
                return 'arm'+''.join([i for i in match if i.isdigit()])
            
            else:
                return ''.join([i for i in match if i.isdigit()])

    def is_version(atribute: str) -> bool:
        #является ли версией
        reg = r'^([0-9]+\.)[0-9+](.[0-9])*'

        if re.fullmatch(reg, atribute) != None:
            return re.fullmatch(reg, atribute)[0]


    marked_up = {
        'keywords' : [], #ключевые слова
        'versions' : [], #список списков версий, промежутков версий продукта
        'razr' : None, #разрядность
    }

    product = product.split(' ')
    to_skip = 0

    for i in range(len(product)):
        if to_skip > 0:
            to_skip -= 1
            continue 

        if product[i] == 'includes':
            marked_up['versions'].append((product[i+1], product[i+3]))
            to_skip = 3
      
        elif is_razr(product[i]) != None:
            marked_up['razr'] = is_razr(product[i])

        elif is_version(product[i]) != None:
            marked_up['versions'].append(is_version((product[i])))

        else:
            marked_up['keywords'].append(product[i])

    marked_up['keywords'].sort()

    return marked_up


def rate_match(atr_local: (list | str), atr_api: (list | str), type_of_atr: str) -> int:
    '''
    Оценивает насколько совпадает передаваемые атрибуты
    Возвращает Число от 0 до 2
    '''
    match type_of_atr:
        case 'keywords':
            if atr_api == atr_local:
                return 2

            else:
                flag = True
                for i in range(min(len(atr_api), len(atr_local))):
                    if atr_api[i] != atr_local[i]:
                        flag = False

                if flag:
                    return 1

                return 0

        case 'versions':
            if len(atr_api) == 0 and len(atr_local) == 0:
                return 2

            for version in atr_api:
                match version:
                    case str():
                        if atr_local[0] == version:
                            return 2

                    case tuple():
                        def format_version(v):
                            #"16.2.8" -> [16, 2, 8]
                            return [int(i) for i in v.split('.')]

                                                
                        def format_length(array, length):
                            for i in range(abs(len(array) - length)):
                                array.append(0)

                            return array

                        start = format_version(version[0])
                        end = format_version(version[1])
                        current = format_version(atr_local[0])

                        length = max([len(i) for i in [start, end, current]])

                        start = format_length(start, length)
                        end = format_length(end, length)
                        current = format_length(current, length)

                        flag = True
                        for i in range(len(current)):
                            if current[i] > end[i] or current[i] < start[i]:
                                flag = False

                            elif current[i] < end[i] and current[i] > start[i]:
                                break

                        if flag:
                            return 2

            return 0

        case 'razr':
            if atr_api == None or atr_local == None:
                return 1

            elif atr_api == atr_local:
                return 2

            else:
                return 0



def compare(product_api: str, product_local: str) -> list:
    '''
    Устанавливает, являются ли две строки разными
    названиями одного продукта
    '''

    product_local = format_local(product_local)
    product_api = format_api(product_api)

    product_local = markup(product_local)
    product_api = markup(product_api)

    rating = []
    for key in product_api.keys():
        rating.append(rate_match(product_local[key], product_api[key], key))

    return rating


def get_table(CVE: str) -> dict:
    '''
    Возвращает ссылку по CVE
    Формат: CVE-yyyy-nnnn; Пример: CVE-2017-0160
    __________________^не фиксированнное количество
    '''
    _url = f'https://api.msrc.microsoft.com/sug/v2.0/en-US/affectedProduct?$orderBy=releaseDate%20desc&$filter=cveNumber%20eq%20%27{CVE}%27'
    with urllib.request.urlopen(_url) as url:
        data = json.load(url)
        return data


def get_best_link(chunk):
    '''
    Отбор лучшей ссылки из строчки в таблице
    Monthly Rollup > Security Update > Security Hotpatch Update
    '''
    links = dict()
    for article in chunk['kbArticles']:
        match article.get('downloadName').lower():
            case 'monthly rollup':
                link = article.get('downloadUrl')
                if link != None:
                    links[2] = link

            case 'security update':
                link = article.get('downloadUrl')
                if link != None:
                    links[1] = link

            case 'security hotpatch update':
                link = article.get('downloadUrl')
                if link != None:
                    links[0] = link

    return links[max(links.keys())]


def choose(cve: str, platform: str, product: str) -> str:
    '''
    На основе таблицы, платформы и продукта выбирает ссылку 
    с лучшим совпадением
    '''
    #Запрос в апи
    table = get_table(cve)

    #Если таблица пуста, вызываем исключение
    if table['@odata.count'] == 0:
        raise EmptyTableError('No data found on microsoft servers')

    #результаы сравнений
    results = dict()

    #проход по записям таблицы
    for chunk in table['value']:
        pair = dict()

        #если продукт - ОС, то платформа не содержится в ответе
        if 'platform' in chunk and 'product' in chunk:
            pair['platform'] = compare(chunk['platform'], platform)
            pair['product'] = compare(chunk['product'], product)

        elif 'product' in chunk and 'platform' not in chunk:
            pair['product'] = compare(chunk['product'], product)

        else:
            continue
        
        #проверка результатов сравнения для каждого элемента пары
        if (0 not in [] if pair.get('platform') == None else pair.get('platform')) and (0 not in pair['product']):
            link = get_best_link(chunk) 
            if link != None:
                res_platform = 0
                if pair.get('platform') != None:
                    res_platform = int(''.join(map(str, pair['platform'])))

                compare_result = int(''.join(map(str, pair['product']))) + res_platform
                #если есть идеальное совпадение - сразу возвращаем результат
                if compare_result == 444 or compare_result == 222:
                    return link
                else:
                    results[link] = compare_result

    #лучший результат сравнения
    max_result = max(results.values())
    for link in results:
        if results[link] == max_result:
            return link