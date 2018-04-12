import sqlite3
import sys
from time import localtime, strftime
import yaml

from vivo_queries.vivo_connect import Connection
from vivo_queries import queries
from vivo_queries.triple_handler import TripleHandler

#pub order is: doi, title, year, volume, issue, pages, doctype, number

class Match(object):
    def __init__(self, vivo_title, alt_title, ratio_missing, ratio_perfect, ratio_imperfect, doi):
        self.vivo_title = vivo_title
        self.alt_title = alt_title
        self.ratio_missing = ratio_missing
        self.ratio_perfect = ratio_perfect
        self.ratio_imperfect = ratio_imperfect
        self.doi = doi

def get_config(config_path):
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file.read())
    except:
        print("Error: Check config file")
        exit()
    return config

def find_john_does(db_path, c):
    c.execute('SELECT * FROM vivo_pubs where doi=""')
    orphans = c.fetchall()

    return orphans

def get_more_details(pub, c):
    nnum = pub[7]

    #get journals
    c.execute('SELECT j.issn, j.title FROM vivo_journals as j WHERE j.journ_num in (SELECT pj.journ_num FROM vivo_pub_journ as pj WHERE pub_num=?)', (nnum,))
    journal_info = c.fetchall()

    #get authors
    c.execute('SELECT a.author_name FROM vivo_authors as a WHERE author in (SELECT pa.auth FROM vivo_pub_auth as pa WHERE pub_num=?)', (nnum,))
    authors = c.fetchall()

    return (journal_info[0], authors)

def find_matches(pub, journal_info, authors, c):
    match = None

    wos_t_match, pm_t_match = match_title(pub[1], c)
    if len(wos_t_match) == 1 or len(pm_t_match) == 1:
        try:
            wos_title = wos_t_match[0]
        except IndexError as e:
            wos_title = None
        try:
            pm_title = pm_t_match[0]
        except IndexError as e:
            pm_title = None
        match = compare_doi(wos_title, pm_title)

    if not match:
        wos_j_pubs, pm_j_pubs = match_journal(journal_info, c)
        wos_matches, pm_matches = match_author(pub[1], authors, wos_j_pubs, pm_j_pubs, c)

    return wos_matches, pm_matches

def match_title(title, c):
    print('!!!')
    c.execute('SELECT * FROM wos_pubs as p WHERE p.title=?', (title,))
    wos_title_match = c.fetchall()
    c.execute('SELECT * FROM pubmed_pubs as p WHERE p.title=?', (title,))
    pm_title_match = c.fetchall()

    return (wos_title_match, pm_title_match)

def match_journal(journal, c):
    issn = journal[0]
    j_title = journal[1]
    wos_journal_matches = []
    pm_journal_matches = []

    if issn:
        c.execute('SELECT * FROM wos_pubs as p WHERE p.wosid=(SELECT j.wosid FROM wos_pub_journ as j WHERE j.issn=?)', (issn,))
        wos_journal_matches = c.fetchall()
        c.execute('SELECT * FROM pubmed_pubs as p WHERE p.pmid=(SELECT j.pmid FROM pubmed_pub_journ as j WHERE j.issn=?)', (issn,))
        pm_journal_matches = c.fetchall()

    if not wos_journal_matches and not pm_journal_matches:
        c.execute('SELECT * FROM wos_pubs as p WHERE p.wosid in (SELECT pj.wosid FROM wos_pub_journ as pj WHERE pj.issn in (SELECT j.issn FROM wos_journals as j WHERE j.title=?))', (j_title,))
        wos_journal_matches = c.fetchall()
        c.execute('SELECT * FROM pubmed_pubs as p WHERE p.pmid in (SELECT pj.pmid FROM pubmed_pub_journ as pj WHERE pj.issn in (SELECT j.issn FROM pubmed_journals as j WHERE j.title=?))', (j_title,))
        pm_journal_matches = c.fetchall()

    return (wos_journal_matches, pm_journal_matches)

def match_author(vivo_title, vivo_authors, wos_options, pm_options, c):
    vivo_split_names = []
    for auth in vivo_authors:
        try:
            last, rest = auth[0].split(',')
            vivo_split_names.append((last.lower(), rest.lower()))
        except ValueError as e:
            vivo_split_names.append((auth[0].lower(), None))

    v_count = len(vivo_authors)
    if v_count == 0:
        v_count = 1

    wos_matches = []
    for option in wos_options:
        c.execute(('SELECT auth FROM wos_pub_auth as wpa WHERE wpa.wosid=?'), (option[7],))
        wos_authors = c.fetchall()
        wos_full_hits, wos_partial_hits, wos_misses = compare_authors(vivo_split_names, wos_authors)

        #missing/total, full/total, (full+partial)/total

        match = Match(vivo_title, option[1], (len(wos_misses)/v_count), (len(wos_full_hits)/v_count), ((len(wos_partial_hits) + len(wos_full_hits))/v_count), option[0])
        wos_matches.append(match)

    pm_matches = []
    for option in pm_options:
        c.execute(('SELECT auth FROM pubmed_pub_auth as pmpa WHERE pmpa.pmid=?'), (option[7],))
        pm_authors = c.fetchall()
        pm_full_hits, pm_partial_hits, pm_misses = compare_authors(vivo_split_names, pm_authors)

        match = Match(vivo_title, option[1], (len(pm_misses)/v_count), (len(pm_full_hits)/v_count), ((len(pm_partial_hits) + len(pm_full_hits))/v_count), option[0])
        pm_matches.append()

    return (wos_matches, pm_matches)


# def identify_pubs(config):
#     vivonnection = Connection(config.get('upload_url'), config.get('email'), config.get('password'), config.get('update_endpoint'), config.get('query_endpoint'))

def compare_authors(vivo_authors, alt_authors):
    split_name = []
    for row in alt_authors:
        try:
            last, rest = row[0].split(',')
            split_name.append((last.lower(), rest.lower()))
        except ValueError as e:
            split_name.append((row[0].lower(), None))

    full_hits = []
    partial_hits = []
    misses = []
    for person in vivo_authors:
        if person in split_name:
            full_hits.append(person)
        elif person[0] in (x for x, y in split_name):
            partial_hits.append(person)
        else:
            misses.append(person)

    return (full_hits, partial_hits, misses)

def compare_doi(wos_entry, pm_entry):
    wos_doi = None
    pm_doi = None

    if wos_entry:
        wos_doi = wos_entry[0]
    if pm_entry:
        pm_doi = pm_entry[0]
    if not wos_entry and not pm_entry:
        return "No doi"

    if wos_doi and pm_doi:
        if wos_doi == pm_doi:
            return wos_doi
        else:
            return None
    elif wos_doi:
        return wos_doi
    elif pm_doi:
        return pm_doi

def main(config_path, db_path):
    config = get_config(config_path)
    conn = sqlite3.connect(db_path) #put db in config
    c = conn.cursor()

    orphans = find_john_does(db_path, c)

    count = 0
    for pub in orphans:
        count += 1
        print(count)

        import pdb
        pdb.set_trace()
        journal_info, authors = get_more_details(pub, c)
        wos_matches, pm_matches = find_matches(pub, journal_info, authors, c)

        with open('lookit.txt', 'w') as log:
            log.write("WOS\n")
            for match in wos_matches:
                log.write('V Title: ' + match.vivo_title)
                log.write('\nOther: ' + match.alt_title)
                log.write('\nMissing ratio: ' + str(match.ratio_missing))
                log.write('\nPerfect ratio: ' + str(match.ratio_perfect))
                log.write('\nImperfect ratio: ' + str(match.ratio_imperfect))
                log.write('\nDoi: ' + match.doi)
                log.write('\n' + '=' * 20 + '\n')

            log.write("\nPUBMED\n")
            for match in pm_matches:
                log.write('V Title: ' + match.vivo_title)
                log.write('\nOther: ' + match.alt_title)
                log.write('\nMissing ratio: ' + str(match.ratio_missing))
                log.write('\nPerfect ratio: ' + str(match.ratio_perfect))
                log.write('\nImperfect ratio: ' + str(match.ratio_imperfect))
                log.write('\nDoi: ' + match.doi)
                log.write('\n' + '=' * 20 + '\n')

        if count == 5:
            exit()

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
