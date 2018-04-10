import os
import os.path
import pprint
import sys
import yaml
import re

from vivo_queries import catalog
from vivo_queries.vivo_connect import Connection
from vivo_queries.vdos.author import Author
from vivo_queries import queries


def get_config(config_path):
    try:
        with open(config_path, 'r') as config_file:
            config = yaml.load(config_file.read())
    except:
        print("Error: Check config file")
        exit()
    return config


def prepare_query(connection):
    template_choice = get_template_type('queries')

    # head, sep, tail = template_type.partition('.')
    # template_choice = head
    print(template_choice)

    template_mod = getattr(queries, template_choice)
    params = template_mod.get_params(connection)

    for key, val in params.items():
        fill_details(connection, key, val, template_choice)

    response = template_mod.run(connection, **params)
    pprint.pprint(response)


def get_template_type(folder):
    available_queries = catalog.list_queries()
    template_options = {}

    for c, query in enumerate(available_queries, 1):
        template_options[c] = query

    for key, val in template_options.items():
        print(str(key) + ': ' + val + '\n')

    index = int(raw_input("Enter number of query: "))
    return template_options.get(index)


def fill_details(connection, key, item, task):
    """
    Given an item, calls get_details and iterates through the list, prompting the user for the literal values.
    """
    print('*' * 20 + '\n' * 2 + "Working on " + key + '\n' * 2 + '*' * 20)
    try:
        sub_task = "make_" + item.type
    except TypeError as e:
        sub_task = None   #Anything using a Thing will have a blank type

    print("Fill in the values for the following (if you do not have a value, leave blank):")
    #Check if user knows n number
    obj_n = raw_input("N number: ")

    if obj_n:
        item.n_number = obj_n
        #TODO: add label check
    else:
        #For non-Thing objects, ask for further detail
        if key != 'Thing':
            obj_name=''
            #Ask for label
            if key == 'Author':
                first_name = raw_input("First name: ")
                if first_name:
                    item.first = first_name

                middle_name = raw_input("Middle name: ")
                if middle_name:
                    item.middle = middle_name

                last_name = raw_input("Last name: ")
                if last_name:
                    item.last = last_name

                if last_name:
                    obj_name = last_name
                    if first_name:
                        obj_name = obj_name + ", " + first_name
                        if middle_name:
                            obj_name = obj_name + " " + middle_name
                    elif middle_name:
                        obj_name = obj_name + ", " + middle_name
                elif first_name:
                    if middle_name:
                        obj_name = first_name + " " + middle_name
                    else:
                        obj_name = first_name
                elif middle_name:
                    obj_name = middle_name

            else:
                obj_name = raw_input(key + " name/title: ")

            if obj_name:
                item.name = scrub(obj_name)
                # Check if label already exists
                if item.type == 'contributor' and key == 'Contributor_PI':
                    item.type = 'contributor_pi'
                elif item.type == 'contributor' and key == 'Contributor_CoPI':
                    item.type = 'contributor_copi'

                match = match_input(connection, item.name, item.type, True)

                if not match:
                    if sub_task != task:
                        # If this entity is not the original query, make entity
                        create_obj = raw_input("This " + item.type + " is not in the database. Would you like to add it? (y/n) ")
                        if create_obj == 'y' or create_obj == 'Y':
                            try:
                                update_path = getattr(queries, sub_task)
                                sub_params = update_path.get_params(connection)
                                if task == 'make_grant' and key in ['AwardingDepartment', 'SubContractedThrough', 'AdministeredBy', 'SupportedWork', 'Contributor_PI', 'Contributor_CoPI']:
                                    details = item.get_details()
                                    for feature in details:
                                        item_info = raw_input(str(feature) + ": ")
                                        setattr(item, feature, item_info)

                                    if (task == 'make_grant' and key == 'AwardingDepartment') or (task == 'make_grant' and key == 'SubContractedThrough'):
                                        sub_params = {'Organization': item}
                                    elif task == 'make_grant' and key == 'AdministeredBy':
                                        sub_params = {'Organization': item}
                                    elif task == 'make_grant' and key == 'SupportedWork':
                                        sub_params = {'Article': item, 'Author': None, 'Journal': None}
                                    elif task == 'make_grant' and (key == 'Contributor_PI' or key == 'Contributor_CoPI'):
                                        author = Author(connection)
                                        print("Author details:")
                                        details = author.get_details()
                                        for feature in details:
                                            item_info = raw_input(str(feature) + ": ")
                                            setattr(author, feature, item_info)

                                        try:
                                            sub_update_path = getattr(queries, 'make_person')
                                            sub_params2 = {'Author': author}
                                            response2 = sub_update_path.run(connection, **sub_params2)
                                        except Exception as e:
                                            print(e)
                                            print("Owl Post can not create a(n) " + author.type +
                                                  " at this time. Please go to your vivo site and make it manually.")

                                        sub_params = {'Contributor': item, 'Author': author}

                                else:
                                    sub_params[key] = item
                                print(sub_task)
                                response = update_path.run(connection, **sub_params)
                                print(response)
                            except Exception as e:
                                print(e)
                                print("Owl Post can not create a(n) " + item.type + " at this time. Please go to your vivo site and make it manually.")
                            return
                else:
                    item.n_number = match
                    print("The n number for this " + item.type + " is " + item.n_number)
                    return
            else:
                # TODO: Decide what to do if no name
                pass

        if task == 'make_grant' and key in ['AwardingDepartment', 'SubContractedThrough', 'AdministeredBy', 'SupportedWork', 'Contributor_PI', 'Contributor_CoPI']:
            pass
        elif key == 'Thing' or obj_name:
            details = item.get_details()
            for feature in details:
                item_info = raw_input(str(feature) + ": ")
                setattr(item, feature, item_info)
        else:
            print("Look up the n number and try again.")


def match_input(connection, label, category, exact_match):

    details = queries.find_n_for_label.get_params(connection)
    details['Thing'].extra = label
    details['Thing'].type = category

    print(category)

    matches = queries.find_n_for_label.run(connection, **details)

    choices = {}
    count = 1
    for key, val in matches.items():
        choices[count] = (key, val)
        count += 1

    if exact_match:
        if choices:
            for key, val in choices.items():
                number, lab = val
                if lab.lower() == label.lower():
                    match = number
                    return match
        match = None
        return None

    index = -1
    if choices:
        for key, val in choices.items():
            number, label = val
            print(str(key) + ': ' + label + ' (' + number +')\n')

        index = raw_input("Do any of these match your input? (if none, write -1): ")

    if not index == -1:
        nnum, label = choices.get(index)
        match = nnum
    else:
        match = None

    return match


def scrub(label):
    clean_label = label.replace('"', '\\"')
    return clean_label


def main(argv1):
    config_path = argv1
    config = get_config(config_path)

    email = config.get('email')
    password = config.get ('password')
    update_endpoint = config.get('update_endpoint')
    query_endpoint = config.get('query_endpoint')
    vivo_url = config.get('upload_url')

    connection = Connection(vivo_url, email, password, update_endpoint, query_endpoint)

    prepare_query(connection)


if __name__ == '__main__':
    main(sys.argv[1])
