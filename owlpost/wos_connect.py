import subprocess
import time

class WOSnnection(object):
    def __init__(self, config):
        self.token = None
        self.credentials = config.get('b64_credentials')
        self.search_url = 'http://search.webofknowledge.com/esti/wokmws/ws/WokSearchLite'
        self.params = {}
        self.params['databaseId'] = 'WOS'
        self.params['collection'] = 'WOS'
        self.params['queryLanguage'] = 'en'
        self.params['firstRecord'] = '1'

        self.get_token()

    def get_token(self):
        response = subprocess.check_output('curl -H "Authorization: Basic {}" -d "@wos/msg.xml" -X POST "http://search.webofknowledge.com/esti/wokmws/ws/WOKMWSAuthenticate"'.format(self.credentials), shell=True)
        print("Response: ", response)
        try:
            result = response[response.index("<return>")+len("<return>"):response.index("</return>")]
            print(result)
            self.token = result
        except ValueError as e:
            #wait for throttling to end
            print("Waiting 60 seconds for api")
            time.sleep(60)
            self.get_token()        