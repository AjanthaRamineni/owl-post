#!/usr/bin/env python
import requests
import xml.etree.cElementTree as ET
import yaml

def run(wosnnection, author, categories):
    SID = wosnnection.token
    params = wosnnection.params
    search_url = wosnnection.search_url
    headers = {'Cookie': 'SID='+SID}

    first = True
    params['userQuery'] = "(AU=" + author + ")"
    cat_query = ""
    if categories:
        for category in categories:
            if first:
                cat_query = "WC=" + category
                first = False
            else:
                cat_query = cat_query + " OR WC=" + category
        params['userQuery'] = params['userQuery'] + " AND (" + cat_query + ")"
    params['count'] = 0

    q = """
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:woksearchlite="http://woksearchlite.v3.wokmws.thomsonreuters.com">
            <soapenv:Header/>
            <soapenv:Body>  
            <woksearchlite:search>
                <queryParameters>
                  <databaseId>{databaseId}</databaseId>
                  <userQuery>{userQuery}</userQuery>  
                   <editions>
                    <collection>{collection}</collection>
                    <edition>SCI</edition>
                   </editions>
                   <editions>
                    <collection>{collection}</collection>
                    <edition>SSCI</edition>
                   </editions>
                   <editions>
                    <collection>{collection}</collection>
                    <edition>AHCI</edition>
                   </editions>
                   <editions>
                    <collection>{collection}</collection>
                    <edition>ESCI</edition>
                   </editions>
                  <queryLanguage>{queryLanguage}</queryLanguage>
                </queryParameters>
                <retrieveParameters>
                  <firstRecord>{firstRecord}</firstRecord>
                   <count>{count}</count>
                </retrieveParameters>
              </woksearchlite:search>
            </soapenv:Body>
        </soapenv:Envelope>
        """

    predata = q.format(**params)
    response = do_search(wosnnection, predata, **params)

    #Find number of records to search for
    params['count'] = response[response.index("<recordsFound>")+len("<recordsFound>"):response.index("</recordsFound>")]
    print('Records found: ' + response[response.index("<recordsFound>")+len("<recordsFound>"):response.index("</recordsFound>")])
    data = q.format(**params)
    result = do_search(wosnnection, data, **params)

    root = ET.fromstring(result)

    records = []
    for child in root.iter('records'):
        records.append(child)

    titles = []
    for record in records:
        titag = record.find('title')
        titles.append(titag.find('value').text)
        # print(records.index(record))
        
    print("Publication list created.")
    return titles

def do_search(wosnnection, query, **params):
    search_url = wosnnection.search_url
    SID = wosnnection.token
    headers = {'Cookie': 'SID='+SID}

    print(query)
    response = requests.post(search_url, data=query, headers=headers)
    result = response.text

    #check if query was successful
    if '<faultcode>' in result:
        fault = result[result.index("<faultstring>")+len("<faultstring>"):result.index("</faultstring>")]
        if "There is a problem with your session identifier (SID)" in fault:
            wosnnection.get_token()
            result = self.do_search(wosnnection, query, **params)

    return result

