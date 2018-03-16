from pubmed_connect import PUBnnection
from vivo_queries.name_cleaner import clean_name

class Citation(object):
    def __init__(self, data):
        self.data = data

    def check_key(self, paths, data=None):
        if not data:
            data = self.data
        if paths[0] in data:
            trail = data[paths[0]]
            if len(paths) > 1:
                trail = self.check_key(paths[1:], trail)
            return trail
        else:
            return ""

class PHandler(object):
    def __init__(self, email):
        self.pubnnection = PUBnnection(email)

    def get_data(self, query):
        id_list = self.pubnnection.get_id_list(query)
        results = self.pubnnection.get_details(id_list)
        return results

    def parse_api(self, pm_dump):
        pubs = []
        pub_auth = {}
        authors = []
        journals = {}
        pub_journ = {}

        for citing in pm_dump['PubmedArticle']:
            citation = Citation(citing['MedlineCitation'])
            pub_title = clean_name(citation.check_key(['Article', 'ArticleTitle']))
            try:
                doi = str(citation.check_key(['Article', 'ELocationID'])[0])
            except IndexError as e:
                doi = ""
            year = citation.check_key(['Article', 'Journal', 'JournalIssue', 'PubDate', 'Year'])
            volume = citation.check_key(['Article', 'Journal', 'JournalIssue', 'Volume'])
            issue = citation.check_key(['Article', 'Journal', 'JournalIssue', 'Issue'])
            pages = citation.check_key(['Article', 'Pagination', 'MedlinePgn'])
            try:
                pub_type = str(citation.check_key(['Article', 'PublicationTypeList'])[0])
            except IndexError as e:
                doi = ""
            pmid = str(citation.check_key(['PMID']))
            issn = str(citation.check_key(['Article', 'Journal', 'ISSN']))
            journ_name = clean_name(citation.check_key(['Article', 'Journal', 'Title']))

            author_dump = citation.check_key(['Article', 'AuthorList'])
            for person in author_dump:
                author = Citation(person)
                lname = clean_name(author.check_key(['LastName']))
                fname = clean_name(author.check_key(['ForeName']))
                name = lname + ', ' + fname

                if name not in authors:
                    authors.append(name)

                if pmid not in pub_auth.keys():
                    pub_auth[pmid] = [name]
                else:
                    #pubmed does not have an id for authors
                    pub_auth[pmid].append(name)

            pubs.append((doi, pub_title, year, volume, issue, pages, pub_type, pmid))
            if issn not in journals.keys():
                journals[issn] = journ_name
            pub_journ[pmid] = issn

        return (pubs, pub_auth, authors, journals, pub_journ)
