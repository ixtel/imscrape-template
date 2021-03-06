import logging
from datetime import datetime
from urlparse import urlparse

from eve.methods.post import post_internal
from eve.methods.patch import patch_internal

from api import api
from settings import db_connection


logger = logging.getLogger('scrapers.core.common')


class CommonMixin(object):
    """
    Common components of scrapers
    """

    name = 'base_crawler'

    scrapeErrorsCollection = 'scrapeErrors'
    scrapeWarningsCollection = 'scrapeWarnings'

    @staticmethod
    def clean_url(url):
        """
        Remove all GET parameters from url
        """
        o = urlparse(url)
        url_without_query_string = o.scheme + "://" + o.netloc + o.path
        return url_without_query_string

    @property
    def db(self):
        return db_connection()

    def save_item(self, collection, specs, data, indexes=[]):
        """
        Save or update item in collection:
            + collection - mongodb collection
            + specs - list parameters used for search
            + data - data to save
            + indexes - fields to index (specs will be used if empty)
        """
        specs_params = {field: data[field] for field in specs}

        obj = self.db[collection].find_one(specs_params)
        if obj is None:
            # insert
            with api.test_request_context():
                api_response = post_internal(collection, data)
            logger.info("Item Saved: {}".format(api_response))
        else:
            # update
            update_this = {}
            for field in specs:
                del data[field]
            for key, value in data.items():
                if key not in obj:
                    update_this[key] = value
                else:
                    if value != obj[key]:
                        update_this[key] = value

            with api.test_request_context():
                api_response = patch_internal(collection, payload=update_this, _id=obj['_id'])
            logger.info("Item Updated: {}".format(api_response))

        if not indexes:
            indexes = specs

        for index in indexes:
            self.db[collection].ensure_index(index)

    def _log2mongo(self, col, url, ex, message, **kwargs):
        """
        Log messages into mongodb collection.
        Arguments:
            + col - mongodb collection name
            + url - url of problem
            + ex - name of exception
            + message - message to log
        """

        data = {
            'url': url,
            'name': self.name,
            'exception': ex,
            'msg': message,
            '_created': datetime.utcnow(),
        }
        data.update(kwargs)
        self.db[col].insert(data)
        self.db[col].ensure_index('url')
        self.db[col].ensure_index('name')

    def log_error(self, url, exception, message, **kwargs):
        self._log2mongo(self.scrapeErrorsCollection, url, exception, message, **kwargs)

    def log_warning(self, url, exception, message, **kwargs):
        self._log2mongo(self.scrapeWarningsCollection, url, exception, message, **kwargs)
