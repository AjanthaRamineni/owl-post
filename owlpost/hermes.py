docstr = """
Hermes
Usage:
    hermes.py (-h | --help)
    hermes.py (-a | -r) <config_file>

Options:
 -h --help        Show this message and exit
 -a --api         Use VIVO api to upload data immediately
 -r --rdf         Produce rdf files with data
"""

from docopt import docopt
import sys
from time import localtime, strftime
import yaml

from vivo_queries import queries
from vivo_queries.name_cleaner import clean_name
from vivo_queries.vivo_connect import Connection

from pubmed_handler import PHandler

CONFIG_PATH = '<config_file>'
_api = '--api'
_rdf = '--rdf'

#cache for authors and journals

class TripleHandler(object):
    def __init__(self, api, connection):
        self.api = api
        self.connection = connection
        self.triples = []

    def update(self, query, **params):
        if self.api:
            result = self.upload(query, **params)
        else:
            result = self.add_trips(query, **params)

    def upload(self, query, **params):
        result = query.run(self.connection, **params)

    def add_trips(self, query, **params):
        result = query.write_rdf(self.connection, **params)
        self.triples.append(result)

def get_config(config_path):
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file.read())
    except Exception, e:
        print("Error: Check config file")
        print(e)
        exit()
    return config

def search_pubmed(handler, start_date, end_date):
    query = 'University of Florida[Affiliation] AND "last 1 days"[EDAT]'

    print("Searching pudmed")
    results = handler.get_data(query)

    return results

def make_updates(connection, pubs, pub_auth, authors, journals, pub_journ):
    vivo_authors = add_authors(connection, authors)
    vivo_journals = add_journals(connection, journals)
    vivo_articles = add_articles(connection, pubs, pub_journ, vivo_journals)

def add_authors(connection, authors, tripler):
    #get n_numbers for all authors included in batch. make authors that don't already exist.
    vivo_authors = {}
    for author in authors:
        if author not in vivo_authors.keys():
            author_n = match_input(connection, author, 'person', True)
            if not author_n:
                first = middle = last = ""
                try:
                    last, rest = author.split(", ")
                    try:
                        first, middle = rest.split(" ", 1)
                    except ValueError as e:
                        first = rest
                except ValueError as e:
                    last = author_clean
                auth_params = queries.make_person.get_params(connection)
                auth_params['Author'].name = author
                auth_params['Author'].last = last
                if first:
                    auth_params['Author'].first = first
                if middle:
                    auth_params['Author'].middle = middle

                result = tripler.update(queries.make_person, **auth_params)
                #queries.make_person.run(connection, **auth_params)
                author_n = auth_params['Author'].n_number
            vivo_authors[author] = author_n
    return vivo_authors

def add_journals(connection, journals, tripler):
    #get n_numbers for all journals included in batch. make journals that don't already exist.
    vivo_journals = {}
    for issn, journal in journals.items():
        if issn not in vivo_journals.keys():
            journal_n = match_input(connection, journal, 'journal', True)
            if not journal_n:
                journal_n = match_input(connection, issn, 'journal', False)
                if not journal_n:
                    journal_params = queries.make_journal.get_params(connection)
                    journal_params['Journal'].name = journal
                    journal_params['Journal'].issn = issn

                    result = tripler.update(queries.make_journal, **journal_params)
                    #result = queries.make_journal.run(connection, **journal_params)
                    journal_n = journal_params['Journal'].n_number
            vivo_journals[issn] = journal_n
    return vivo_journals

def add_articles(connection, pubs, pub_journ, vivo_journals, tripler):
    #get n_numbers for all articles in batch. make pubs that don't already exist.
    vivo_pubs = {}
    for pub in pubs:
        if pub[6] == 'Journal Article':
            if pub[1] not in vivo_pubs.values():
                pub_n = match_input(connection, pub[1], 'academic_article', True)
                if not pub_n:
                    pub_n = match_input(connection, pub[0], 'academic_article', False)
                    if not pub_n:
                        pub_params = queries.make_academic_article.get_params(connection)
                        pub_params['Article'].name = pub[1]
                        add_valid_data(pub_params['Article'], 'volume', pub[3])
                        add_valid_data(pub_params['Article'], 'issue', pub[4])
                        add_valid_data(pub_params['Article'], 'publication_year', pub[2])
                        add_valid_data(pub_params['Article'], 'doi', pub[0])
                        add_valid_data(pub_params['Article'], 'pmid', pub[7])

                        try:
                            start_page, end_page = pub[5].split("-")
                            add_valid_data(pub_params['Article'], 'start_page', start_page)
                            add_valid_data(pub_params['Article'], 'end_page', end_page)
                        except ValueError as e:
                            start_page = pub[5]
                            add_valid_data(pub_params['Article'], 'start_page', start_page)

                        issn = pub_journ[pub_params['Article'].pmid]
                        journal_n = vivo_journals[issn]
                        pub_params['Journal'].n_number = journal_n

                        result = tripler.update(queries.make_academic_article, **pub_params)
                        #result = queries.make_academic_article.run(connection, **pub_params)
                        pub_n = pub_params['Article'].n_number
                vivo_pubs[pub[7]] = pub_n
    return vivo_pubs

def add_authors_to_pubs(connection, pub_auth, vivo_pubs, vivo_authors, tripler):
    for pub, auth_list in pub_auth.items():
        for author in auth_list:
            params = queries.add_author_to_pub.get_params(connection)
            params['Article'].n_number = vivo_pubs[pub]
            params['Author'].n_number = vivo_authors[author]
            old_author = queries.check_author_on_pub.run(connection, **params)
            if not old_author:
                result = tripler.update(queries.add_author_to_pub, **params)
                #result = queries.add_author_to_pub.run(connection, **params)

def add_valid_data(article, feature, value):
    if value:
        setattr(article, feature, value)

def match_input(connection, label, category, name):
    details = queries.find_n_for_label.get_params(connection)
    details['Thing'].extra = label
    details['Thing'].type = category
    choices = {}
    match = None

    if not name:
        if category == 'journal':
            choices = queries.find_n_for_issn.run(connection, **details)
            if len(choices) == 1:
                match = choices[0]

        if category == 'academic_article':
            choices = queries.find_n_for_doi.run(connection, **details)
            if len(choices) == 1:
                match = choices[0]

    else:
        matches = queries.find_n_for_label.run(connection, **details)
        for key, val in matches.items():
            if val.endswith(" "):
                val = val[:-1]
            if label.lower() == val.lower():
                choices[key] = val

        #perfect match
        if len(choices) == 1:
            match = choices[0]

        #inclusive perfect match
        if len(choices) == 0:
            for key, val in matches.items():
                if label.lower() in val.lower():
                    choices[key] = val

            if len(choices) == 1:
                match = choices[0]

        #TODO: add to disambiguation list when multiple matches
        #if len(choices) > 1:

    return match

def main(args):
    config = get_config(args[CONFIG_PATH])
    email = config.get('email')
    password = config.get ('password')
    update_endpoint = config.get('update_endpoint')
    query_endpoint = config.get('query_endpoint')
    vivo_url = config.get('upload_url')

    use_api = (args[_api])
    use_rdf = (args[_rdf])
    start_date = 0
    end_date = 0

    connection = Connection(vivo_url, email, password, update_endpoint, query_endpoint)
    handler = PHandler(email)
    results = search_pubmed(handler, start_date, end_date)
    pubs, pub_auth, authors, journals, pub_journ = handler.parse_api(results)

    tripler = TripleHandler(use_api, connection)
    vivo_authors = add_authors(connection, authors, tripler)
    vivo_journals = add_journals(connection, journals, tripler)
    vivo_articles = add_articles(connection, pubs, pub_journ, vivo_journals, tripler)
    add_authors_to_pubs(connection, pub_auth, vivo_articles, vivo_authors, tripler)

    if use_rdf:
        timestamp = strftime("%Y_%m_%d_%H_%M")
        filename = timestamp + '_upload.rdf'
        filepath = 'data_out/' + filename
        with open(filepath, 'w') as rdf_file:
            for triple_set in tripler.triples:
                rdf_file.write(triple_set + '\n')
        print('Check ' + filepath)

    # if args[_api]:
    #     make_updates(connection, pubs, pub_auth, authors, journals, pub_journ)
    # if args[_rdf]:
    #     make_rdf(connection, pubs, pub_auth, authors, journals, pub_journ)

if __name__ == '__main__':
    args = docopt(docstr)
    main(args)
