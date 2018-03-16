import sys
import yaml

from vivo_queries.vdos.article import Article
from vivo_queries.vdos.author import Author
from vivo_queries.vdos.journal import Journal
from pubmed_handler import Citation, PHandler
from vivo_queries import queries
from vivo_queries.vivo_connect import Connection

triples = ''

class TripleStore(object):
    def __init__(self):
        self.triples = []

    def search_for_label(self, label):
        label = '"' + label + '"'
        for trip in self.triples:
            if label in trip:
                #get existing n number
                uri = trip.split('>', 1)[0]
                number = uri.rsplit('/', 1)[-1]
                return number
        return None

    def add_triple(self, sentence):
        self.triples.append(sentence)

    def write_to_file(self, filepath):
        with open(filepath, 'w') as output:
            for triple in self.triples:
                output.write(triple + '\n')

def get_config(config_path):
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file.read())
    except:
        print("Error: Check config file")
        exit()
    return config


def identify_author(connection, store):
    author = Author(connection)
    obj_n = raw_input("Enter the n number of the person (if you do not know, leave blank): ")
    if obj_n:
        author.n_number = obj_n
    else:
        print("Enter the person's name.")
        first_name = raw_input("First name: ")
        if first_name:
            author.first = first_name
        middle_name = raw_input("Middle name: ")
        if middle_name:
            author.middle = middle_name
        last_name = raw_input("Last name: ")
        if last_name:
            author.last = last_name
        obj_name = last_name + ", " + first_name + " " + middle_name
        author.name = obj_name

        match = match_input(connection, obj_name, 'person', True)

        if not match:
            create_obj = raw_input("This person is not in the database. Would you like to add them? (y/n) ")
            if create_obj == 'y' or create_obj == 'Y':
                global triples
                print("Fill in the following details. Leave blank if you do not know what to write.")
                details = author.get_details()
                for detail in details:
                    item_info = raw_input(str(detail) + ": ")
                    setattr(author, detail, item_info)

                params = {'Author': author}
                triple = queries.make_person.write_rdf(connection, **params)
                store.add_triple(triple)
                print('*' * 6 + '\nAdding person\n' + '*' * 6)

    return author

def sort_articles(connection, pub, author, store):
    #TODO: add reviews, editorials, letters
    citation = Citation(pub['MedlineCitation'])
    try:
        obj_type = str(citation.check_key(['Article', 'PublicationTypeList'])[0])
    except IndexError as e:
        obj_type = "Journal Article"

    article = Article(connection)
    article.name = scrub(citation.check_key(['Article', 'ArticleTitle']).title())
    article.volume = citation.check_key(['Article', 'Journal', 'JournalIssue', 'Volume'])
    article.issue =  citation.check_key(['Article', 'Journal', 'JournalIssue', 'Issue'])
    article.publication_year =  citation.check_key(['Article', 'Journal', 'JournalIssue', 'PubDate', 'Year'])
    try:
        article.doi =  str(citation.check_key(['Article', 'ELocationID'])[0])
    except IndexError as e:
        pass
    article.pubmed_id =  citation.check_key(['PMID'])

    journal = get_journal(connection, citation, store)

    if obj_type=='Journal Article':
        #check if article exists
        match = match_input(connection, article.name, article.type, False)    #check with article title
        if not match:
            match = match_input(connection, article.doi, article.type, False) #check with article doi
            if not match:
                params = {'Article': article, 'Author': author, 'Journal': journal}
                triple = queries.make_academic_article.write_rdf(connection, **params)
                store.add_triple(triple)
                print('*' * 6 + '\nAdding article\n' + '*' * 6)

        if match:
            return None

    elif obj_type=='Editorial':
        pass

    else:
        return None

def scrub(label):
    clean_label = label.replace('"', '\\"')
    return clean_label

def get_journal(connection, citation, store):
    parts = queries.make_journal.get_params(connection)
    parts['Journal'].name = citation.check_key(['Article', 'Journal', 'Title']).title()
    parts['Journal'].issn = str(citation.check_key(['Article', 'Journal', 'ISSN']))

    match = match_input(connection, parts['Journal'].name, 'journal', False)     #check with journal name
    if not match:
        match = match_input(connection, parts['Journal'].issn, 'journal', False) #check with journal issn

    if match:
        parts['Journal'].n_number = match
    else:
        match = store.search_for_label(parts['Journal'].name)
        if match:
            parts['Journal'].n_number = match
        else:
            triple = queries.make_journal.write_rdf(connection, **parts)
            store.add_triple(triple)
            print('*' * 6 + '\nAdding journal\n' + '*' * 6)

    return parts['Journal']

def match_input(connection, label, category, interact):
    details = queries.find_n_for_label.get_params(connection)
    details['Thing'].name = label
    details['Thing'].extra = label
    details['Thing'].type = category

    matches = queries.find_n_for_label.run(connection, **details)

    hits = {}
    #label is passed with doi. this counts on there being no articles with the doi as their name.
    if (len(matches) == 0) and category == "academic_article":

        hits = queries.find_n_for_doi.run(connection, **details)
        if len(hits) == 1:
            for key in hits:
                match = key

    #label is passed with issn. this counts on there being no journals with the issn as their name.
    if (len(matches) == 0) and category == "journal":
        hits = queries.find_n_for_issn.run(connection, **details)
        if len(hits) == 1:
            for key in hits:
                match = key

    #single match using title
    if len(matches) == 1:
        for key in matches:
            match = key
    else:
        if interact:
            choices = {}
            count = 1
            for key, val in hits.items():
                if label.lower in val.lower():
                    choices[count] = (key, val)
                    count += 1

            index = -1
            if choices:
                for key, val in choices.items():
                    number,label = val
                    print((str(key) + ': ' + label + ' (' + number + ')\n'))

                index = input("Do any of these match your input? (if none, write -1): ")
            if not index == -1:
                nnum, label = choices.get(index)
                match = nnum
            else:
                match = None
        else:
            match = None
            #TODO: deal with duplicates
    return match

def main(config_path):
    config = get_config(config_path)

    email = config.get('email')
    password = config.get ('password')
    update_endpoint = config.get('update_endpoint')
    query_endpoint = config.get('query_endpoint')
    vivo_url = config.get('upload_url')

    connection = Connection(vivo_url, email, password, update_endpoint, query_endpoint)
    trip_store = TripleStore()

    author = identify_author(connection, trip_store)
    handler = PHandler(email)
    query = raw_input("Write your pubmed query: ")
    raw_articles = handler.get_data(query)

    for citing in raw_articles['PubmedArticle']:
        sort_articles(connection, citing, author, trip_store)

    trip_store.write_to_file('data_out/upload.rdf')

if __name__ == '__main__':
    main(sys.argv[1])
