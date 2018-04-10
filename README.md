# owl-post
Send data back and forth from VIVO

The goal of owl-post is to allow users to interact with VIVO without having to learn the ontology, SPARQL, or anything about rdf. The list of available queries can be found in the queries directory.

### Before You Begin
Make sure to edit the example config file. If you do not update it, you will not be able to communicate with your VIVO. The email and password must be for a vivo account with admin rights. The input_file is only necessary for automated processes, like hedwig.

## owls.py
```python owls.py my/path/to/config/file```

owls is the command line version of manually adding or querying data to or from Vivo through the web interface. Simply run the program, and then select the query you would like by number from the list. Then follow the instructions (make sure to leave inputs blank for information you do not know). 

## hedwig.py
```python hedwig.py my/path/to/config/file```

hedwig takes bibtex files from `webofknowledge.com/wos` and converts them into triples which it then uploads. Search the webofknowledge site with your desired query and save the results as a bibtex file (optionally to the data_in folder). Then update the config file with the bibtex file location.

## pigwidgeon.py
```python pigwidgeon.py my/path/to/config/file```

pigwidgeon interacts with the pubmed api and adds publications to an author it will ask you to specify via the command line. pigwidgeon produces rdf files which can be uploaded to VIVO through VIVO's online interface.

## hermes.py
```python hermes.py -r my/path/to/config/file```

hermes will search pubmed for all publications based on a affliation and date (soon to be customizable) and upload them into VIVO. It parses all the journals, authors, publishers, and relationships. Then it checks and validates authors and journals for n-number in VIVO. Finally it puts it all together and uploads them into VIVO.
