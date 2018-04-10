docstr = """
Hermes
Usage:
    hermes.py (-h | --help)
    hermes.py (-a | -r) [-d] <config_file>

Options:
 -h --help        Show this message and exit
 -a --api         Use VIVO api to upload data immediately
 -r --rdf         Produce rdf files with data
 -d --database     Put api results into MySQL database
"""

from docopt import docopt
import mysql.connector as mariadb
import os
import os.path
from time import localtime, strftime
import yaml

from vivo_queries import queries
from vivo_queries.name_cleaner import clean_name
from vivo_queries.vivo_connect import Connection
from vivo_queries.update_log import UpdateLog

from pubmed_handler import PHandler
from triple_handler import TripleHandler

CONFIG_PATH = '<config_file>'
_api = '--api'
_rdf = '--rdf'
_db = '--database'

#TODO:cache for authors and journals

def get_config(config_path):
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file.read())
    except Exception as e:
        print("Error: Check config file")
        print(e)
        exit()
    return config

def make_folders(log_folder, folders):
    if not os.path.isdir(log_folder):
        os.mkdir(log_folder)

    for folder in folders:
        if not os.path.isdir(folder):
            os.mkdir(folder)

def search_pubmed(handler, log_file):
    query = 'University of Florida[Affiliation] AND "last 1 days"[edat]'

    print("Searching pubmed")
    results = handler.get_data(query, log_file)

    return results

def sql_insert(db, db_port, db_user, db_pw, handler, pubs, pub_auth, authors, journals, pub_journ):
    #put database in config
    conn = mariadb.connect(user=db_user, password=db_pw, port=db_port, database=db)
    c = conn.cursor()
    handler.prepare_tables(c)

    handler.local_add_pubs(c, pubs, 'hermes')
    handler.local_add_authors(c, authors)
    handler.local_add_journals(c, journals, 'hermes')
    handler.local_add_pub_auth(c, pub_auth)
    handler.local_add_pub_journ(c, pub_journ)

    conn.commit()

def add_authors(connection, authors, tripler, ulog, disamb_file):
    #get n_numbers for all authors included in batch. make authors that don't already exist.
    vivo_authors = {}
    for author in authors:
        if author not in vivo_authors.keys():
            author_n = match_input(connection, author, 'person', True, disamb_file)
            if not author_n:
                first = middle = last = ""
                try:
                    last, rest = author.split(", ")
                    try:
                        first, middle = rest.split(" ", 1)
                    except ValueError as e:
                        first = rest
                except ValueError as e:
                    last = author
                auth_params = queries.make_person.get_params(connection)
                auth_params['Author'].name = author
                auth_params['Author'].last = last
                if first:
                    auth_params['Author'].first = first
                if middle:
                    auth_params['Author'].middle = middle

                result = tripler.update(queries.make_person, **auth_params)
                author_n = auth_params['Author'].n_number
                ulog.add_to_log('authors', author, (connection.vivo_url + author_n))

            vivo_authors[author] = author_n
    return vivo_authors

def add_journals(connection, journals, tripler, ulog, disamb_file):
    #get n_numbers for all journals included in batch. make journals that don't already exist.
    vivo_journals = {}
    for issn, journal in journals.items():
        if issn not in vivo_journals.keys():
            journal_n = match_input(connection, journal, 'journal', True, disamb_file)
            if not journal_n:
                journal_n = match_input(connection, issn, 'journal', False, disamb_file)
                if not journal_n:
                    journal_params = queries.make_journal.get_params(connection)
                    journal_params['Journal'].name = journal
                    journal_params['Journal'].issn = issn

                    result = tripler.update(queries.make_journal, **journal_params)
                    #result = queries.make_journal.run(connection, **journal_params)
                    journal_n = journal_params['Journal'].n_number
                    ulog.add_to_log('journals', journal, (connection.vivo_url + journal_n))

            vivo_journals[issn] = journal_n

    return vivo_journals

def add_articles(connection, pubs, pub_journ, vivo_journals, tripler, ulog, disamb_file):
    #get n_numbers for all articles in batch. make pubs that don't already exist.
    vivo_pubs = {}

    for pub in pubs:
        pub_type = None
        query_type = None
        if pub[6] == 'Journal Article':
            pub_type = 'academic_article'
            query_type = getattr(queries, 'make_academic_article')
        elif pub[6] == 'Letter':
            pub_type = 'letter'
            query_type = getattr(queries, 'make_letter')
        elif pub[6] == 'Editorial' or pub[6] == 'Comment':
            pub_type = 'editorial'
            query_type = getattr(queries, 'make_editorial_article')
        else:
            query_type = 'pass'

        if pub[1] not in vivo_pubs.values():
            pub_n = match_input(connection, pub[1], pub_type, True, disamb_file)
            if not pub_n:
                pub_n = match_input(connection, pub[0], pub_type, False, disamb_file)
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
                    
                    if query_type=='pass':
                        ulog.track_skips(pub[6], **pub_params)
                    else:
                        result = tripler.update(query_type, **pub_params)
                        pub_n = pub_params['Article'].n_number
                        ulog.add_to_log('articles', pub[1], (connection.vivo_url + pub_n))
                
            vivo_pubs[pub[7]] = pub_n
    return vivo_pubs

def add_authors_to_pubs(connection, pub_auth, vivo_pubs, vivo_authors, tripler, ulog):
    for pub, auth_list in pub_auth.items():
        for author in auth_list:
            params = queries.add_author_to_pub.get_params(connection)
            params['Article'].n_number = vivo_pubs[pub]
            params['Author'].n_number = vivo_authors[author]

            if pub in ulog.skips.keys():
                ulog.add_author_to_skips(pub, author)
            else:
                old_author = queries.check_author_on_pub.run(connection, **params)
                if not old_author:
                    result = tripler.update(queries.add_author_to_pub, **params)
                    #result = queries.add_author_to_pub.run(connection, **params)

def add_valid_data(article, feature, value):
    if value:
        setattr(article, feature, value)

def match_input(connection, label, category, name, disamb_file):
    details = queries.find_n_for_label.get_params(connection)
    details['Thing'].extra = label
    details['Thing'].type = category
    choices = {}
    match = None

    if not name:
        if category == 'journal':
            choices = queries.find_n_for_issn.run(connection, **details)
            if len(choices) == 1:
                match = list(choices.keys())[0]

        if category == 'academic_article':
            choices = queries.find_n_for_doi.run(connection, **details)
            if len(choices) == 1:
                match = list(choices.keys())[0]

    else:
        matches = queries.find_n_for_label.run(connection, **details)
        for key, val in matches.items():
            if val.endswith(" "):
                val = val[:-1]
            if label.lower() == val.lower():
                choices[key] = val

        #perfect match
        if len(choices) == 1:
            match = list(choices.keys())[0]

        #inclusive perfect match
        if len(choices) == 0:
            for key, val in matches.items():
                if label.lower() in val.lower():
                    choices[key] = val

            if len(choices) == 1:
                match = list(choices.keys())[0]

        if len(choices) > 1:
            with open(disamb_file, "a+") as dis_file:
                #TODO: this won't contain the about-to-be-newly added uri
                dis_file.write("{} has possible uris: \n{}\n".format(label, list(choices.keys())))
    return match

def main(args):
    config = get_config(args[CONFIG_PATH])
    email = config.get('email')
    password = config.get ('password')
    update_endpoint = config.get('update_endpoint')
    query_endpoint = config.get('query_endpoint')
    vivo_url = config.get('upload_url')

    connection = Connection(vivo_url, email, password, update_endpoint, query_endpoint)
    handler = PHandler(email)

    try:
        log_folder = config.get('folder_for_logs')
    except KeyError as e:
        log_folder = './'

    disam = os.path.join(log_folder, 'disambiguation')
    output = os.path.join(log_folder, 'output')
    uploads = os.path.join(log_folder, 'uploads')
    make_folders(log_folder, [disam, output, uploads])

    timestamp = strftime("%Y_%m_%d")
    disam_file = os.path.join(disam, ('disambiguation_' + timestamp + '.txt'))
    output_file = os.path.join(output, ('output_file_' + timestamp + '.txt'))
    upload_file = os.path.join(uploads, ('upload_log_' + timestamp + '.txt'))
    skips_file = os.path.join(uploads, ('skips_' + timestamp + '.txt'))

    results = search_pubmed(handler, output_file)
    pubs, pub_auth, authors, journals, pub_journ = handler.parse_api(results)

    if args[_db]:
        db = config.get('database')
        db_port = config.get('database_port')
        db_user = config.get('database_user')
        db_pw = config.get('database_pw')
        sql_insert(db, db_port, db_user, db_pw, handler, pubs, pub_auth, authors, journals, pub_journ)

    tripler = TripleHandler(args[_api], connection, output_file)
    ulog = UpdateLog()
    try:
        vivo_authors = add_authors(connection, authors, tripler, ulog, disam_file)
        vivo_journals = add_journals(connection, journals, tripler, ulog, disam_file)
        vivo_articles = add_articles(connection, pubs, pub_journ, vivo_journals, tripler, ulog, disam_file)
        add_authors_to_pubs(connection, pub_auth, vivo_articles, vivo_authors, tripler, ulog)
    except Exception as e:
        print('Error')
        raise(e)
        with open(output_file, 'a+') as log:
            log.write("Error\n")
            log.write(str(e))

    ulog.create_file(upload_file)
    ulog.write_skips(skips_file)

    if args[_rdf]:
        rdf_file = timestamp + '_upload.rdf'
        rdf_filepath = os.path.join(uploads, rdf_file)
        tripler.print_rdf(rdf_filepath)

if __name__ == '__main__':
    args = docopt(docstr)
    main(args)
