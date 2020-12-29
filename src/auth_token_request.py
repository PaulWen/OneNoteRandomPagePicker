from scrapy import Request
from scrapy.http.headers import Headers

import microsoft_graph_device_flow as auth


class AuthTokenRequest(Request):
    """
    Override the Request object in order to set a new authorization token into the header when
    the token expires. The token is a global variable.
    Taken from: https://stackoverflow.com/questions/28771174/scrapy-scraped-website-authentication-token-expires-while-scraping
    """

    @property
    def headers(self):
        authorization_token = auth.retrieveAccessToken()
        return Headers({'Authorization': 'BEARER {}'.format(authorization_token)}, encoding=self.encoding)

    @headers.setter
    def headers(self, value):
        pass
